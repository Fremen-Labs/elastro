"""Health assessment orchestrator."""

from __future__ import annotations

import time
from typing import List, Optional

from elastro.core.client import ElasticsearchClient
from elastro.core.logger import get_logger
from elastro.health.collectors.base import CollectContext, CollectorRegistry
from elastro.health.collectors.cluster import (
    ClusterHealthCollector,
    PendingTasksCollector,
)
from elastro.health.collectors.health_report import (
    HealthReportCollector,
    non_passing_findings,
)
from elastro.health.models import (
    AssessmentReport,
    Finding,
    FindingStatus,
    Severity,
    score_to_status,
)
from elastro.health.scoring import compute_fallback_score, compute_weighted_score

logger = get_logger(__name__)

_DEFAULT_COLLECTORS = [
    HealthReportCollector(),
    ClusterHealthCollector(),
    PendingTasksCollector(),
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
    ) -> AssessmentReport:
        """Run registered collectors and build an assessment report."""
        start = time.monotonic()
        ctx = CollectContext(client=self._client, timeout=timeout)
        ctx.options["verbose_report"] = verbose_report
        if feature:
            ctx.options["feature"] = feature

        try:
            info = self._client.client.info()
            es_version = info.get("version", {}).get("number", "unknown")
        except Exception:
            es_version = "unknown"
        ctx.es_version = es_version

        logger.info("Starting health assessment (es_version=%s)", es_version)
        results = self._registry.run(ctx, names=collectors)

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
        return report


def _build_default_registry() -> CollectorRegistry:
    registry = CollectorRegistry()
    for collector in _DEFAULT_COLLECTORS:
        registry.register(collector)
    return registry