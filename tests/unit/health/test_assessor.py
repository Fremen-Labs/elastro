"""Unit tests for HealthAssessor."""

import unittest
from unittest.mock import Mock, patch

from elastro.core.client import ElasticsearchClient
from elastro.health.assessor import HealthAssessor
from elastro.health.collectors.base import CollectContext, CollectorRegistry, CollectorResult
from elastro.health.models import FindingStatus


class _StubCollector:
    name = "stub"

    def collect(self, ctx: CollectContext) -> CollectorResult:
        return CollectorResult(
            name=self.name,
            status="ok",
            data={"cluster_name": "custom", "status": "green"},
        )


class TestHealthAssessor(unittest.TestCase):
    def setUp(self):
        self.mock_es = Mock()
        self.mock_es.info.return_value = {"version": {"number": "8.17.2"}}
        self.mock_client = Mock(spec=ElasticsearchClient)
        self.mock_client.client = self.mock_es

    @patch("elastro.health.collectors.cluster.HealthManager")
    def test_run_green_cluster(self, mock_manager_cls):
        manager = mock_manager_cls.return_value
        manager.cluster_health.return_value = {
            "cluster_name": "prod",
            "status": "green",
        }
        manager.pending_tasks.return_value = []

        report = HealthAssessor(self.mock_client).run()

        self.assertEqual(report.cluster_name, "prod")
        self.assertEqual(report.overall_score, 100)
        self.assertEqual(report.overall_status, FindingStatus.PASS)
        self.assertEqual(report.findings, [])
        self.assertIn("cluster_health", report.collectors_run)
        self.assertEqual(report.elasticsearch_version, "8.17.2")

    @patch("elastro.health.collectors.cluster.HealthManager")
    def test_run_yellow_cluster_with_pending_tasks(self, mock_manager_cls):
        manager = mock_manager_cls.return_value
        manager.cluster_health.return_value = {
            "cluster_name": "dev",
            "status": "yellow",
        }
        manager.pending_tasks.return_value = [{"action": "shard-started"}]

        report = HealthAssessor(self.mock_client).run()

        self.assertEqual(report.overall_score, 68)
        self.assertEqual(len(report.findings), 2)
        self.assertIn("cluster.status.yellow", [f.id for f in report.findings])
        self.assertIn("cluster.pending_tasks", [f.id for f in report.findings])

    def test_custom_registry(self):
        registry = CollectorRegistry()
        registry.register(_StubCollector())
        report = HealthAssessor(self.mock_client, registry=registry).run(
            collectors=["stub"]
        )
        self.assertEqual(report.collectors_run, ["stub"])
        self.assertEqual(report.collectors_failed, [])


if __name__ == "__main__":
    unittest.main()