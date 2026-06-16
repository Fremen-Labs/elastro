"""Unit tests for replica misconfiguration rule."""

import unittest

from elastro.health.rules.engine import RuleContext
from elastro.health.rules.replica import (
    count_data_nodes,
    replica_misconfig_findings,
    smart_replica_target,
)


class TestReplicaRule(unittest.TestCase):
    def test_count_data_nodes(self):
        nodes_data = {
            "nodes": {
                "n1": {"roles": ["master", "data"]},
                "n2": {"roles": ["master"]},
                "n3": {"roles": ["data_hot"]},
            }
        }
        self.assertEqual(count_data_nodes(nodes_data), 2)

    def test_smart_replica_target(self):
        self.assertEqual(smart_replica_target(2, 1), 0)
        self.assertEqual(smart_replica_target(3, 3), 2)

    def test_finding_when_replicas_exceed_data_nodes(self):
        ctx = RuleContext(
            collector_data={
                "nodes": {
                    "nodes": {
                        "n1": {"roles": ["data"], "name": "node-1"},
                    }
                },
                "ilm": {
                    "indices": [
                        {"index": "logs-000001", "rep": "1", "health": "yellow"},
                        {"index": "healthy", "rep": "0", "health": "green"},
                    ]
                },
            }
        )
        findings = replica_misconfig_findings(ctx)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].id, "replica.misconfig.logs-000001")
        self.assertEqual(findings[0].metadata["suggested_replicas"], 0)
        self.assertEqual(findings[0].remediation.label, "Reduce replicas to 0")

    def test_skips_system_indices(self):
        ctx = RuleContext(
            collector_data={
                "nodes": {"nodes": {"n1": {"roles": ["data"]}}},
                "ilm": {"indices": [{"index": ".security-7", "rep": "2"}]},
            }
        )
        self.assertEqual(replica_misconfig_findings(ctx), [])


if __name__ == "__main__":
    unittest.main()
