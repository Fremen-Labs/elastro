"""Unit tests for persistent yellow cluster rule."""

import unittest
from datetime import datetime, timedelta, timezone

from elastro.health.rules.engine import RuleContext
from elastro.health.rules.persistent_yellow import persistent_yellow_findings


class TestPersistentYellowRule(unittest.TestCase):
    def _history(self, *, hours_apart: float, count: int = 3):
        now = datetime.now(timezone.utc)
        records = []
        for offset in range(count):
            assessed_at = now - timedelta(hours=hours_apart * offset)
            records.append(
                {
                    "assessed_at": assessed_at.isoformat(),
                    "overall_status": "warn",
                    "overall_score": 72,
                    "findings": [
                        {
                            "id": "cluster.status.yellow",
                            "status": "warn",
                        }
                    ],
                }
            )
        return records

    def test_emits_when_yellow_persists_beyond_threshold(self):
        ctx = RuleContext(
            cluster_name="docker-cluster",
            collector_data={"cluster_health": {"status": "yellow"}},
            assessment_history=self._history(hours_apart=2, count=3),
        )
        findings = persistent_yellow_findings(ctx, hours_threshold=4)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].id, "cluster.persistent_yellow")

    def test_no_finding_when_cluster_is_green(self):
        ctx = RuleContext(
            collector_data={"cluster_health": {"status": "green"}},
            assessment_history=self._history(hours_apart=2, count=3),
        )
        self.assertEqual(persistent_yellow_findings(ctx), [])

    def test_no_finding_without_enough_history(self):
        ctx = RuleContext(
            collector_data={"cluster_health": {"status": "yellow"}},
            assessment_history=self._history(hours_apart=2, count=1),
        )
        self.assertEqual(persistent_yellow_findings(ctx), [])


if __name__ == "__main__":
    unittest.main()
