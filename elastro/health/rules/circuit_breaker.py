"""Circuit breaker tripped / high utilization detection."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from elastro.core.logger import get_logger
from elastro.health.models import Finding, FindingStatus, Severity
from elastro.health.rules.engine import RuleContext

logger = get_logger(__name__)

DEFAULT_USAGE_THRESHOLD = 85.0
_MONITORED_BREAKERS = (
    "request",
    "fielddata",
    "in_flight_requests",
    "parent",
    "model_inference",
)


def _breaker_usage(stats: Dict[str, Any]) -> Optional[float]:
    estimated = stats.get("estimated_size_in_bytes")
    limit = stats.get("limit_size_in_bytes") or stats.get("limit_size")
    if estimated is None or not limit:
        return None
    try:
        return round((float(estimated) / float(limit)) * 100, 2)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def circuit_breaker_findings(
    nodes_data: Dict[str, Any],
    *,
    usage_threshold: float = DEFAULT_USAGE_THRESHOLD,
) -> List[Finding]:
    """Emit findings when breakers are tripped or near limit."""
    nodes = nodes_data.get("nodes") or {}
    findings: List[Finding] = []

    for node_id, node in nodes.items():
        if not isinstance(node, dict):
            continue
        node_name = str(node.get("name", node_id))
        breakers = node.get("breakers") or {}
        if not isinstance(breakers, dict):
            continue

        for breaker_name, stats in breakers.items():
            if breaker_name not in _MONITORED_BREAKERS or not isinstance(stats, dict):
                continue

            tripped = bool(stats.get("tripped"))
            usage = _breaker_usage(stats)
            if not tripped and (usage is None or usage < usage_threshold):
                continue

            severity = Severity.CRITICAL if tripped else Severity.HIGH
            status = FindingStatus.FAIL if tripped else FindingStatus.WARN
            if tripped:
                summary = (
                    f"Circuit breaker '{breaker_name}' is TRIPPED on '{node_name}'. "
                    "Elasticsearch is rejecting operations to protect JVM heap."
                )
            else:
                summary = (
                    f"Circuit breaker '{breaker_name}' on '{node_name}' is at "
                    f"{usage}% of its limit (threshold {usage_threshold}%)."
                )

            logger.debug(
                "Circuit breaker alert node=%s breaker=%s tripped=%s usage=%s",
                node_name,
                breaker_name,
                tripped,
                usage,
            )
            findings.append(
                Finding(
                    id=f"jvm.circuit_breaker.{breaker_name}.{node_name}",
                    category="jvm",
                    title=f"Circuit breaker {'tripped' if tripped else 'pressure'}: {breaker_name}",
                    status=status,
                    severity=severity,
                    score_impact=10 if tripped else 6,
                    summary=summary,
                    detail=_circuit_breaker_detail(breaker_name, tripped, usage),
                    affected_resources=[node_name],
                    source="rule",
                    metadata={
                        "node_id": node_id,
                        "breaker": breaker_name,
                        "tripped": tripped,
                        "usage_percent": usage,
                        "stats": stats,
                    },
                )
            )

    return findings


def _circuit_breaker_detail(
    breaker_name: str,
    tripped: bool,
    usage: Optional[float],
) -> str:
    state = "TRIPPED" if tripped else f"{usage}% of limit"
    return (
        f"Breaker '{breaker_name}' state: {state}.\n\n"
        "Implications:\n"
        "  • Tripped breakers return 429/503 errors and block searches or aggregations\n"
        "  • Parent breaker trips affect all child operations on the node\n"
        "  • Fielddata breaker trips often indicate sorting/aggregations on text fields\n\n"
        "How to resolve:\n"
        "  1. Reduce heavy aggregations, batch size, or concurrent searches\n"
        "  2. Add data nodes or increase heap if sustained legitimate load\n"
        "  3. Use doc_values/keyword fields instead of fielddata on text\n"
        "  4. Check for memory leaks or oversized request payloads\n"
        "  5. elastro health nodes -o table  (review per-node heap/disk)"
    )


def circuit_breaker_rule(ctx: RuleContext) -> List[Finding]:
    nodes_data = ctx.collector_data.get("nodes") or {}
    if not nodes_data:
        return []
    return circuit_breaker_findings(nodes_data)