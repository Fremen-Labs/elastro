"""Unit tests for snapshots collector."""

import unittest
from unittest.mock import Mock, patch

from elastro.core.client import ElasticsearchClient
from elastro.core.errors import OperationError
from elastro.health.collectors.base import CollectContext
from elastro.health.collectors.snapshots import SnapshotsCollector


class TestSnapshotsCollector(unittest.TestCase):
    @patch("elastro.health.collectors.snapshots.SnapshotManager")
    def test_verify_failure_emits_finding(self, mock_manager_cls):
        mock_manager = mock_manager_cls.return_value
        mock_manager.list_repositories.return_value = {"backup": {"type": "fs"}}

        mock_client = Mock(spec=ElasticsearchClient)
        mock_client.client.snapshot.verify_repository.side_effect = Exception(
            "repository unavailable"
        )

        collector = SnapshotsCollector()
        result = collector.collect(CollectContext(client=mock_client))

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.data["count"], 1)
        self.assertEqual(len(result.data["findings"]), 1)
        self.assertEqual(result.data["findings"][0].category, "snapshots")

    @patch("elastro.health.collectors.snapshots.SnapshotManager")
    def test_list_error(self, mock_manager_cls):
        mock_manager_cls.return_value.list_repositories.side_effect = OperationError(
            "forbidden"
        )
        collector = SnapshotsCollector()
        result = collector.collect(
            CollectContext(client=Mock(spec=ElasticsearchClient))
        )
        self.assertEqual(result.status, "error")


if __name__ == "__main__":
    unittest.main()
