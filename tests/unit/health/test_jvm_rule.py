"""Unit tests for JVM heap pressure rule."""

import json
import unittest
from pathlib import Path

from elastro.health.rules.jvm import jvm_heap_used_percent, jvm_pressure_findings

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "health"


class TestJvmPressureRule(unittest.TestCase):
    def setUp(self):
        self.payload = json.loads(
            (FIXTURES / "nodes_stats_disk_pressure.json").read_text()
        )
        self.nodes_data = {
            "nodes": {
                "node-1": {
                    "id": "node-1",
                    "name": "es-node-1",
                    "jvm": self.payload["nodes"]["node-1"]["jvm"],
                },
                "node-2": {
                    "id": "node-2",
                    "name": "es-node-2",
                    "jvm": self.payload["nodes"]["node-2"]["jvm"],
                },
            }
        }

    def test_heap_used_percent_from_mem(self):
        pct = jvm_heap_used_percent(self.nodes_data["nodes"]["node-1"]["jvm"])
        self.assertEqual(pct, 82.0)

    def test_finding_when_heap_above_threshold(self):
        findings = jvm_pressure_findings(self.nodes_data, threshold=75.0)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].category, "jvm")
        self.assertIn("es-node-1", findings[0].summary)

    def test_no_finding_below_threshold(self):
        findings = jvm_pressure_findings(self.nodes_data, threshold=85.0)
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
