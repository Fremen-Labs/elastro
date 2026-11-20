"""Unit tests for HealthAssessor."""

import json
import unittest
from pathlib import Path
from unittest.mock import Mock

from elastro.core.client import ElasticsearchClient
from elastro.health.assessor import HealthAssessor
from elastro.health.collectors.base import (
    CollectContext,
    CollectorRegistry,
    CollectorResult,
)
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

            report_out = HealthAssessor(self.mock_client, registry=registry).run()

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

    def test_run_records_failed_collector_and_keeps_sibling(self):
        class _BoomCollector:
            name = "boom"

            def collect(self, ctx: CollectContext) -> CollectorResult:
                raise RuntimeError("boom")

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
        registry.register(_BoomCollector())
        registry.register(_DiskStub())
        report = HealthAssessor(self.mock_client, registry=registry).run()
        self.assertEqual(report.collectors_run, ["boom", "disk"])
        self.assertEqual(report.collectors_failed, ["boom"])
        self.assertEqual(len(report.findings), 1)
        self.assertEqual(report.findings[0].category, "disk")

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

    def test_run_applies_rule_engine_findings(self):
        class _NodesStub:
            name = "nodes"

            def collect(self, ctx: CollectContext) -> CollectorResult:
                from elastro.health.models import Finding, Severity

                return CollectorResult(
                    name=self.name,
                    status="ok",
                    data={
                        "nodes": {
                            "n1": {
                                "name": "es-node-1",
                                "roles": ["data"],
                                "jvm": {"mem": {"heap_used_percent": 88}},
                            }
                        }
                    },
                )

        class _IlmStub:
            name = "ilm"

            def collect(self, ctx: CollectContext) -> CollectorResult:
                return CollectorResult(
                    name=self.name,
                    status="ok",
                    data={"indices": [], "findings": []},
                )

        registry = CollectorRegistry()
        registry.register(_NodesStub())
        registry.register(_IlmStub())
        report = HealthAssessor(self.mock_client, registry=registry).run(
            collectors=["nodes", "ilm"]
        )
        rule_ids = {finding.id for finding in report.findings}
        self.assertIn("jvm.heap_pressure.es-node-1", rule_ids)

    def test_custom_feature_apm_not_forwarded_and_filters_findings(self):
        from elastro.health.models import Finding, Severity

        class _CaptureCollector:
            name = "health_report"
            feature = "unset"

            def collect(self, ctx: CollectContext) -> CollectorResult:
                _CaptureCollector.feature = ctx.options.get("feature")
                return CollectorResult(
                    name=self.name,
                    status="ok",
                    data={
                        "report": {},
                        "findings": [],
                        "cluster_name": "c",
                        "status": "green",
                        "indicators": {},
                    },
                )

        registry = CollectorRegistry()
        registry.register(_CaptureCollector())
        with unittest.mock.patch("elastro.health.assessor.RuleEngine") as engine:
            engine.return_value.evaluate.return_value = [
                Finding(
                    id="apm.datastream.missing",
                    category="apm",
                    title="missing",
                    status=FindingStatus.FAIL,
                    severity=Severity.HIGH,
                    score_impact=15,
                    summary="missing",
                    source="rule",
                    indicator="apm",
                ),
                Finding(
                    id="jvm.heap_pressure.n1",
                    category="jvm",
                    title="heap",
                    status=FindingStatus.WARN,
                    severity=Severity.HIGH,
                    score_impact=5,
                    summary="heap",
                    source="rule",
                ),
            ]
            report = HealthAssessor(self.mock_client, registry=registry).run(
                feature="apm"
            )
        self.assertIsNone(_CaptureCollector.feature)
        ids = {item.id for item in report.findings}
        self.assertEqual(ids, {"apm.datastream.missing"})

    def test_feature_disk_still_forwarded(self):
        class _CaptureCollector:
            name = "health_report"
            feature = "unset"

            def collect(self, ctx: CollectContext) -> CollectorResult:
                _CaptureCollector.feature = ctx.options.get("feature")
                return CollectorResult(
                    name=self.name,
                    status="ok",
                    data={
                        "report": {},
                        "findings": [],
                        "cluster_name": "c",
                        "status": "green",
                        "indicators": {},
                    },
                )

        registry = CollectorRegistry()
        registry.register(_CaptureCollector())
        with unittest.mock.patch("elastro.health.assessor.RuleEngine") as engine:
            engine.return_value.evaluate.return_value = []
            HealthAssessor(self.mock_client, registry=registry).run(feature="disk")
        self.assertEqual(_CaptureCollector.feature, "disk")

    def test_missing_apm_is_skipped_on_default_assess(self):
        class _ApmStub:
            name = "apm_beats"

            def collect(self, ctx: CollectContext) -> CollectorResult:
                return CollectorResult(
                    name=self.name,
                    status="ok",
                    data={"indices": [], "data_streams": []},
                )

        registry = CollectorRegistry()
        registry.register(_ApmStub())
        report = HealthAssessor(self.mock_client, registry=registry).run()
        missing = [
            item for item in report.findings if item.id == "apm.datastream.missing"
        ]
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0].status, FindingStatus.SKIPPED)

    def test_missing_apm_fails_when_feature_apm(self):
        class _ApmStub:
            name = "apm_beats"

            def collect(self, ctx: CollectContext) -> CollectorResult:
                return CollectorResult(
                    name=self.name,
                    status="ok",
                    data={"indices": [], "data_streams": []},
                )

        registry = CollectorRegistry()
        registry.register(_ApmStub())
        report = HealthAssessor(self.mock_client, registry=registry).run(feature="apm")
        missing = [
            item for item in report.findings if item.id == "apm.datastream.missing"
        ]
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0].status, FindingStatus.FAIL)

    def test_feature_disk_excludes_security_and_cluster_blocks(self):
        from elastro.health.models import Finding, Severity

        class _CaptureCollector:
            name = "health_report"
            feature = "unset"

            def collect(self, ctx: CollectContext) -> CollectorResult:
                _CaptureCollector.feature = ctx.options.get("feature")
                return CollectorResult(
                    name=self.name,
                    status="ok",
                    data={
                        "report": {},
                        "findings": [],
                        "cluster_name": "c",
                        "status": "green",
                        "indicators": {},
                    },
                )

        class _DiskStub:
            name = "disk"

            def collect(self, ctx: CollectContext) -> CollectorResult:
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
        registry.register(_CaptureCollector())
        registry.register(_DiskStub())
        with unittest.mock.patch("elastro.health.assessor.RuleEngine") as engine:
            engine.return_value.evaluate.return_value = [
                Finding(
                    id="security.tls.plain_http",
                    category="security",
                    title="plain http",
                    status=FindingStatus.WARN,
                    severity=Severity.HIGH,
                    score_impact=10,
                    summary="http",
                    source="collector",
                ),
                Finding(
                    id="cluster.block.indices",
                    category="cluster",
                    title="block",
                    status=FindingStatus.FAIL,
                    severity=Severity.CRITICAL,
                    score_impact=12,
                    summary="block",
                    source="rule",
                ),
            ]
            report = HealthAssessor(self.mock_client, registry=registry).run(
                feature="disk"
            )
        self.assertEqual(_CaptureCollector.feature, "disk")
        ids = {item.id for item in report.findings}
        self.assertEqual(ids, {"disk.high.node-a"})
        self.assertEqual(report.overall_score, 92)

    def test_feature_apm_keeps_cluster_fail_findings(self):
        from elastro.health.models import Finding, Severity

        class _CaptureCollector:
            name = "health_report"

            def collect(self, ctx: CollectContext) -> CollectorResult:
                return CollectorResult(
                    name=self.name,
                    status="ok",
                    data={
                        "report": {},
                        "findings": [],
                        "cluster_name": "c",
                        "status": "green",
                        "indicators": {},
                    },
                )

        registry = CollectorRegistry()
        registry.register(_CaptureCollector())
        with unittest.mock.patch("elastro.health.assessor.RuleEngine") as engine:
            engine.return_value.evaluate.return_value = [
                Finding(
                    id="apm.datastream.missing",
                    category="apm",
                    title="missing",
                    status=FindingStatus.FAIL,
                    severity=Severity.HIGH,
                    score_impact=15,
                    summary="missing",
                    source="rule",
                    indicator="apm",
                ),
                Finding(
                    id="cluster.block.indices",
                    category="cluster",
                    title="block",
                    status=FindingStatus.FAIL,
                    severity=Severity.CRITICAL,
                    score_impact=12,
                    summary="block",
                    source="rule",
                ),
                Finding(
                    id="jvm.heap_pressure.n1",
                    category="jvm",
                    title="heap",
                    status=FindingStatus.WARN,
                    severity=Severity.HIGH,
                    score_impact=5,
                    summary="heap",
                    source="rule",
                ),
            ]
            report = HealthAssessor(self.mock_client, registry=registry).run(
                feature="apm"
            )
        ids = {item.id for item in report.findings}
        self.assertEqual(ids, {"apm.datastream.missing", "cluster.block.indices"})
        self.assertEqual(report.overall_score, 73)


if __name__ == "__main__":
    unittest.main()
