"""Cluster shard limit pressure (max shards open)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from elastro.core.logger import get_logger
from elastro.health.models import Finding, FindingStatus, Severity
from elastro.health.rules.engine import RuleContext
from elastro.health.rules.replica import count_data_nodes

logger = get_logger(__name__)

DEFAULT_MAX_SHARDS_PER_NODE = 1000
DEFAULT_WARN_RATIO = 0.85


def _merged_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    for layer in ("defaults", "persistent", "transient"):
        values = settings.get(layer, {})
        if isinstance(values, dict):
            merged.update(values)
    return merged


def _parse_int_setting(value: Any, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def shard_limit_findings(
    ctx: RuleContext,
    *,
    warn_ratio: float = DEFAULT_WARN_RATIO,
) -> List[Finding]:
    """Warn when open shards approach cluster.max_shards_per_node capacity."""
    shards_data = ctx.collector_data.get("shards") or {}
    analysis = shards_data.get("analysis") or {}
    open_shards = int(analysis.get("total_shards", 0) or 0)
    if open_shards <= 0:
        return []

    nodes_data = ctx.collector_data.get("nodes") or {}
    data_nodes = count_data_nodes(nodes_data)
    if data_nodes <= 0:
        return []

    max_per_node = DEFAULT_MAX_SHARDS_PER_NODE
    settings_blob = ctx.collector_data.get("cluster_settings")
    if isinstance(settings_blob, dict):
        merged = _merged_settings(settings_blob)
        max_per_node = _parse_int_setting(
            merged.get("cluster.max_shards_per_node"),
            DEFAULT_MAX_SHARDS_PER_NODE,
        )

    cluster_limit = max_per_node * data_nodes
    if cluster_limit <= 0:
        return []

    utilization = open_shards / cluster_limit
    if utilization < warn_ratio:
        return []

    pct = round(utilization * 100, 1)
    severity = Severity.HIGH if utilization >= 0.95 else Severity.MEDIUM
    status = FindingStatus.FAIL if utilization >= 0.98 else FindingStatus.WARN

    logger.info(
        "Shard limit pressure cluster=%s open=%s limit=%s pct=%s",
        ctx.cluster_name,
        open_shards,
        cluster_limit,
        pct,
    )
    return [
        Finding(
            id="cluster.shard_limit_pressure",
            category="cluster",
            title="Approaching maximum shard limit",
            status=status,
            severity=severity,
            score_impact=8 if utilization >= 0.95 else 5,
            summary=(
                f"{open_shards:,} shards open ({pct}% of estimated "
                f"{cluster_limit:,} limit = {max_per_node:,}/node × {data_nodes} data nodes)."
            ),
            detail=_shard_limit_detail(open_shards, cluster_limit, max_per_node, data_nodes),
            affected_resources=[ctx.cluster_name] if ctx.cluster_name != "unknown" else [],
            source="rule",
            metadata={
                "open_shards": open_shards,
                "cluster_limit": cluster_limit,
                "max_shards_per_node": max_per_node,
                "data_nodes": data_nodes,
                "utilization_percent": pct,
            },
        )
    ]


def _shard_limit_detail(
    open_shards: int,
    cluster_limit: int,
    max_per_node: int,
    data_nodes: int,
) -> str:
    return (
        f"Open shards: {open_shards:,} / estimated limit {cluster_limit:,}.\n\n"
        "Implications:\n"
        "  • New indices, rollovers, and restores fail with 'maximum shards open'\n"
        "  • Often follows oversharding or aggressive ILM rollover\n\n"
        "How to resolve:\n"
        "  1. elastro health trends --finding shards.oversharded -o table\n"
        "  2. Delete empty backing indices; shrink or reindex to fewer shards\n"
        "  3. Temporarily raise cluster.max_shards_per_node only with added data nodes\n"
        f"  4. Current setting: {max_per_node:,} shards/node across {data_nodes} data nodes"
    )


def shard_limit_rule(ctx: RuleContext) -> List[Finding]:
    return shard_limit_findings(ctx)