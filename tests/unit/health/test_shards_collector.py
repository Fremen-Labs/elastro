"""Unit tests for shards collector."""

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from elastro.core.client import ElasticsearchClient
from elastro.health.collectors.base import CollectContext
from elastro.health.collectors.shards import ShardsCollector

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "health"


class TestShardsCollector(unittest.TestCase):
    def setUp(self):
        self.rows = json.loads((FIXTURES / "cat_shards_mixed.json").read_text())
        self.mock_es = MagicMock()
        self.mock_es.cat.shards.return_value = self.rows
        self.mock_client = MagicMock(spec=ElasticsearchClient)
        self.mock_client.client = self.mock_es
        self.ctx = CollectContext(client=self.mock_client)

    def test_collect_returns_analysis(self):
        result = ShardsCollector().collect(self.ctx)
        self.assertEqual(result.status, "ok")
        analysis = result.data["analysis"]
        self.assertEqual(analysis["total_shards"], 6)
        self.assertEqual(analysis["oversharded_count"], 4)

    @patch("elastro.health.collectors.shards.IndexManager")
    def test_explain_allocation_for_index(self, mock_index_manager_cls):
        from elastro.health.collectors.shards import explain_allocation

        mock_index_manager_cls.return_value.allocation_explain.return_value = {
            "allocate_explanation": "blocked",
        }
        payload = explain_allocation(self.ctx, index_name="logs-000001")
        self.assertEqual(payload["allocate_explanation"], "blocked")


if __name__ == "__main__":
    unittest.main()
