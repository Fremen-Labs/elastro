"""Per-node resource hotspot variance rule."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from elastro.core.logger import get_logger
from elastro.health.collectors.disk import disk_used_percent
from elastro.health.models import Finding, FindingStatus, Severity
from elastro.health.rules.engine import RuleContext
from elastro.health.rules.jvm import jvm_heap_used_percent

logger = get_logger(__name__)

DEFAULT_HOTSPOT_VARIANCE_PCT = 30.0


def _node_metric_values(
    nodes_data: Dict[str, Any],
) -> Dict[str, List[Tuple[str, float]]]:
    """Extract per-node metric samples keyed by metric name."""
    nodes = nodes_data.get("nodes") or {}
    metrics: Dict[str, List[Tuple[str, float]]] = {
        "heap_used_percent": [],
        "disk_used_percent": [],
        "cpu_percent": [],
    }

    for node_id, node in nodes.items():
        if not isinstance(node, dict):
            continue
        node_name = str(node.get("name", node_id))

        heap_pct = jvm_heap_used_percent(node.get("jvm") or {})
        if heap_pct is not None:
            metrics["heap_used_percent"].append((node_name, heap_pct))

        disk_pct = disk_used_percent(node.get("fs") or {})
        if disk_pct is not None:
            metrics["disk_used_percent"].append((node_name, disk_pct))

        cpu = (node.get("os") or {}).get("cpu") or {}
        cpu_pct = cpu.get("percent")
        if cpu_pct is not None:
            try:
                metrics["cpu_percent"].append((node_name, float(cpu_pct)))
            except (TypeError, ValueError):
                pass

    return metrics


def hotspot_variance(
    nodes_data: Dict[str, Any],
    *,
    variance_threshold: float = DEFAULT_HOTSPOT_VARIANCE_PCT,
) -> List[Dict[str, Any]]:
    """Return hotspot summaries when node metric spread exceeds the threshold."""
    metrics = _node_metric_values(nodes_data)
    hotspots: List[Dict[str, Any]] = []

    labels = {
        "heap_used_percent": "JVM heap",
        "disk_used_percent": "disk usage",
        "cpu_percent": "CPU",
    }

    for metric_name, samples in metrics.items():
        if len(samples) < 2:
            continue
        values = [value for _, value in samples]
        spread = max(values) - min(values)
        if spread < variance_threshold:
            continue

        hottest = max(samples, key=lambda item: item[1])
        coldest = min(samples, key=lambda item: item[1])
        hotspots.append(
            {
                "metric": metric_name,
                "label": labels.get(metric_name, metric_name),
                "spread": round(spread, 2),
                "min_node": coldest[0],
                "min_value": coldest[1],
                "max_node": hottest[0],
                "max_value": hottest[1],
                "threshold": variance_threshold,
            }
        )

    return hotspots


def hotspot_findings(
    ctx: RuleContext,
    *,
    variance_threshold: float = DEFAULT_HOTSPOT_VARIANCE_PCT,
) -> List[Finding]:
    """Emit findings when per-node resource usage variance is high."""
    nodes_data = ctx.collector_data.get("nodes") or {}
    if not nodes_data:
        return []

    hotspots = hotspot_variance(
        nodes_data,
        variance_threshold=variance_threshold,
    )
    findings: List[Finding] = []
    for hotspot in hotspots:
        label = hotspot["label"]
        logger.debug(
            "Hotspot detected metric=%s spread=%s threshold=%s",
            hotspot["metric"],
            hotspot["spread"],
            variance_threshold,
        )
        findings.append(
            Finding(
                id=f"nodes.hotspot.{hotspot['metric']}",
                category="nodes",
                title=f"Node hotspot: {label}",
                status=FindingStatus.WARN,
                severity=Severity.MEDIUM,
                score_impact=5,
                summary=(
                    f"{label} varies by {hotspot['spread']:.1f} points across nodes "
                    f"({hotspot['min_node']}={hotspot['min_value']:.1f}, "
                    f"{hotspot['max_node']}={hotspot['max_value']:.1f})."
                ),
                affected_resources=[hotspot["max_node"], hotspot["min_node"]],
                source="rule",
                metadata=hotspot,
            )
        )
    return findings