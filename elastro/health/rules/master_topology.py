"""Master-eligible node topology checks."""

from __future__ import annotations

from typing import Dict, List

from elastro.core.logger import get_logger
from elastro.health.models import Finding, FindingStatus, Severity
from elastro.health.rules.engine import RuleContext

logger = get_logger(__name__)

RECOMMENDED_MIN_MASTER_ELIGIBLE = 3


def _master_eligible_count(nodes_data: Dict[str, object]) -> int:
    nodes = nodes_data.get("nodes") or {}
    count = 0
    for node in nodes.values():
        if not isinstance(node, dict):
            continue
        roles = node.get("roles") or []
        if "master" in roles:
            count += 1
    return count


def master_topology_findings(ctx: RuleContext) -> List[Finding]:
    """Warn when master-eligible node count risks split-brain or no quorum."""
    nodes_data = ctx.collector_data.get("nodes") or {}
    total_nodes = int(nodes_data.get("node_count", 0) or 0)
    if total_nodes <= 0:
        return []

    master_eligible = _master_eligible_count(nodes_data)
    findings: List[Finding] = []

    if master_eligible == 0:
        logger.warning("No master-eligible nodes detected cluster=%s", ctx.cluster_name)
        findings.append(
            Finding(
                id="cluster.master_eligible_missing",
                category="cluster",
                title="No master-eligible nodes detected",
                status=FindingStatus.FAIL,
                severity=Severity.CRITICAL,
                score_impact=15,
                summary=(
                    "No nodes report the master role. The cluster cannot elect "
                    "a master and will reject cluster-state updates."
                ),
                detail=(
                    "Every production cluster needs dedicated or mixed master-eligible nodes.\n\n"
                    "How to resolve:\n"
                    "  1. Ensure node.roles includes 'master' on at least 3 nodes\n"
                    "  2. Check discovery.seed_hosts and cluster.initial_master_nodes\n"
                    "  3. Review master_is_stable indicator in health assess output"
                ),
                source="rule",
                metadata={
                    "master_eligible": 0,
                    "total_nodes": total_nodes,
                },
            )
        )
        return findings

    if total_nodes >= 3 and master_eligible < RECOMMENDED_MIN_MASTER_ELIGIBLE:
        logger.info(
            "Low master-eligible count cluster=%s master=%s total=%s",
            ctx.cluster_name,
            master_eligible,
            total_nodes,
        )
        findings.append(
            Finding(
                id="cluster.master_eligible_low",
                category="cluster",
                title="Insufficient master-eligible nodes",
                status=FindingStatus.WARN,
                severity=Severity.HIGH,
                score_impact=6,
                summary=(
                    f"Only {master_eligible} master-eligible node(s) for "
                    f"{total_nodes} total nodes. Elastic recommends an odd "
                    f"number ≥ {RECOMMENDED_MIN_MASTER_ELIGIBLE} for quorum."
                ),
                detail=(
                    "Too few master-eligible nodes increases split-brain risk "
                    "after network partitions.\n\n"
                    "How to resolve:\n"
                    "  1. Add dedicated master nodes (no data role) in production\n"
                    "  2. Use discovery.seed_providers and voting configuration "
                    "for managed deployments\n"
                    "  3. Never run two master-eligible nodes only — use 1 or 3+"
                ),
                source="rule",
                metadata={
                    "master_eligible": master_eligible,
                    "total_nodes": total_nodes,
                    "recommended_min": RECOMMENDED_MIN_MASTER_ELIGIBLE,
                },
            )
        )

    return findings
