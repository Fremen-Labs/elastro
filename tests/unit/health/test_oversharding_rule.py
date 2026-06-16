"""Unit tests for oversharding rule."""

import unittest

from elastro.health.rules.engine import RuleContext
from elastro.health.rules.oversharding import oversharding_findings


class TestOvershardingRule(unittest.TestCase):
    def test_emits_findings_for_mis_sized_shards(self):
        ctx = RuleContext(
            collector_data={
                "shards": {
                    "analysis": {
                        "oversharded_count": 12,
                        "undersharded_count": 2,
                        "avg_bytes": 1024 * 1024,
                        "overshard_threshold_bytes": 1024 * 1024,
                        "undershard_threshold_bytes": 50 * 1024**3,
                    }
                }
            }
        )
        findings = oversharding_findings(ctx)
        ids = {finding.id for finding in findings}
        self.assertIn("shards.oversharded", ids)
        self.assertIn("shards.undersharded", ids)

    def test_no_findings_without_analysis(self):
        self.assertEqual(oversharding_findings(RuleContext()), [])


if __name__ == "__main__":
    unittest.main()