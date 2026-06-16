"""JVM heap pressure rules."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from elastro.core.logger import get_logger
from elastro.health.models import Finding, FindingStatus, Severity
from elastro.health.rules.engine import RuleContext

logger = get_logger(__name__)

DEFAULT_HEAP_THRESHOLD = 75.0


def jvm_heap_used_percent(jvm: Dict[str, Any]) -> Optional[float]:
    """Return JVM heap used percentage from nodes.stats jvm block."""
    mem = jvm.get("mem") or {}
    heap_used = mem.get("heap_used_percent")
    if heap_used is not None:
        try:
            return float(heap_used)
        except (TypeError, ValueError):
            pass

    heap_used_bytes = mem.get("heap_used_in_bytes")
    heap_max_bytes = mem.get("heap_max_in_bytes")
    if heap_used_bytes is not None and heap_max_bytes:
        try:
            return round((float(heap_used_bytes) / float(heap_max_bytes)) * 100, 2)
        except (TypeError, ValueError, ZeroDivisionError):
            return None
    return None


def jvm_pressure_findings(
    nodes_data: Dict[str, Any],
    *,
    threshold: float = DEFAULT_HEAP_THRESHOLD,
) -> List[Finding]:
    """Emit findings when node JVM heap usage exceeds the threshold."""
    nodes = nodes_data.get("nodes") or {}
    findings: List[Finding] = []

    for node_id, node in nodes.items():
        if not isinstance(node, dict):
            continue
        heap_pct = jvm_heap_used_percent(node.get("jvm") or {})
        if heap_pct is None or heap_pct < threshold:
            continue

        node_name = node.get("name", node_id)
        severity = Severity.HIGH if heap_pct >= 90 else Severity.MEDIUM
        status = FindingStatus.WARN if heap_pct < 90 else FindingStatus.FAIL

        logger.debug(
            "JVM pressure on %s: heap_used_percent=%s threshold=%s",
            node_name,
            heap_pct,
            threshold,
        )
        findings.append(
            Finding(
                id=f"jvm.heap_pressure.{node_name}",
                category="jvm",
                title=f"JVM heap pressure on {node_name}",
                status=status,
                severity=severity,
                score_impact=5 if heap_pct < 90 else 10,
                summary=(
                    f"Node '{node_name}' JVM heap is {heap_pct}% used "
                    f"(threshold {threshold}%)."
                ),
                affected_resources=[node_name],
                source="rule",
                metadata={
                    "node_id": node_id,
                    "heap_used_percent": heap_pct,
                    "threshold": threshold,
                },
            )
        )

    return findings


def jvm_rule(ctx: RuleContext) -> List[Finding]:
    """RuleEngine adapter for JVM heap pressure checks."""
    nodes_data = ctx.collector_data.get("nodes") or {}
    if not nodes_data:
        return []
    return jvm_pressure_findings(nodes_data)
