"""Health assessment orchestrator."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from elastro.core.client import ElasticsearchClient
from elastro.core.logger import get_logger
from elastro.health.collectors.base import CollectContext, CollectorRegistry
from elastro.health.collectors.cluster import (
    ClusterHealthCollector,
    PendingTasksCollector,
)
from elastro.health.collectors.disk import DiskCollector
from elastro.health.collectors.health_report import (
    HealthReportCollector,
    non_passing_findings,
)
from elastro.health.collectors.nodes import NodesCollector
from elastro.health.collectors.ilm import IlmCollector
from elastro.health.collectors.mappings import MappingsCollector
from elastro.health.collectors.security import SecurityCollector
from elastro.health.collectors.shards import ShardsCollector
from elastro.health.collectors.snapshots import SnapshotsCollector
from elastro.health.rules.engine import RuleContext, RuleEngine
from elastro.health.models import (
    AssessmentReport,
    Finding,
    FindingStatus,
    Severity,
    score_to_status,
)
from elastro.health.audit import HealthAuditLogger
from elastro.health.config import DEFAULT_HISTORY_INDEX
from elastro.health.history import index_assessment
from elastro.health.scoring import compute_fallback_score, compute_weighted_score

logger = get_logger(__name__)

_DEFAULT_COLLECTORS = [
    HealthReportCollector(),
    ClusterHealthCollector(),
    PendingTasksCollector(),
    NodesCollector(),
    DiskCollector(),
    SnapshotsCollector(),
    IlmCollector(),
    ShardsCollector(),
    MappingsCollector(),
    SecurityCollector(),
]


class HealthAssessor:
    """Orchestrates health collectors and produces assessment reports."""

    def __init__(
        self,
        client: ElasticsearchClient,
        registry: Optional[CollectorRegistry] = None,
    ):
        self._client = client
        self._registry = registry or _build_default_registry()

    def run(
        self,
        *,
        timeout: str = "30s",
        collectors: Optional[List[str]] = None,
        verbose_report: bool = True,
        feature: Optional[str] = None,
        assessment_history: Optional[List[Dict[str, Any]]] = None,
        enable_history: bool = False,
        history_index: str = DEFAULT_HISTORY_INDEX,
        profile: str = "default",
        host: Optional[str] = None,
        audit_logger: Optional[HealthAuditLogger] = None,
    ) -> AssessmentReport:
        """Run registered collectors and build an assessment report."""
        start = time.monotonic()
        ctx = CollectContext(client=self._client, timeout=timeout)
        ctx.options["verbose_report"] = verbose_report
        if feature:
            ctx.options["feature"] = feature
        if assessment_history:
            ctx.options["assessment_history"] = assessment_history

        try:
            info = self._client.client.info()
            es_version = info.get("version", {}).get("number", "unknown")
        except Exception:
            es_version = "unknown"
        ctx.es_version = es_version

        logger.info("Starting health assessment (es_version=%s)", es_version)
        results = _run_collectors(self._registry, ctx, names=collectors)

        cluster_name = "unknown"
        overall_score = 0
        findings: List[Finding] = []
        collectors_run: List[str] = []
        collectors_failed: List[str] = []
        raw_health_report: Optional[dict] = None
        used_health_report = False

        for result in results:
            collectors_run.append(result.name)
            if result.status == "skipped":
                if result.name == "health_report":
                    findings.append(
                        Finding(
                            id="health_report.unavailable",
                            category="cluster",
                            title="Health report unavailable",
                            status=FindingStatus.SKIPPED,
                            severity=Severity.LOW,
                            summary=result.error or "Health report collector was skipped.",
                            source="collector",
                        )
                    )
                continue
            if result.status != "ok":
                collectors_failed.append(result.name)
                continue

            if result.name == "health_report":
                report_data = result.data
                raw_health_report = report_data.get("report")
                cluster_name = report_data.get("cluster_name", cluster_name) or cluster_name
                indicators = report_data.get("indicators", {})
                overall_score = compute_weighted_score(indicators)
                findings.extend(non_passing_findings(report_data.get("findings", [])))
                used_health_report = True

            elif result.name == "cluster_health":
                health = result.data
                cluster_name = health.get("cluster_name", cluster_name)
                cluster_health_status = health.get("status", "unknown")
                if not used_health_report:
                    overall_score = compute_fallback_score(cluster_health_status)
                    if cluster_health_status != "green":
                        severity = (
                            Severity.CRITICAL
                            if cluster_health_status == "red"
                            else Severity.HIGH
                        )
                        findings.append(
                            Finding(
                                id=f"cluster.status.{cluster_health_status}",
                                category="cluster",
                                title=f"Cluster status is {cluster_health_status}",
                                status=(
                                    FindingStatus.FAIL
                                    if cluster_health_status == "red"
                                    else FindingStatus.WARN
                                ),
                                severity=severity,
                                score_impact=100 - overall_score,
                                summary=(
                                    f"Cluster '{cluster_name}' reports status "
                                    f"'{cluster_health_status}'."
                                ),
                                source="collector",
                                metadata=health,
                            )
                        )

            elif result.name == "pending_tasks":
                count = result.data.get("count", 0)
                if count > 0:
                    findings.append(
                        Finding(
                            id="cluster.pending_tasks",
                            category="cluster",
                            title="Pending cluster tasks",
                            status=FindingStatus.WARN,
                            severity=Severity.MEDIUM,
                            score_impact=min(count * 2, 10),
                            summary=f"{count} task(s) pending on the cluster master.",
                            source="collector",
                            metadata=result.data,
                        )
                    )
                    overall_score = max(0, overall_score - min(count * 2, 10))

            elif result.name == "ilm":
                ilm_findings = result.data.get("findings", [])
                if ilm_findings:
                    findings.extend(ilm_findings)
                    deduction = sum(
                        getattr(item, "score_impact", 0) for item in ilm_findings
                    )
                    overall_score = max(0, overall_score - deduction)

            elif result.name == "disk":
                disk_findings = result.data.get("findings", [])
                if disk_findings:
                    findings.extend(disk_findings)
                    deduction = sum(
                        getattr(item, "score_impact", 0) for item in disk_findings
                    )
                    overall_score = max(0, overall_score - deduction)

            elif result.name == "snapshots":
                snapshot_findings = result.data.get("findings", [])
                if snapshot_findings:
                    findings.extend(snapshot_findings)
                    deduction = sum(
                        getattr(item, "score_impact", 0) for item in snapshot_findings
                    )
                    overall_score = max(0, overall_score - deduction)

            elif result.name == "security":
                security_findings = result.data.get("findings", [])
                if security_findings:
                    findings.extend(security_findings)
                    deduction = sum(
                        getattr(item, "score_impact", 0) for item in security_findings
                    )
                    overall_score = max(0, overall_score - deduction)

        collector_data = {
            result.name: result.data
            for result in results
            if result.status == "ok"
        }
        rule_ctx = RuleContext(
            cluster_name=cluster_name,
            collector_data=collector_data,
            assessment_history=ctx.options.get("assessment_history", []),
            es_version=es_version,
        )
        rule_findings = RuleEngine().evaluate(rule_ctx)
        if rule_findings:
            findings.extend(rule_findings)
            deduction = sum(item.score_impact for item in rule_findings)
            overall_score = max(0, overall_score - deduction)

        duration_ms = int((time.monotonic() - start) * 1000)
        report = AssessmentReport(
            cluster_name=cluster_name,
            elasticsearch_version=es_version,
            duration_ms=duration_ms,
            overall_score=overall_score,
            overall_status=score_to_status(overall_score),
            findings=findings,
            collectors_run=collectors_run,
            collectors_failed=collectors_failed,
            raw_health_report=raw_health_report,
        )
        logger.info(
            "Health assessment complete: score=%s status=%s findings=%s",
            report.overall_score,
            report.overall_status.value,
            len(report.findings),
        )

        resolved_host = host or _resolve_client_host(self._client)
        auditor = audit_logger or HealthAuditLogger(
            self._client,
            profile=profile,
            host=resolved_host,
        )
        auditor.log_assess(report)

        if enable_history:
            index_assessment(
                self._client,
                report,
                history_index=history_index,
                profile=profile,
                host=resolved_host,
            )

        return report


def _resolve_client_host(client: ElasticsearchClient) -> str:
    hosts = getattr(client, "hosts", None)
    if isinstance(hosts, list) and hosts:
        return str(hosts[0])
    if isinstance(hosts, str):
        return hosts
    return "unknown"


def _build_default_registry() -> CollectorRegistry:
    registry = CollectorRegistry()
    for collector in _DEFAULT_COLLECTORS:
        registry.register(collector)
    return registry


def _run_collectors(
    registry: CollectorRegistry,
    ctx: CollectContext,
    *,
    names: Optional[List[str]] = None,
) -> List:
    """Run collectors sequentially, sharing health report context with later collectors."""
    from elastro.health.collectors.base import CollectorResult

    targets = names if names is not None else registry.list()
    results: List[CollectorResult] = []

    for name in targets:
        collector = registry.get(name)
        if collector is None:
            results.append(
                CollectorResult(
                    name=name,
                    status="skipped",
                    error=f"Unknown collector: {name}",
                )
            )
            continue

        start = time.monotonic()
        try:
            result = collector.collect(ctx)
        except Exception as exc:
            logger.warning(
                "Collector %s failed: %s",
                name,
                exc,
                exc_info=True,
            )
            result = CollectorResult(
                name=name,
                status="error",
                error=str(exc),
                duration_ms=int((time.monotonic() - start) * 1000),
            )
        else:
            if result.duration_ms == 0:
                result.duration_ms = int((time.monotonic() - start) * 1000)

        if result.name == "health_report" and result.status == "ok":
            ctx.options["health_report"] = result.data.get("report")

        results.append(result)

    return results