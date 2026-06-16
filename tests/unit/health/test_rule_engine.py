"""Unit tests for RuleEngine."""

import unittest

from elastro.health.models import Finding, FindingStatus, Severity
from elastro.health.rules.engine import RuleContext, RuleEngine


class TestRuleEngine(unittest.TestCase):
    def test_evaluates_registered_rules(self):
        def always_warn(ctx: RuleContext):
            return [
                Finding(
                    id="test.warn",
                    category="test",
                    title="Test warning",
                    status=FindingStatus.WARN,
                    severity=Severity.LOW,
                    summary="Synthetic rule finding",
                    source="rule",
                )
            ]

        findings = RuleEngine(rules=[always_warn]).evaluate(RuleContext())
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].id, "test.warn")

    def test_continues_when_rule_raises(self):
        def broken_rule(_ctx: RuleContext):
            raise RuntimeError("rule failed")

        def ok_rule(_ctx: RuleContext):
            return [
                Finding(
                    id="ok.rule",
                    category="test",
                    title="OK",
                    status=FindingStatus.PASS,
                    severity=Severity.INFO,
                    summary="ok",
                    source="rule",
                )
            ]

        findings = RuleEngine(rules=[broken_rule, ok_rule]).evaluate(RuleContext())
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].id, "ok.rule")

    def test_default_rules_include_jvm_replica_and_persistent_yellow(self):
        rule_names = {
            getattr(rule, "__name__", repr(rule))
            for rule in RuleEngine.default_rules()
        }
        self.assertIn("jvm_rule", rule_names)
        self.assertIn("replica_misconfig_findings", rule_names)
        self.assertIn("persistent_yellow_findings", rule_names)
        self.assertIn("oversharding_findings", rule_names)
        self.assertIn("hotspot_findings", rule_names)
        self.assertIn("unassigned_shard_findings", rule_names)
        self.assertIn("circuit_breaker_rule", rule_names)
        self.assertIn("thread_pool_rule", rule_names)
        self.assertIn("backup_policy_findings", rule_names)


if __name__ == "__main__":
    unittest.main()