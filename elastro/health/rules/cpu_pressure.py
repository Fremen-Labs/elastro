"""Per-node CPU pressure detection."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from elastro.core.logger import get_logger
from elastro.health.models import Finding, FindingStatus, Severity
from elastro.health.rules.engine import RuleContext

logger = get_logger(__name__)

DEFAULT_CPU_THRESHOLD = 85.0


def _node_cpu_percent(node: Dict[str, Any]) -> Optional[float]:
    cpu = (node.get("os") or {}).get("cpu") or {}
    raw = cpu.get("percent")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def cpu_pressure_findings(
    nodes_data: Dict[str, Any],
    *,
    threshold: float = DEFAULT_CPU_THRESHOLD,
) -> List[Finding]:
    """Emit findings when node OS CPU exceeds threshold."""
    nodes = nodes_data.get("nodes") or {}
    findings: List[Finding] = []

    for node_id, node in nodes.items():
        if not isinstance(node, dict):
            continue
        cpu_pct = _node_cpu_percent(node)
        if cpu_pct is None or cpu_pct < threshold:
            continue

        node_name = str(node.get("name", node_id))
        severity = Severity.HIGH if cpu_pct >= 95 else Severity.MEDIUM
        status = FindingStatus.FAIL if cpu_pct >= 95 else FindingStatus.WARN

        logger.debug(
            "CPU pressure node=%s cpu_percent=%s threshold=%s",
            node_name,
            cpu_pct,
            threshold,
        )
        findings.append(
            Finding(
                id=f"nodes.cpu_pressure.{node_name}",
                category="nodes",
                title=f"High CPU usage on {node_name}",
                status=status,
                severity=severity,
                score_impact=6 if cpu_pct < 95 else 10,
                summary=(
                    f"Node '{node_name}' reports {cpu_pct:.0f}% CPU "
                    f"(threshold {threshold:.0f}%)."
                ),
                detail=(
                    "Sustained high CPU on data nodes slows searches, indexing, "
                    "and shard recovery.\n\n"
                    "Common causes:\n"
                    "  • Heavy aggregations or scripted queries\n"
                    "  • Merge pressure on undersized nodes\n"
                    "  • Hot shards concentrated on one node (see hotspot findings)\n\n"
                    "How to resolve:\n"
                    "  1. elastro health hotspots -o table\n"
                    "  2. Scale out or upgrade CPU on overloaded nodes\n"
                    "  3. Reduce expensive searches; add dedicated coordinating nodes"
                ),
                affected_resources=[node_name],
                source="rule",
                metadata={
                    "node_id": node_id,
                    "cpu_percent": cpu_pct,
                    "threshold": threshold,
                },
            )
        )

    return findings


def cpu_pressure_rule(ctx: RuleContext) -> List[Finding]:
    nodes_data = ctx.collector_data.get("nodes") or {}
    if not nodes_data:
        return []
    return cpu_pressure_findings(nodes_data)