"""Unit tests for the Health Manager module."""

import unittest
from unittest.mock import Mock, patch, MagicMock

import pytest

from elastro.core.client import ElasticsearchClient
from elastro.core.errors import OperationError
from elastro.utils.health import HealthManager


class TestHealthManager(unittest.TestCase):
    """Test cases for the HealthManager class."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Mock the Elasticsearch client
        self.mock_es = Mock()
        self.mock_client = Mock(spec=ElasticsearchClient)
        self.mock_client.client = self.mock_es

        # Create the HealthManager instance with mocked client
        self.health_manager = HealthManager(self.mock_client)

    def test_cluster_health_default(self):
        """Test getting cluster health with default parameters."""
        # Setup mock response
        expected_result = {
            "cluster_name": "test-cluster",
            "status": "green",
            "timed_out": False,
            "number_of_nodes": 3,
            "number_of_data_nodes": 2,
            "active_primary_shards": 5,
            "active_shards": 10,
        }
        self.mock_es.cluster.health.return_value = expected_result

        # Call the method
        result = self.health_manager.cluster_health()

        # Assertions
        self.mock_es.cluster.health.assert_called_once_with(
            level="cluster", timeout="30s"
        )
        self.assertEqual(result, expected_result)

    def test_cluster_health_with_index(self):
        """Test getting cluster health for a specific index."""
        # Setup mock response
        expected_result = {
            "status": "yellow",
            "timed_out": False,
            "active_primary_shards": 2,
            "active_shards": 4,
        }
        self.mock_es.cluster.health.return_value = expected_result

        # Call the method
        result = self.health_manager.cluster_health(index="test-index")

        # Assertions
        self.mock_es.cluster.health.assert_called_once_with(
            index="test-index", level="cluster", timeout="30s"
        )
        self.assertEqual(result, expected_result)

    def test_cluster_health_error(self):
        """Test error handling when cluster health fails."""
        # Setup mock to raise an exception
        self.mock_es.cluster.health.side_effect = Exception("Connection error")

        # Verify exception is properly wrapped
        with self.assertRaises(OperationError) as context:
            self.health_manager.cluster_health()

        self.assertIn("Failed to get cluster health", str(context.exception))

    def test_node_stats_default(self):
        """Test getting node stats with default parameters."""
        # Setup mock response
        expected_result = {
            "nodes": {
                "node1": {"name": "node-1", "indices": {}},
                "node2": {"name": "node-2", "indices": {}},
            }
        }
        self.mock_es.nodes.stats.return_value = expected_result

        # Call the method
        result = self.health_manager.node_stats()

        # Assertions
        self.mock_es.nodes.stats.assert_called_once_with()
        self.assertEqual(result, expected_result)

    def test_node_stats_with_node_id(self):
        """Test getting node stats for a specific node."""
        # Setup mock response
        expected_result = {"nodes": {"node1": {"name": "node-1", "indices": {}}}}
        self.mock_es.nodes.stats.return_value = expected_result

        # Call the method
        result = self.health_manager.node_stats(node_id="node1")

        # Assertions
        self.mock_es.nodes.stats.assert_called_once_with(node_id="node1")
        self.assertEqual(result, expected_result)

    def test_node_stats_with_metrics(self):
        """Test getting node stats with specific metrics."""
        # Setup mock response
        expected_result = {"nodes": {"node1": {"name": "node-1", "jvm": {}}}}
        self.mock_es.nodes.stats.return_value = expected_result

        # Call the method
        result = self.health_manager.node_stats(metrics=["jvm", "os"])

        # Assertions
        self.mock_es.nodes.stats.assert_called_once_with(metric="jvm,os")
        self.assertEqual(result, expected_result)

    def test_node_stats_with_node_id_and_metrics(self):
        """Test getting node stats with both node ID and metrics."""
        # Setup mock response
        expected_result = {"nodes": {"node1": {"name": "node-1", "jvm": {}, "os": {}}}}
        self.mock_es.nodes.stats.return_value = expected_result

        # Call the method
        result = self.health_manager.node_stats(node_id="node1", metrics=["jvm", "os"])

        # Assertions
        self.mock_es.nodes.stats.assert_called_once_with(
            node_id="node1", metric="jvm,os"
        )
        self.assertEqual(result, expected_result)

    def test_node_stats_error(self):
        """Test error handling when node stats fails."""
        # Setup mock to raise an exception
        self.mock_es.nodes.stats.side_effect = Exception("Node not available")

        # Verify exception is properly wrapped
        with self.assertRaises(OperationError) as context:
            self.health_manager.node_stats()

        self.assertIn("Failed to get node stats", str(context.exception))

    def test_node_info_default(self):
        """Test getting node info with default parameters."""
        # Setup mock response
        expected_result = {
            "nodes": {
                "node1": {"name": "node-1", "version": "7.10.0"},
                "node2": {"name": "node-2", "version": "7.10.0"},
            }
        }
        self.mock_es.nodes.info.return_value = expected_result

        # Call the method
        result = self.health_manager.node_info()

        # Assertions
        self.mock_es.nodes.info.assert_called_once_with()
        self.assertEqual(result, expected_result)

    def test_node_info_with_node_id(self):
        """Test getting node info for a specific node."""
        # Setup mock response
        expected_result = {"nodes": {"node1": {"name": "node-1", "version": "7.10.0"}}}
        self.mock_es.nodes.info.return_value = expected_result

        # Call the method
        result = self.health_manager.node_info(node_id="node1")

        # Assertions
        self.mock_es.nodes.info.assert_called_once_with(node_id="node1")
        self.assertEqual(result, expected_result)

    def test_node_info_with_metrics(self):
        """Test getting node info with specific metrics."""
        # Setup mock response
        expected_result = {"nodes": {"node1": {"name": "node-1", "jvm": {}, "os": {}}}}
        self.mock_es.nodes.info.return_value = expected_result

        # Call the method
        result = self.health_manager.node_info(metrics=["jvm", "os"])

        # Assertions
        self.mock_es.nodes.info.assert_called_once_with(metric="jvm,os")
        self.assertEqual(result, expected_result)

    def test_node_info_with_node_id_and_metrics(self):
        """Test getting node info with both node ID and metrics."""
        # Setup mock response
        expected_result = {"nodes": {"node1": {"name": "node-1", "jvm": {}, "os": {}}}}
        self.mock_es.nodes.info.return_value = expected_result

        # Call the method
        result = self.health_manager.node_info(node_id="node1", metrics=["jvm", "os"])

        # Assertions
        self.mock_es.nodes.info.assert_called_once_with(
            node_id="node1", metric="jvm,os"
        )
        self.assertEqual(result, expected_result)

    def test_node_info_error(self):
        """Test error handling when node info fails."""
        # Setup mock to raise an exception
        self.mock_es.nodes.info.side_effect = Exception("Node not found")

        # Verify exception is properly wrapped
        with self.assertRaises(OperationError) as context:
            self.health_manager.node_info()

        self.assertIn("Failed to get node info", str(context.exception))

    def test_cluster_stats(self):
        """Test getting cluster stats."""
        # Setup mock response
        expected_result = {
            "cluster_name": "test-cluster",
            "indices": {"count": 5},
            "nodes": {"count": {"total": 3}},
        }
        self.mock_es.cluster.stats.return_value = expected_result

        # Call the method
        result = self.health_manager.cluster_stats()

        # Assertions
        self.mock_es.cluster.stats.assert_called_once_with()
        self.assertEqual(result, expected_result)

    def test_cluster_stats_error(self):
        """Test error handling when cluster stats fails."""
        # Setup mock to raise an exception
        self.mock_es.cluster.stats.side_effect = Exception("Cluster stats unavailable")

        # Verify exception is properly wrapped
        with self.assertRaises(OperationError) as context:
            self.health_manager.cluster_stats()

        self.assertIn("Failed to get cluster stats", str(context.exception))

    def test_pending_tasks(self):
        """Test getting pending tasks."""
        # Setup mock response
        expected_result = {
            "tasks": [
                {"source": "create-index", "executing": True},
                {"source": "shard-allocation", "executing": False},
            ]
        }
        self.mock_es.cluster.pending_tasks.return_value = expected_result

        # Call the method
        result = self.health_manager.pending_tasks()

        # Assertions
        self.mock_es.cluster.pending_tasks.assert_called_once_with()
        self.assertEqual(result, expected_result["tasks"])

    def test_pending_tasks_error(self):
        """Test error handling when pending tasks fails."""
        # Setup mock to raise an exception
        self.mock_es.cluster.pending_tasks.side_effect = Exception(
            "Cannot retrieve pending tasks"
        )

        # Verify exception is properly wrapped
        with self.assertRaises(OperationError) as context:
            self.health_manager.pending_tasks()

        self.assertIn("Failed to get pending tasks", str(context.exception))

    def test_allocation_explain_default(self):
        """Test getting allocation explanation with default parameters."""
        # Setup mock response
        expected_result = {
            "index": "test",
            "shard": 0,
            "primary": True,
            "current_state": "started",
        }
        self.mock_es.cluster.allocation_explain.return_value = expected_result

        # Call the method
        result = self.health_manager.allocation_explain()

        # Assertions
        self.mock_es.cluster.allocation_explain.assert_called_once_with()
        self.assertEqual(result, expected_result)

    def test_allocation_explain_with_params(self):
        """Test getting allocation explanation with specific parameters."""
        # Setup mock response
        expected_result = {
            "index": "test-index",
            "shard": 2,
            "primary": True,
            "current_state": "started",
        }
        self.mock_es.cluster.allocation_explain.return_value = expected_result

        # Call the method
        result = self.health_manager.allocation_explain(
            index="test-index", shard=2, primary=True
        )

        # Assertions
        self.mock_es.cluster.allocation_explain.assert_called_once_with(
            body={"index": "test-index", "shard": 2, "primary": True}
        )
        self.assertEqual(result, expected_result)

    def test_allocation_explain_error(self):
        """Test error handling when allocation explain fails."""
        # Setup mock to raise an exception
        self.mock_es.cluster.allocation_explain.side_effect = Exception(
            "Cannot explain allocation"
        )

        # Verify exception is properly wrapped
        with self.assertRaises(OperationError) as context:
            self.health_manager.allocation_explain()

        self.assertIn("Failed to explain allocation", str(context.exception))

    def test_cluster_settings(self):
        """Test getting cluster settings."""
        # Setup mock response
        expected_result = {
            "persistent": {"cluster": {"routing": {"allocation": {"enable": "all"}}}},
            "transient": {},
        }
        self.mock_es.cluster.get_settings.return_value = expected_result

        # Call the method
        result = self.health_manager.cluster_settings()

        # Assertions
        self.mock_es.cluster.get_settings.assert_called_once_with(
            include_defaults=False
        )
        self.assertEqual(result, expected_result)

    def test_cluster_settings_with_defaults(self):
        """Test getting cluster settings with defaults."""
        # Setup mock response
        expected_result = {
            "persistent": {},
            "transient": {},
            "defaults": {"cluster": {"routing": {"allocation": {"enable": "all"}}}},
        }
        self.mock_es.cluster.get_settings.return_value = expected_result

        # Call the method
        result = self.health_manager.cluster_settings(include_defaults=True)

        # Assertions
        self.mock_es.cluster.get_settings.assert_called_once_with(include_defaults=True)
        self.assertEqual(result, expected_result)

    def test_cluster_settings_error(self):
        """Test error handling when getting cluster settings fails."""
        # Setup mock to raise an exception
        self.mock_es.cluster.get_settings.side_effect = Exception("Cannot get settings")

        # Verify exception is properly wrapped
        with self.assertRaises(OperationError) as context:
            self.health_manager.cluster_settings()

        self.assertIn("Failed to get cluster settings", str(context.exception))

    def test_verify_repository_success(self):
        """Test successful repository verification."""
        # Setup mock response
        self.mock_es.snapshot.verify_repository.return_value = {
            "nodes": {"node1": {"name": "node-1"}, "node2": {"name": "node-2"}}
        }

        # Call the method
        result = self.health_manager.verify_repository("test-repo")

        # Assertions
        self.mock_es.snapshot.verify_repository.assert_called_once_with(
            repository="test-repo"
        )
        self.assertTrue(result)

    def test_verify_repository_failure(self):
        """Test error handling for repository verification."""
        # Setup mock to raise an exception
        self.mock_es.snapshot.verify_repository.side_effect = Exception(
            "Repository not found"
        )

        # Verify exception is properly wrapped
        with self.assertRaises(OperationError) as context:
            self.health_manager.verify_repository("test-repo")

        self.assertIn("Failed to verify repository", str(context.exception))

    def test_index_stats_default(self):
        """Test getting index stats with default parameters."""
        # Setup mock response
        expected_result = {
            "_all": {"primaries": {}, "total": {}},
            "indices": {
                "index1": {"primaries": {}, "total": {}},
                "index2": {"primaries": {}, "total": {}},
            },
        }
        self.mock_es.indices.stats.return_value = expected_result

        # Call the method
        result = self.health_manager.index_stats()

        # Assertions
        self.mock_es.indices.stats.assert_called_once_with()
        self.assertEqual(result, expected_result)

    def test_index_stats_with_index(self):
        """Test getting index stats for a specific index."""
        # Setup mock response
        expected_result = {
            "_all": {"primaries": {}, "total": {}},
            "indices": {"test-index": {"primaries": {}, "total": {}}},
        }
        self.mock_es.indices.stats.return_value = expected_result

        # Call the method
        result = self.health_manager.index_stats(index="test-index")

        # Assertions
        self.mock_es.indices.stats.assert_called_once_with(index="test-index")
        self.assertEqual(result, expected_result)

    def test_index_stats_error(self):
        """Test error handling when getting index stats fails."""
        # Setup mock to raise an exception
        self.mock_es.indices.stats.side_effect = Exception("Cannot get index stats")

        # Verify exception is properly wrapped
        with self.assertRaises(OperationError) as context:
            self.health_manager.index_stats()

        self.assertIn("Failed to get index stats", str(context.exception))

    def test_diagnose(self):
        """Test the diagnose method."""
        # Setup mock responses
        self.mock_es.cluster.health.return_value = {"status": "green"}
        self.mock_es.nodes.info.return_value = {"nodes": {"node1": {}, "node2": {}}}
        self.mock_es.indices.get.return_value = {"index1": {}, "index2": {}}

        # For pending_tasks, we need to mock the method on HealthManager
        with patch.object(self.health_manager, "pending_tasks", return_value=[]):
            # Call the method
            result = self.health_manager.diagnose()

            # Assertions
            self.assertEqual(result["cluster_health"]["status"], "green")
            self.assertEqual(result["nodes_count"], 2)
            self.assertEqual(result["indices_count"], 2)
            self.assertEqual(result["pending_tasks"], 0)
            self.assertTrue(result["status"]["is_healthy"])
            self.assertEqual(result["status"]["health_status"], "green")
            self.assertFalse(result["status"]["has_pending_tasks"])

    def test_diagnose_with_yellow_status(self):
        """Test the diagnose method with yellow cluster status."""
        # Setup mock responses
        self.mock_es.cluster.health.return_value = {"status": "yellow"}
        self.mock_es.nodes.info.return_value = {"nodes": {"node1": {}, "node2": {}}}
        self.mock_es.indices.get.return_value = {"index1": {}, "index2": {}}

        # For pending_tasks, we need to mock the method on HealthManager
        with patch.object(self.health_manager, "pending_tasks", return_value=[]):
            # Call the method
            result = self.health_manager.diagnose()

            # Assertions
            self.assertEqual(result["cluster_health"]["status"], "yellow")
            self.assertEqual(result["nodes_count"], 2)
            self.assertEqual(result["indices_count"], 2)
            self.assertEqual(result["pending_tasks"], 0)
            self.assertFalse(result["status"]["is_healthy"])
            self.assertEqual(result["status"]["health_status"], "yellow")
            self.assertFalse(result["status"]["has_pending_tasks"])

    def test_diagnose_with_pending_tasks(self):
        """Test the diagnose method with pending tasks."""
        # Setup mock responses
        self.mock_es.cluster.health.return_value = {"status": "green"}
        self.mock_es.nodes.info.return_value = {"nodes": {"node1": {}, "node2": {}}}
        self.mock_es.indices.get.return_value = {"index1": {}, "index2": {}}

        # For pending_tasks, mock to return some tasks
        with patch.object(
            self.health_manager,
            "pending_tasks",
            return_value=[{"source": "create-index", "executing": True}],
        ):
            # Call the method
            result = self.health_manager.diagnose()

            # Assertions
            self.assertEqual(result["cluster_health"]["status"], "green")
            self.assertEqual(result["pending_tasks"], 1)
            self.assertTrue(result["status"]["is_healthy"])
            self.assertTrue(result["status"]["has_pending_tasks"])

    def test_diagnose_error(self):
        """Test error handling for diagnose method."""
        # Setup one of the called methods to raise an exception
        self.mock_es.cluster.health.side_effect = Exception("Connection refused")

        # Verify exception is properly wrapped
        with self.assertRaises(OperationError) as context:
            self.health_manager.diagnose()

        self.assertIn("Failed to perform diagnostics", str(context.exception))


if __name__ == "__main__":
    unittest.main()
