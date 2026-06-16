"""Unassigned shard detection — red/yellow cluster root cause."""

from __future__ import annotations

from typing import List

from elastro.core.logger import get_logger
from elastro.health.models import (
    Finding,
    FindingStatus,
    RemediationAction,
    RemediationSafety,
    Severity,
)
from elastro.health.rules.engine import RuleContext

logger = get_logger(__name__)


def unassigned_shard_findings(ctx: RuleContext) -> List[Finding]:
    """Emit a finding when shards are UNASSIGNED."""
    analysis = (ctx.collector_data.get("shards") or {}).get("analysis") or {}
    unassigned = int(analysis.get("unassigned_count", 0))

    if unassigned <= 0:
        health = ctx.collector_data.get("cluster_health") or {}
        try:
            unassigned = int(health.get("unassigned_shards", 0) or 0)
        except (TypeError, ValueError):
            unassigned = 0

    if unassigned <= 0:
        return []

    cluster_name = ctx.cluster_name
    logger.info(
        "Unassigned shards detected cluster=%s count=%s",
        cluster_name,
        unassigned,
    )
    return [
        Finding(
            id="shards.unassigned",
            category="shards",
            title="Unassigned shards detected",
            status=FindingStatus.FAIL if unassigned > 0 else FindingStatus.WARN,
            severity=Severity.HIGH,
            score_impact=min(unassigned * 2, 15),
            summary=(
                f"{unassigned} shard(s) are UNASSIGNED. Elasticsearch cannot "
                "route these shards to data nodes, which often drives yellow "
                "or red cluster health and risks query/indexing gaps."
            ),
            detail=_unassigned_detail(unassigned),
            affected_resources=[cluster_name] if cluster_name != "unknown" else [],
            source="rule",
            remediation=RemediationAction(
                id="explain_allocation",
                label="Explain shard allocation",
                command="elastro health shards --explain -o table",
                safety=RemediationSafety.OBSERVE,
            ),
            metadata={"unassigned_count": unassigned},
        )
    ]


def _unassigned_detail(count: int) -> str:
    return (
        f"{count} shard(s) have state UNASSIGNED.\n\n"
        "Common causes:\n"
        "  • Too few data nodes for replica count (replica > data_nodes - 1)\n"
        "  • Disk watermarks blocking allocation (high/flood stage)\n"
        "  • Index routing filters or allocation awareness pinning shards\n"
        "  • Cluster shard limits (cluster.max_shards_per_node) reached\n"
        "  • Recent node loss without enough replicas\n\n"
        "How to resolve:\n"
        "  1. elastro health shards --explain -o table\n"
        "  2. elastro health shards --analyze -o table\n"
        "  3. elastro health fix --dry-run  (replica/reroute remediations)\n"
        "  4. Free disk or raise watermarks if allocation is disk-blocked"
    )
