"""Health assessment routes — /api/clusters/{name}/health/* endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from elastro.core.logger import get_logger
from elastro.health.assessor import HealthAssessor
from elastro.health.collectors.nodes import NodesCollector
from elastro.health.collectors.base import CollectContext
from elastro.health.config import DEFAULT_HISTORY_INDEX
from elastro.health.history import (
    filter_records_by_window,
    parse_window,
    query_assessment_history,
)
from elastro.health.models import AssessmentReport, FindingStatus
from elastro.health.trends import compute_trends_from_records
from elastro.health.remediation.catalog import RemediationCatalog
from elastro.health.remediation.executor import RemediationExecutor
from elastro.health.rules.jvm import jvm_heap_used_percent
from elastro.server.health_cache import (
    DEFAULT_TTL_SECONDS,
    get_cached_report,
    get_history,
    store_report,
)
from elastro.server.schemas import HealthFixRequestSchema
from elastro.server.services import build_es_client

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["health"])


def _health_assessment_settings(read_config: Any) -> Dict[str, Any]:
    config = read_config()
    health = config.get("health", {}) if isinstance(config, dict) else {}
    assessment = health.get("assessment", {}) if isinstance(health, dict) else {}
    if not isinstance(assessment, dict):
        assessment = {}
    return {
        "enable_history": bool(assessment.get("enable_history", False)),
        "history_index": str(assessment.get("history_index", DEFAULT_HISTORY_INDEX)),
    }


def _merge_history(
    cluster_name: str,
    *,
    es_records: List[Dict[str, Any]],
    cache_records: List[Dict[str, Any]],
    limit: int,
) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    for record in es_records + cache_records:
        if not isinstance(record, dict):
            continue
        session_id = str(record.get("session_id", ""))
        assessed_at = str(record.get("assessed_at", ""))
        key = session_id or assessed_at or str(id(record))
        existing = merged.get(key)
        if existing is None or str(record.get("assessed_at", "")) > str(
            existing.get("assessed_at", "")
        ):
            merged[key] = record

    records = sorted(
        merged.values(),
        key=lambda item: str(item.get("assessed_at", "")),
        reverse=True,
    )
    return records[:limit]


def _load_cluster_history(
    cluster_name: str,
    target: Dict[str, Any],
    read_config: Any,
    *,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    settings = _health_assessment_settings(read_config)
    cache_records = get_history(cluster_name, limit=limit)
    if not settings["enable_history"]:
        return cache_records

    try:
        client = build_es_client(target)
        es_records = query_assessment_history(
            client,
            history_index=settings["history_index"],
            cluster_name=cluster_name,
            limit=limit,
        )
        return _merge_history(
            cluster_name,
            es_records=es_records,
            cache_records=cache_records,
            limit=limit,
        )
    except Exception as exc:
        logger.warning(
            "ES history unavailable for cluster=%s; using cache only: %s",
            cluster_name,
            exc,
        )
        return cache_records


def _find_cluster(read_config: Any, cluster_name: str) -> Dict[str, Any]:
    config = read_config()
    target = next(
        (c for c in config.get("clusters", []) if c["name"] == cluster_name),
        None,
    )
    if not target:
        raise HTTPException(
            status_code=404,
            detail=f"Cluster '{cluster_name}' not found in configuration.",
        )
    return target


def _serialize_report(
    report: AssessmentReport,
    *,
    include_raw: bool = False,
) -> Dict[str, Any]:
    payload = report.model_dump(mode="json")
    if not include_raw:
        payload.pop("raw_health_report", None)
    return payload


def _open_findings(report: AssessmentReport) -> List[Dict[str, Any]]:
    """Return non-passing findings suitable for GUI display."""
    open_statuses = {
        FindingStatus.WARN,
        FindingStatus.FAIL,
        FindingStatus.UNKNOWN,
    }
    findings = [
        finding for finding in report.findings if finding.status in open_statuses
    ]
    findings.sort(
        key=lambda item: (
            0
            if item.severity.value == "critical"
            else 1
            if item.severity.value == "high"
            else 2
            if item.severity.value == "medium"
            else 3,
            item.title,
        )
    )
    return [finding.model_dump(mode="json") for finding in findings]


def _run_assessment(
    cluster_name: str,
    target: Dict[str, Any],
    read_config: Any,
    *,
    verbose: bool = True,
    features: Optional[List[str]] = None,
    timeout: str = "30s",
) -> AssessmentReport:
    settings = _health_assessment_settings(read_config)
    client = build_es_client(target)
    assessor = HealthAssessor(client)
    feature = features[0] if features else None
    history_records = _load_cluster_history(
        cluster_name,
        target,
        read_config,
        limit=20,
    )
    report = assessor.run(
        timeout=timeout,
        verbose_report=verbose,
        feature=feature,
        assessment_history=history_records,
        enable_history=settings["enable_history"],
        history_index=settings["history_index"],
        host=str(target.get("host", "unknown")),
    )
    if report.cluster_name == "unknown":
        report = report.model_copy(update={"cluster_name": cluster_name})
    store_report(cluster_name, report, ttl_seconds=DEFAULT_TTL_SECONDS)
    return report


def _disk_used_percent(fs: Dict[str, Any]) -> Optional[float]:
    total = fs.get("total") or {}
    available = total.get("available_in_bytes")
    total_bytes = total.get("total_in_bytes")
    if available is None or not total_bytes:
        return None
    try:
        used = float(total_bytes) - float(available)
        return round((used / float(total_bytes)) * 100, 2)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _summarize_nodes(nodes: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    summary: List[Dict[str, Any]] = []
    for node_id, node in nodes.items():
        if not isinstance(node, dict):
            continue
        summary.append(
            {
                "id": node_id,
                "name": node.get("name", node_id),
                "roles": node.get("roles", []),
                "heap_used_percent": jvm_heap_used_percent(node.get("jvm") or {}),
                "disk_used_percent": _disk_used_percent(node.get("fs") or {}),
            }
        )
    summary.sort(key=lambda item: item.get("name") or "")
    return summary


def health_routes(read_config: Any, verify_token: Any) -> APIRouter:
    """Bind health routes to shared config accessor and auth."""

    @router.get("/clusters/{cluster_name}/health/assess")
    def assess_cluster_health(
        cluster_name: str,
        verbose: bool = Query(True, description="Request verbose _health_report"),
        features: Optional[List[str]] = Query(None, description="Limit indicators"),
        token: str = Depends(verify_token),
    ) -> Dict[str, Any]:
        target = _find_cluster(read_config, cluster_name)
        try:
            logger.info("GUI health assess requested for cluster=%s", cluster_name)
            report = _run_assessment(
                cluster_name,
                target,
                read_config,
                verbose=verbose,
                features=features,
            )
            return _serialize_report(report)
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(
                "Health assess failed for %s: %s",
                cluster_name,
                exc,
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail=f"Health assessment failed: {exc}",
            ) from exc

    @router.get("/clusters/{cluster_name}/health/score")
    def get_cluster_health_score(
        cluster_name: str,
        refresh: bool = Query(False, description="Bypass cache and re-assess"),
        token: str = Depends(verify_token),
    ) -> Dict[str, Any]:
        target = _find_cluster(read_config, cluster_name)
        cached = None if refresh else get_cached_report(cluster_name)

        try:
            if cached is None:
                report = _run_assessment(cluster_name, target, read_config)
            else:
                report = cached

            return {
                "cluster_name": cluster_name,
                "overall_score": report.overall_score,
                "overall_status": report.overall_status.value,
                "assessed_at": report.assessed_at.isoformat(),
                "elasticsearch_version": report.elasticsearch_version,
                "cached": cached is not None and not refresh,
                "findings_count": len(_open_findings(report)),
            }
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(
                "Health score failed for %s: %s",
                cluster_name,
                exc,
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail=f"Failed to compute health score: {exc}",
            ) from exc

    @router.get("/clusters/{cluster_name}/health/findings")
    def get_cluster_health_findings(
        cluster_name: str,
        token: str = Depends(verify_token),
    ) -> Dict[str, Any]:
        _find_cluster(read_config, cluster_name)
        report = get_cached_report(cluster_name)
        if report is None:
            raise HTTPException(
                status_code=404,
                detail="No cached assessment. Run GET /health/assess first.",
            )
        return {
            "cluster_name": cluster_name,
            "overall_score": report.overall_score,
            "findings": _open_findings(report),
        }

    @router.get("/clusters/{cluster_name}/health/history")
    def get_cluster_health_history(
        cluster_name: str,
        limit: int = Query(10, ge=1, le=50),
        token: str = Depends(verify_token),
    ) -> Dict[str, Any]:
        target = _find_cluster(read_config, cluster_name)
        settings = _health_assessment_settings(read_config)
        assessments = _load_cluster_history(
            cluster_name,
            target,
            read_config,
            limit=limit,
        )
        return {
            "cluster_name": cluster_name,
            "assessments": assessments,
            "source": "merged" if settings["enable_history"] else "cache",
        }

    @router.get("/clusters/{cluster_name}/health/trends")
    def get_cluster_health_trends(
        cluster_name: str,
        window: str = Query("7d", description="History window (7d, 24h, 30d)"),
        limit: int = Query(50, ge=1, le=200),
        finding: Optional[str] = Query(None, description="Filter recurring findings"),
        token: str = Depends(verify_token),
    ) -> Dict[str, Any]:
        target = _find_cluster(read_config, cluster_name)
        settings = _health_assessment_settings(read_config)
        try:
            parse_window(window)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        try:
            records = _load_cluster_history(
                cluster_name,
                target,
                read_config,
                limit=limit,
            )
            records = filter_records_by_window(records, window)
            report = compute_trends_from_records(
                records,
                cluster_name=cluster_name,
                window=window,
                finding_id=finding,
                source="merged" if settings["enable_history"] else "cache",
            )
            return report.to_dict()
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(
                "Health trends failed for %s: %s",
                cluster_name,
                exc,
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail=f"Failed to compute health trends: {exc}",
            ) from exc

    @router.get("/clusters/{cluster_name}/health/nodes")
    def get_cluster_health_nodes(
        cluster_name: str,
        token: str = Depends(verify_token),
    ) -> Dict[str, Any]:
        target = _find_cluster(read_config, cluster_name)
        try:
            client = build_es_client(target)
            collector = NodesCollector()
            ctx = CollectContext(client=client, timeout="30s")
            result = collector.collect(ctx)
            if result.status != "ok":
                raise HTTPException(
                    status_code=500,
                    detail=result.error or "Failed to collect node stats",
                )
            nodes = result.data.get("nodes", {})
            return {
                "cluster_name": cluster_name,
                "node_count": result.data.get("node_count", len(nodes)),
                "nodes": _summarize_nodes(nodes),
            }
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(
                "Health nodes failed for %s: %s",
                cluster_name,
                exc,
                exc_info=True,
            )
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @router.post("/clusters/{cluster_name}/health/fix")
    def apply_health_fix(
        cluster_name: str,
        req: HealthFixRequestSchema,
        token: str = Depends(verify_token),
    ) -> Dict[str, Any]:
        target = _find_cluster(read_config, cluster_name)
        action = req.action
        if action == "reroute":
            action = "reroute_failed"

        index_name = req.index_name
        if not index_name and req.finding_id:
            report = get_cached_report(cluster_name)
            if report:
                finding = next(
                    (f for f in report.findings if f.id == req.finding_id),
                    None,
                )
                if finding and finding.affected_resources:
                    index_name = finding.affected_resources[0]

        entry = RemediationCatalog.get(action)
        if entry is None:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown remediation action: {req.action}",
            )
        if entry.requires_index and not index_name:
            raise HTTPException(
                status_code=400,
                detail="index_name is required for this remediation action",
            )

        try:
            logger.info(
                "GUI health fix requested cluster=%s action=%s index=%s dry_run=%s",
                cluster_name,
                action,
                index_name,
                req.dry_run,
            )
            from elastro.health.audit import HealthAuditLogger

            client = build_es_client(target)
            cached_report = get_cached_report(cluster_name)
            session_id = cached_report.session_id if cached_report else None
            audit = HealthAuditLogger(client, host=str(target.get("host", "unknown")))
            executor = RemediationExecutor(
                client,
                dry_run=req.dry_run,
                interactive=False,
                api_mode=True,
                session_id=session_id,
                audit_logger=audit,
                cluster_name=cluster_name,
            )
            result = executor.execute_action(action, index_name)
            if result.dry_run:
                return {
                    "status": "dry_run",
                    "action": action,
                    "index_name": index_name,
                    "planned_api_call": result.planned_api_call,
                    "message": result.message,
                    "rollback_id": result.rollback_id,
                }
            if not result.success:
                raise HTTPException(status_code=500, detail=result.message)
            return {
                "status": "success",
                "action": action,
                "index_name": index_name,
                "message": result.message,
                "rollback_id": result.rollback_id,
            }
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(
                "Health fix failed cluster=%s action=%s: %s",
                cluster_name,
                action,
                exc,
                exc_info=True,
            )
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return router
