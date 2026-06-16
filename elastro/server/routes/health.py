"""Health assessment routes — /api/clusters/{name}/health/* endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from elastro.core.logger import get_logger
from elastro.health.assessor import HealthAssessor
from elastro.health.collectors.nodes import NodesCollector
from elastro.health.collectors.base import CollectContext
from elastro.health.models import AssessmentReport, FindingStatus
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
        finding
        for finding in report.findings
        if finding.status in open_statuses
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
    *,
    verbose: bool = True,
    features: Optional[List[str]] = None,
    timeout: str = "30s",
) -> AssessmentReport:
    client = build_es_client(target)
    assessor = HealthAssessor(client)
    feature = features[0] if features else None
    report = assessor.run(
        timeout=timeout,
        verbose_report=verbose,
        feature=feature,
        assessment_history=get_history(cluster_name, limit=20),
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
                report = _run_assessment(cluster_name, target)
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
        _find_cluster(read_config, cluster_name)
        return {
            "cluster_name": cluster_name,
            "assessments": get_history(cluster_name, limit=limit),
        }

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
            client = build_es_client(target)
            executor = RemediationExecutor(
                client,
                dry_run=req.dry_run,
                interactive=False,
                api_mode=True,
            )
            result = executor.execute_action(action, index_name)
            if result.dry_run:
                return {
                    "status": "dry_run",
                    "action": action,
                    "index_name": index_name,
                    "planned_api_call": result.planned_api_call,
                    "message": result.message,
                }
            if not result.success:
                raise HTTPException(status_code=500, detail=result.message)
            return {
                "status": "success",
                "action": action,
                "index_name": index_name,
                "message": result.message,
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