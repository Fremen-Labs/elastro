"""Replica misconfiguration rule — replicas exceed data node capacity."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

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

_DATA_ROLES = frozenset(
    {"data", "data_content", "data_hot", "data_warm", "data_cold", "data_frozen"}
)


def count_data_nodes(nodes_data: Dict[str, Any]) -> int:
    """Count nodes that can hold shard data."""
    nodes = nodes_data.get("nodes") or {}
    count = 0
    for node in nodes.values():
        if not isinstance(node, dict):
            continue
        roles = node.get("roles") or []
        if any(role in _DATA_ROLES for role in roles):
            count += 1
    return count


def _index_entries(ctx: RuleContext) -> List[Dict[str, Any]]:
    ilm_data = ctx.collector_data.get("ilm") or {}
    indices = ilm_data.get("indices")
    if isinstance(indices, list):
        return [item for item in indices if isinstance(item, dict)]
    return []


def _parse_replica_count(index_entry: Dict[str, Any]) -> Optional[int]:
    raw = index_entry.get("rep", index_entry.get("replicas"))
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def smart_replica_target(current: int, data_nodes: int) -> int:
    """Suggest min(current, data_nodes - 1), floored at zero."""
    if data_nodes <= 0:
        return 0
    return max(0, min(current, data_nodes - 1))


def replica_misconfig_findings(ctx: RuleContext) -> List[Finding]:
    """Emit findings when index replicas exceed available data nodes."""
    nodes_data = ctx.collector_data.get("nodes") or {}
    data_nodes = count_data_nodes(nodes_data)
    if data_nodes <= 0:
        return []

    indices = _index_entries(ctx)
    if not indices:
        return []

    findings: List[Finding] = []
    for index_entry in indices:
        name = str(index_entry.get("index", "")).strip()
        if not name or name.startswith("."):
            continue

        replicas = _parse_replica_count(index_entry)
        if replicas is None or replicas < data_nodes:
            continue

        suggested = smart_replica_target(replicas, data_nodes)
        logger.debug(
            "Replica misconfig on %s: replicas=%s data_nodes=%s suggested=%s",
            name,
            replicas,
            data_nodes,
            suggested,
        )
        findings.append(
            Finding(
                id=f"replica.misconfig.{name}",
                category="shards",
                title=f"Replica misconfiguration: {name}",
                status=FindingStatus.WARN,
                severity=Severity.HIGH,
                score_impact=5,
                summary=(
                    f"Index '{name}' has {replicas} replica(s) but only "
                    f"{data_nodes} data node(s) are available; reduce replicas "
                    f"to {suggested}."
                ),
                affected_resources=[name],
                source="rule",
                remediation=RemediationAction(
                    id="reduce_replicas",
                    label=f"Reduce replicas to {suggested}",
                    command="elastro health fix",
                    safety=RemediationSafety.DESTRUCTIVE,
                ),
                metadata={
                    "current_replicas": replicas,
                    "data_nodes": data_nodes,
                    "suggested_replicas": suggested,
                },
            )
        )

    return findings
