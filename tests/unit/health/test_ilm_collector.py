"""Unit tests for ILM collector."""

import unittest
from unittest.mock import MagicMock, patch

from elastro.core.client import ElasticsearchClient
from elastro.health.collectors.base import CollectContext
from elastro.health.collectors.ilm import IlmCollector, _lifecycle_issue, _select_explain_targets


class TestIlmCollector(unittest.TestCase):
    def setUp(self):
        self.mock_es = MagicMock()
        self.mock_client = MagicMock(spec=ElasticsearchClient)
        self.mock_client.client = self.mock_es
        self.ctx = CollectContext(client=self.mock_client)

    def test_select_explain_targets_prefers_unhealthy_indices(self):
        indices = [
            {"index": "logs-000001", "health": "yellow"},
            {"index": "healthy", "health": "green"},
        ]
        targets = _select_explain_targets(indices, health_report=None)
        self.assertEqual(targets, {"logs-000001"})

    def test_lifecycle_issue_detects_error_step(self):
        issue = _lifecycle_issue({"step": "ERROR", "step_info": "snapshot failed"})
        self.assertIn("snapshot failed", issue or "")

    @patch("elastro.health.collectors.ilm.IlmManager")
    @patch("elastro.health.collectors.ilm.IndexManager")
    def test_collect_returns_indices_and_findings(
        self, mock_index_manager_cls, mock_ilm_manager_cls
    ):
        mock_index_manager_cls.return_value.list.return_value = [
            {"index": "logs-000001", "health": "yellow", "rep": "1"}
        ]
        mock_ilm_manager_cls.return_value.explain_lifecycle.return_value = {
            "managed": True,
            "step": "ERROR",
            "step_info": "rollover blocked",
        }

        result = IlmCollector().collect(self.ctx)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.data["index_count"], 1)
        self.assertEqual(len(result.data["findings"]), 1)
        self.assertEqual(result.data["findings"][0].category, "ilm")


if __name__ == "__main__":
    unittest.main()