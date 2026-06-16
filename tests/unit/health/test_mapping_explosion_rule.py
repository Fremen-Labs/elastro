"""Unit tests for mapping explosion rule."""

import unittest

from elastro.health.rules.engine import RuleContext
from elastro.health.rules.mapping_explosion import mapping_explosion_findings


class TestMappingExplosionRule(unittest.TestCase):
    def test_emits_finding_when_ratio_exceeds_threshold(self):
        ctx = RuleContext(
            collector_data={
                "mappings": {
                    "indices": [
                        {
                            "index": "logs-000001",
                            "field_count": 850,
                            "field_limit": 1000,
                            "field_ratio": 0.85,
                        }
                    ]
                }
            }
        )
        findings = mapping_explosion_findings(ctx)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].id, "mappings.explosion.logs-000001")

    def test_no_findings_below_threshold(self):
        ctx = RuleContext(
            collector_data={
                "mappings": {
                    "indices": [
                        {
                            "index": "logs-000001",
                            "field_count": 100,
                            "field_limit": 1000,
                            "field_ratio": 0.1,
                        }
                    ]
                }
            }
        )
        self.assertEqual(mapping_explosion_findings(ctx), [])


if __name__ == "__main__":
    unittest.main()