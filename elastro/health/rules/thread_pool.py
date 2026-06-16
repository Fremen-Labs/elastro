"""Thread pool rejection detection (429 rejected requests)."""

from __future__ import annotations

from typing import Any, Dict, List

from elastro.core.logger import get_logger
from elastro.health.models import Finding, FindingStatus, Severity
from elastro.health.rules.engine import RuleContext

logger = get_logger(__name__)

_MONITORED_POOLS = ("write", "search", "bulk", "index", "management")


def thread_pool_findings(nodes_data: Dict[str, Any]) -> List[Finding]:
    """Emit findings when thread pools report rejected tasks."""
    nodes = nodes_data.get("nodes") or {}
    findings: List[Finding] = []

    for node_id, node in nodes.items():
        if not isinstance(node, dict):
            continue
        node_name = str(node.get("name", node_id))
        pools = node.get("thread_pool") or {}
        if not isinstance(pools, dict):
            continue

        for pool_name, stats in pools.items():
            if pool_name not in _MONITORED_POOLS or not isinstance(stats, dict):
                continue
            try:
                rejected = int(stats.get("rejected", 0) or 0)
            except (TypeError, ValueError):
                rejected = 0
            if rejected <= 0:
                continue

            queue = stats.get("queue", 0)
            active = stats.get("active", 0)
            logger.info(
                "Thread pool rejections node=%s pool=%s rejected=%s",
                node_name,
                pool_name,
                rejected,
            )
            findings.append(
                Finding(
                    id=f"nodes.thread_pool_rejected.{pool_name}.{node_name}",
                    category="nodes",
                    title=f"Thread pool rejections: {pool_name}",
                    status=FindingStatus.WARN,
                    severity=Severity.HIGH,
                    score_impact=min(5 + rejected // 10, 12),
                    summary=(
                        f"Node '{node_name}' rejected {rejected} task(s) on the "
                        f"'{pool_name}' thread pool (active={active}, queue={queue})."
                    ),
                    detail=_thread_pool_detail(pool_name, rejected),
                    affected_resources=[node_name],
                    source="rule",
                    metadata={
                        "node_id": node_id,
                        "pool": pool_name,
                        "rejected": rejected,
                        "active": active,
                        "queue": queue,
                    },
                )
            )

    return findings


def _thread_pool_detail(pool_name: str, rejected: int) -> str:
    return (
        f"The '{pool_name}' pool rejected {rejected} task(s).\n\n"
        "Implications:\n"
        "  • Clients receive HTTP 429 responses; bulk/index/search work is dropped\n"
        "  • Sustained rejections mean the node cannot keep up with ingest or query load\n"
        "  • Write pool rejections often coincide with indexing spikes or slow disks\n\n"
        "How to resolve:\n"
        "  1. Scale out data/ingest nodes or reduce bulk concurrency\n"
        "  2. Tune thread_pool.write.size / queue_size only after adding capacity\n"
        "  3. Check disk latency and JVM pressure on rejecting nodes\n"
        "  4. Stagger reindex/snapshot operations across off-peak windows"
    )


def thread_pool_rule(ctx: RuleContext) -> List[Finding]:
    nodes_data = ctx.collector_data.get("nodes") or {}
    if not nodes_data:
        return []
    return thread_pool_findings(nodes_data)