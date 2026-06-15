"""Health assessment orchestrator."""

from __future__ import annotations

import time
from typing import List, Optional

from elastro.core.client import ElasticsearchClient
from elastro.core.errors import OperationError
from elastro.core.logger import get_logger
from elastro.health.collectors.base import CollectContext, CollectorRegistry
from elastro.health.collectors.cluster import (
    ClusterHealthCollector,
    PendingTasksCollector,
)
from elastro.health.manager import HealthManager
from elastro.health.models import (
    AssessmentReport,
    Finding,
    FindingStatus,
    Severity,
    cluster_status_to_score,
    score_to_status,
)

logger = get_logger(__name__)

_DEFAULT_COLLECTORS = [
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
        self._manager = HealthManager(client)
        self._registry = registry or _build_default_registry()

    def run(
        self,
        *,
        timeout: str = "30s",
        collectors: Optional[List[str]] = None,
    ) -> AssessmentReport:
        """Run registered collectors and build a baseline assessment report."""
        start = time.monotonic()
        ctx = CollectContext(client=self._client, timeout=timeout)

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

        for result in results:
            collectors_run.append(result.name)
            if result.status != "ok":
                collectors_failed.append(result.name)
                continue

            if result.name == "cluster_health":
                health = result.data
                cluster_name = health.get("cluster_name", "unknown")
                status = health.get("status", "unknown")
                overall_score = cluster_status_to_score(status)

                if status != "green":
                    severity = Severity.CRITICAL if status == "red" else Severity.HIGH
                    findings.append(
                        Finding(
                            id=f"cluster.status.{status}",
                            category="cluster",
                            title=f"Cluster status is {status}",
                            status=(
                                FindingStatus.FAIL
                                if status == "red"
                                else FindingStatus.WARN
                            ),
                            severity=severity,
                            score_impact=100 - overall_score,
                            summary=(
                                f"Cluster '{cluster_name}' reports status '{status}'."
                            ),
                            source="collector",
                            metadata=health,
                        )
                    )

            if result.name == "pending_tasks":
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