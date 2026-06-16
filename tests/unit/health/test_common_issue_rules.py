"""Unit tests for common Elasticsearch operational issue rules."""

import unittest

from elastro.health.rules.backup_policy import backup_policy_findings
from elastro.health.rules.circuit_breaker import circuit_breaker_findings
from elastro.health.rules.cluster_blocks import cluster_block_findings
from elastro.health.rules.cluster_capacity import shard_limit_findings
from elastro.health.rules.cpu_pressure import cpu_pressure_findings
from elastro.health.rules.engine import RuleContext
from elastro.health.rules.master_topology import master_topology_findings
from elastro.health.rules.shards_unassigned import unassigned_shard_findings
from elastro.health.rules.thread_pool import thread_pool_findings


class TestCommonIssueRules(unittest.TestCase):
    def test_unassigned_shards_from_analysis(self):
        ctx = RuleContext(
            collector_data={
                "shards": {"analysis": {"unassigned_count": 3}},
            }
        )
        findings = unassigned_shard_findings(ctx)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].id, "shards.unassigned")

    def test_circuit_breaker_tripped(self):
        nodes_data = {
            "nodes": {
                "n1": {
                    "name": "node-1",
                    "breakers": {
                        "request": {
                            "tripped": True,
                            "estimated_size_in_bytes": 900,
                            "limit_size_in_bytes": 1000,
                        }
                    },
                }
            }
        }
        findings = circuit_breaker_findings(nodes_data)
        self.assertEqual(len(findings), 1)
        self.assertIn("circuit_breaker", findings[0].id)

    def test_thread_pool_rejections(self):
        nodes_data = {
            "nodes": {
                "n1": {
                    "name": "node-1",
                    "thread_pool": {"write": {"rejected": 42, "active": 4, "queue": 0}},
                }
            }
        }
        findings = thread_pool_findings(nodes_data)
        self.assertEqual(findings[0].id, "nodes.thread_pool_rejected.write.node-1")

    def test_shard_limit_pressure(self):
        ctx = RuleContext(
            collector_data={
                "shards": {"analysis": {"total_shards": 900}},
                "nodes": {
                    "node_count": 1,
                    "nodes": {"n1": {"roles": ["data"]}},
                },
                "cluster_settings": {
                    "defaults": {"cluster.max_shards_per_node": "1000"},
                },
            }
        )
        findings = shard_limit_findings(ctx)
        self.assertEqual(findings[0].id, "cluster.shard_limit_pressure")

    def test_skips_backup_when_snapshots_collector_missing(self):
        self.assertEqual(backup_policy_findings(RuleContext()), [])

    def test_no_snapshot_repositories(self):
        ctx = RuleContext(collector_data={"snapshots": {"count": 0}})
        findings = backup_policy_findings(ctx)
        self.assertEqual(findings[0].id, "snapshots.not_configured")

    def test_cpu_pressure(self):
        nodes_data = {
            "nodes": {
                "n1": {"name": "hot-node", "os": {"cpu": {"percent": 92}}},
            }
        }
        findings = cpu_pressure_findings(nodes_data, threshold=85.0)
        self.assertEqual(findings[0].id, "nodes.cpu_pressure.hot-node")

    def test_master_eligible_low(self):
        ctx = RuleContext(
            collector_data={
                "nodes": {
                    "node_count": 5,
                    "nodes": {
                        "n1": {"roles": ["master", "data"]},
                        "n2": {"roles": ["data"]},
                        "n3": {"roles": ["data"]},
                        "n4": {"roles": ["data"]},
                        "n5": {"roles": ["data"]},
                    },
                }
            }
        )
        findings = master_topology_findings(ctx)
        self.assertEqual(findings[0].id, "cluster.master_eligible_low")

    def test_cluster_read_only_block(self):
        ctx = RuleContext(
            collector_data={
                "cluster_health": {
                    "blocks": {
                        "read_only_allow_delete": {
                            "description": "disk usage exceeded flood-stage watermark",
                        }
                    }
                }
            }
        )
        findings = cluster_block_findings(ctx)
        self.assertEqual(findings[0].id, "cluster.block.read_only_allow_delete")


if __name__ == "__main__":
    unittest.main()