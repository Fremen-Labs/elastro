"""Unit tests for health lint."""

import unittest
from unittest.mock import MagicMock, patch

from elastro.core.client import ElasticsearchClient
from elastro.health.lint import run_lint


class TestHealthLint(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock(spec=ElasticsearchClient)

    @patch("elastro.health.lint.ShardsCollector")
    @patch("elastro.health.lint.MappingsCollector")
    @patch("elastro.health.lint.IndexManager")
    def test_run_lint_settings_detects_zero_replicas(
        self,
        mock_index_manager_cls,
        mock_mappings_collector_cls,
        mock_shards_collector_cls,
    ):
        mock_index_manager_cls.return_value.list.return_value = [
            {
                "index": "logs-000001",
                "health": "yellow",
                "pri": "1",
                "rep": "0",
                "docs.count": "100",
            }
        ]
        mock_index_manager_cls.return_value.get.return_value = {
            "logs-000001": {
                "settings": {
                    "index": {
                        "number_of_replicas": "0",
                        "refresh_interval": "30s",
                    }
                },
                "mappings": {"properties": {"message": {"type": "text"}}},
            }
        }

        findings = run_lint(self.mock_client, categories=["settings"])
        ids = {finding.id for finding in findings}
        self.assertIn("settings.replicas_zero.logs-000001", ids)
        mock_mappings_collector_cls.assert_not_called()
        mock_shards_collector_cls.assert_not_called()

    @patch("elastro.health.lint.ShardsCollector")
    @patch("elastro.health.lint.MappingsCollector")
    def test_run_lint_mappings_uses_mapping_explosion_rule(
        self,
        mock_mappings_collector_cls,
        mock_shards_collector_cls,
    ):
        mock_mappings_collector_cls.return_value.collect.return_value = MagicMock(
            status="ok",
            data={
                "indices": [
                    {
                        "index": "wide-000001",
                        "field_count": 900,
                        "field_limit": 1000,
                        "field_ratio": 0.9,
                    }
                ]
            },
        )

        findings = run_lint(self.mock_client, categories=["mappings"])
        ids = {finding.id for finding in findings}
        self.assertIn("mappings.explosion.wide-000001", ids)
        mock_shards_collector_cls.assert_not_called()

    def test_unknown_category_raises(self):
        with self.assertRaises(Exception):
            run_lint(self.mock_client, categories=["invalid"])


if __name__ == "__main__":
    unittest.main()