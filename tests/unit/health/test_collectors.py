"""Unit tests for health collector registry."""

import unittest
from unittest.mock import Mock

from elastro.core.client import ElasticsearchClient
from elastro.health.collectors.base import (
    CollectContext,
    CollectorRegistry,
    CollectorResult,
)
from elastro.health.collectors.cluster import (
    ClusterHealthCollector,
    PendingTasksCollector,
)


class _FailingCollector:
    name = "failing"

    def collect(self, ctx: CollectContext) -> CollectorResult:
        raise RuntimeError("boom")


class TestCollectorRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = CollectorRegistry()
        self.mock_client = Mock(spec=ElasticsearchClient)
        self.ctx = CollectContext(client=self.mock_client)

    def test_register_and_list(self):
        self.registry.register(ClusterHealthCollector())
        self.registry.register(PendingTasksCollector())
        self.assertEqual(
            self.registry.list(), ["cluster_health", "pending_tasks"]
        )  # registration order, not alphabetical

    def test_duplicate_registration_raises(self):
        self.registry.register(ClusterHealthCollector())
        with self.assertRaises(ValueError):
            self.registry.register(ClusterHealthCollector())

    def test_run_unknown_collector(self):
        results = self.registry.run(self.ctx, names=["missing"])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "skipped")
        self.assertIn("Unknown collector", results[0].error or "")

    def test_run_captures_collector_exception(self):
        self.registry.register(_FailingCollector())
        results = self.registry.run(self.ctx, names=["failing"])
        self.assertEqual(results[0].status, "error")
        self.assertEqual(results[0].error, "boom")


class TestClusterHealthCollector(unittest.TestCase):
    def test_collect_success(self):
        mock_es = Mock()
        mock_es.cluster.health.return_value = {
            "cluster_name": "test",
            "status": "green",
        }
        mock_client = Mock(spec=ElasticsearchClient)
        mock_client.client = mock_es

        collector = ClusterHealthCollector()
        result = collector.collect(CollectContext(client=mock_client))

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.data["status"], "green")
        mock_es.cluster.health.assert_called_once_with(level="cluster", timeout="30s")


if __name__ == "__main__":
    unittest.main()