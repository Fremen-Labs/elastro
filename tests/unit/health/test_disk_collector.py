"""Unit tests for disk collector and watermark findings."""

import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from elastro.core.client import ElasticsearchClient
from elastro.health.collectors.disk import (
    build_node_disk_usages,
    disk_used_percent,
    disk_watermark_findings,
    parse_disk_watermarks,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "health"


class TestDiskWatermarkParsing(unittest.TestCase):
    def test_parse_percent_watermarks(self):
        settings = {
            "defaults": {},
            "persistent": {
                "cluster.routing.allocation.disk.watermark.low": "85%",
                "cluster.routing.allocation.disk.watermark.high": "90%",
                "cluster.routing.allocation.disk.watermark.flood_stage": "95%",
            },
            "transient": {},
        }
        watermarks = parse_disk_watermarks(settings)
        self.assertEqual(watermarks["high"], 90.0)
        self.assertEqual(watermarks["flood_stage"], 95.0)

    def test_disk_used_percent(self):
        used = disk_used_percent(
            {"total": {"total_in_bytes": 100, "available_in_bytes": 10}}
        )
        self.assertEqual(used, 90.0)


class TestDiskFindings(unittest.TestCase):
    def setUp(self):
        payload = json.loads((FIXTURES / "nodes_stats_disk_pressure.json").read_text())
        self.usages = build_node_disk_usages(
            {
                "node-1": {
                    "name": "es-node-1",
                    "fs": payload["nodes"]["node-1"]["fs"],
                },
                "node-2": {
                    "name": "es-node-2",
                    "fs": payload["nodes"]["node-2"]["fs"],
                },
            }
        )

    def test_high_watermark_finding_generated(self):
        findings = disk_watermark_findings(
            self.usages,
            {"low": 85.0, "high": 90.0, "flood_stage": 95.0},
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].category, "disk")
        self.assertIn("es-node-1", findings[0].title)
        self.assertGreaterEqual(findings[0].metadata["used_percent"], 90.0)

    def test_flood_stage_is_critical(self):
        usages = [
            {
                "node_id": "n1",
                "node_name": "hot-node",
                "used_percent": 96.0,
            }
        ]
        findings = disk_watermark_findings(
            usages,
            {"low": 85.0, "high": 90.0, "flood_stage": 95.0},
        )
        self.assertEqual(findings[0].severity.value, "critical")
        self.assertEqual(findings[0].status.value, "fail")


class TestDiskCollectorIntegration(unittest.TestCase):
    @patch("elastro.health.collectors.disk.NodesCollector.collect")
    @patch("elastro.health.collectors.disk.HealthManager")
    def test_collect_emits_findings(self, mock_manager_cls, mock_nodes_collect):
        mock_manager = mock_manager_cls.return_value
        mock_manager.cluster_settings.return_value = {
            "defaults": {
                "cluster.routing.allocation.disk.watermark.high": "90%",
                "cluster.routing.allocation.disk.watermark.flood_stage": "95%",
            },
            "persistent": {},
            "transient": {},
        }

        payload = json.loads((FIXTURES / "nodes_stats_disk_pressure.json").read_text())
        mock_nodes_collect.return_value = Mock(
            status="ok",
            data={
                "nodes": {
                    "node-1": {
                        "name": "es-node-1",
                        "fs": payload["nodes"]["node-1"]["fs"],
                    }
                }
            },
        )

        from elastro.health.collectors.base import CollectContext
        from elastro.health.collectors.disk import DiskCollector

        collector = DiskCollector()
        result = collector.collect(
            CollectContext(client=Mock(spec=ElasticsearchClient))
        )

        self.assertEqual(result.status, "ok")
        self.assertEqual(len(result.data["findings"]), 1)


if __name__ == "__main__":
    unittest.main()
