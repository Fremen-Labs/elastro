"""Unit tests for nodes collector and table formatter."""

import unittest
from unittest.mock import Mock, patch

from elastro.core.client import ElasticsearchClient
from elastro.core.errors import OperationError
from elastro.health.collectors.base import CollectContext
from elastro.health.collectors.nodes import NodesCollector
from elastro.health.formatters.nodes_table import format_nodes_table


class TestNodesCollector(unittest.TestCase):
    def test_collect_merges_stats_and_info(self):
        mock_es = Mock()
        mock_client = Mock(spec=ElasticsearchClient)
        mock_client.client = mock_es

        mock_manager = Mock()
        mock_manager.node_stats.return_value = {
            "nodes": {
                "abc": {
                    "name": "node-a",
                    "jvm": {"mem": {"heap_used_percent": 70}},
                    "fs": {
                        "total": {
                            "total_in_bytes": 1000,
                            "available_in_bytes": 400,
                        }
                    },
                }
            }
        }
        mock_manager.node_info.return_value = {
            "nodes": {"abc": {"roles": ["data", "ingest"]}}
        }

        collector = NodesCollector()
        with patch(
            "elastro.health.collectors.nodes.HealthManager",
            return_value=mock_manager,
        ):
            result = collector.collect(
                CollectContext(
                    client=mock_client,
                    options={"metrics": "jvm,fs"},
                )
            )

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.data["node_count"], 1)
        node = result.data["nodes"]["abc"]
        self.assertEqual(node["roles"], ["data", "ingest"])
        mock_manager.node_stats.assert_called_once_with(
            node_id=None,
            metrics=["jvm", "fs"],
        )

    def test_collect_error(self):
        mock_manager = Mock()
        mock_manager.node_stats.side_effect = OperationError("nodes down")

        collector = NodesCollector()
        with patch(
            "elastro.health.collectors.nodes.HealthManager",
            return_value=mock_manager,
        ):
            result = collector.collect(
                CollectContext(client=Mock(spec=ElasticsearchClient))
            )

        self.assertEqual(result.status, "error")


class TestNodesTableFormatter(unittest.TestCase):
    def test_table_includes_requested_metrics(self):
        nodes = {
            "n1": {
                "id": "n1",
                "name": "node-a",
                "roles": ["data"],
                "jvm": {"mem": {"heap_used_percent": 72, "heap_used_in_bytes": 720}},
                "fs": {
                    "total": {
                        "total_in_bytes": 1000,
                        "available_in_bytes": 250,
                    }
                },
            }
        }
        output = format_nodes_table(nodes, ["jvm", "fs"])
        self.assertIn("Node Health", output)
        self.assertIn("node-a", output)
        self.assertIn("72", output)


if __name__ == "__main__":
    unittest.main()
