"""Unit tests for HealthAssessor."""

import json
import unittest
from pathlib import Path
from unittest.mock import Mock

from elastro.core.client import ElasticsearchClient
from elastro.health.assessor import HealthAssessor
from elastro.health.collectors.base import CollectContext, CollectorRegistry, CollectorResult
from elastro.health.collectors.cluster import (
    ClusterHealthCollector,
    PendingTasksCollector,
)
from elastro.health.collectors.health_report import map_indicators
from elastro.health.models import FindingStatus

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "health"


class _HealthReportStub:
    name = "health_report"

    def __init__(self, report: dict):
        self._report = report

    def collect(self, ctx: CollectContext) -> CollectorResult:
        findings = map_indicators(self._report)
        return CollectorResult(
            name=self.name,
            status="ok",
            data={
                "report": self._report,
                "findings": findings,
                "cluster_name": self._report["cluster_name"],
                "status": self._report["status"],
                "indicators": self._report["indicators"],
            },
        )


class TestHealthAssessor(unittest.TestCase):
    def setUp(self):
        self.mock_es = Mock()
        self.mock_es.info.return_value = {"version": {"number": "8.15.2"}}
        self.mock_client = Mock(spec=ElasticsearchClient)
        self.mock_client.client = self.mock_es

    def _registry_with_report(self, report: dict) -> CollectorRegistry:
        registry = CollectorRegistry()
        registry.register(_HealthReportStub(report))
        registry.register(ClusterHealthCollector())
        registry.register(PendingTasksCollector())
        return registry

    def test_run_uses_health_report_score(self):
        with open(
            FIXTURES / "health_report_shards_yellow.json", encoding="utf-8"
        ) as handle:
            report = json.load(handle)

        with unittest.mock.patch(
            "elastro.health.collectors.cluster.HealthManager"
        ) as mock_manager_cls:
            manager = mock_manager_cls.return_value
            manager.cluster_health.return_value = {
                "cluster_name": "docker-cluster",
                "status": "yellow",
            }
            manager.pending_tasks.return_value = []

            report_out = HealthAssessor(
                self.mock_client,
                registry=self._registry_with_report(report),
            ).run()

        self.assertEqual(report_out.cluster_name, "docker-cluster")
        self.assertGreater(report_out.overall_score, 50)
        self.assertLess(report_out.overall_score, 100)
        self.assertEqual(len(report_out.findings), 1)
        self.assertEqual(report_out.findings[0].indicator, "shards_availability")
        self.assertIsNotNone(report_out.raw_health_report)

    def test_run_falls_back_when_health_report_skipped(self):
        class _SkippedCollector:
            name = "health_report"

            def collect(self, ctx: CollectContext) -> CollectorResult:
                return CollectorResult(
                    name=self.name, status="skipped", error="requires 8.7+"
                )

        registry = CollectorRegistry()
        registry.register(_SkippedCollector())
        registry.register(ClusterHealthCollector())
        registry.register(PendingTasksCollector())

        with unittest.mock.patch(
            "elastro.health.collectors.cluster.HealthManager"
        ) as mock_manager_cls:
            manager = mock_manager_cls.return_value
            manager.cluster_health.return_value = {
                "cluster_name": "legacy",
                "status": "green",
            }
            manager.pending_tasks.return_value = []

            report_out = HealthAssessor(
                self.mock_client, registry=registry
            ).run()

        self.assertEqual(report_out.overall_score, 100)
        self.assertEqual(len(report_out.findings), 1)
        self.assertEqual(report_out.findings[0].id, "health_report.unavailable")
        self.assertIsNone(report_out.raw_health_report)

    def test_custom_registry_minimal(self):
        class _StubCollector:
            name = "stub"

            def collect(self, ctx: CollectContext) -> CollectorResult:
                return CollectorResult(name=self.name, status="ok", data={})

        registry = CollectorRegistry()
        registry.register(_StubCollector())
        report = HealthAssessor(self.mock_client, registry=registry).run(
            collectors=["stub"]
        )
        self.assertEqual(report.collectors_run, ["stub"])
        self.assertEqual(report.collectors_failed, [])

    def test_run_includes_disk_collector_findings(self):
        class _DiskStub:
            name = "disk"

            def collect(self, ctx: CollectContext) -> CollectorResult:
                from elastro.health.models import Finding, Severity

                finding = Finding(
                    id="disk.high.node-a",
                    category="disk",
                    title="Disk high watermark on node-a",
                    status=FindingStatus.WARN,
                    severity=Severity.HIGH,
                    score_impact=8,
                    summary="Node disk usage is 92%",
                    source="collector",
                )
                return CollectorResult(
                    name=self.name,
                    status="ok",
                    data={"findings": [finding], "nodes": []},
                )

        registry = CollectorRegistry()
        registry.register(_DiskStub())
        report = HealthAssessor(self.mock_client, registry=registry).run(
            collectors=["disk"]
        )
        self.assertEqual(len(report.findings), 1)
        self.assertEqual(report.findings[0].category, "disk")
        self.assertLess(report.overall_score, 100)


if __name__ == "__main__":
    unittest.main()