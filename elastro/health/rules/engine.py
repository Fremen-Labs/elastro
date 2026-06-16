"""Rule evaluation engine for custom health checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from elastro.core.logger import get_logger
from elastro.health.models import Finding

logger = get_logger(__name__)

RuleFn = Callable[["RuleContext"], List[Finding]]


@dataclass
class RuleContext:
    """Inputs gathered by collectors for custom rule evaluation."""

    cluster_name: str = "unknown"
    collector_data: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    assessment_history: List[Dict[str, Any]] = field(default_factory=list)
    es_version: Optional[str] = None


class RuleEngine:
    """Evaluate registered health rules against collector output."""

    def __init__(self, rules: Optional[List[RuleFn]] = None) -> None:
        self._rules = rules if rules is not None else self.default_rules()

    @classmethod
    def default_rules(cls) -> List[RuleFn]:
        from elastro.health.rules.backup_policy import backup_policy_findings
        from elastro.health.rules.circuit_breaker import circuit_breaker_rule
        from elastro.health.rules.cluster_blocks import cluster_block_findings
        from elastro.health.rules.cluster_capacity import shard_limit_rule
        from elastro.health.rules.cpu_pressure import cpu_pressure_rule
        from elastro.health.rules.hotspots import hotspot_findings
        from elastro.health.rules.jvm import jvm_rule
        from elastro.health.rules.mapping_explosion import mapping_explosion_findings
        from elastro.health.rules.master_topology import master_topology_findings
        from elastro.health.rules.oversharding import oversharding_findings
        from elastro.health.rules.persistent_yellow import persistent_yellow_findings
        from elastro.health.rules.replica import replica_misconfig_findings
        from elastro.health.rules.shards_unassigned import unassigned_shard_findings
        from elastro.health.rules.thread_pool import thread_pool_rule

        return [
            cluster_block_findings,
            master_topology_findings,
            unassigned_shard_findings,
            shard_limit_rule,
            backup_policy_findings,
            jvm_rule,
            circuit_breaker_rule,
            cpu_pressure_rule,
            thread_pool_rule,
            replica_misconfig_findings,
            persistent_yellow_findings,
            oversharding_findings,
            hotspot_findings,
            mapping_explosion_findings,
        ]

    def evaluate(self, ctx: RuleContext) -> List[Finding]:
        """Run all rules and return merged findings."""
        findings: List[Finding] = []
        for rule in self._rules:
            rule_name = getattr(rule, "__name__", repr(rule))
            try:
                emitted = rule(ctx)
            except Exception as exc:
                logger.warning(
                    "Health rule %s failed: %s",
                    rule_name,
                    exc,
                    exc_info=True,
                )
                continue
            if emitted:
                logger.debug(
                    "Rule %s emitted %s finding(s)",
                    rule_name,
                    len(emitted),
                )
                findings.extend(emitted)
        return findings