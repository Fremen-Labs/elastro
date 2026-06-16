"""Unit tests for node hotspot variance rule."""

import unittest

from elastro.health.rules.engine import RuleContext
from elastro.health.rules.hotspots import hotspot_findings, hotspot_variance


class TestHotspotsRule(unittest.TestCase):
    def test_detects_heap_hotspot(self):
        nodes_data = {
            "nodes": {
                "n1": {
                    "name": "hot-node",
                    "jvm": {"mem": {"heap_used_percent": 92}},
                    "fs": {
                        "total": {
                            "total_in_bytes": 1000,
                            "available_in_bytes": 500,
                        }
                    },
                    "os": {"cpu": {"percent": 20}},
                },
                "n2": {
                    "name": "cool-node",
                    "jvm": {"mem": {"heap_used_percent": 45}},
                    "fs": {
                        "total": {
                            "total_in_bytes": 1000,
                            "available_in_bytes": 900,
                        }
                    },
                    "os": {"cpu": {"percent": 18}},
                },
            }
        }
        hotspots = hotspot_variance(nodes_data, variance_threshold=30)
        metrics = {row["metric"] for row in hotspots}
        self.assertIn("heap_used_percent", metrics)

    def test_finding_emitted_for_hotspot(self):
        ctx = RuleContext(
            collector_data={
                "nodes": {
                    "nodes": {
                        "n1": {
                            "name": "hot-node",
                            "jvm": {"mem": {"heap_used_percent": 95}},
                            "fs": {
                                "total": {
                                    "total_in_bytes": 1000,
                                    "available_in_bytes": 500,
                                }
                            },
                        },
                        "n2": {
                            "name": "cool-node",
                            "jvm": {"mem": {"heap_used_percent": 40}},
                            "fs": {
                                "total": {
                                    "total_in_bytes": 1000,
                                    "available_in_bytes": 900,
                                }
                            },
                        },
                    }
                }
            }
        )
        findings = hotspot_findings(ctx, variance_threshold=30)
        ids = {finding.id for finding in findings}
        self.assertIn("nodes.hotspot.heap_used_percent", ids)
        self.assertGreaterEqual(len(findings), 1)


if __name__ == "__main__":
    unittest.main()