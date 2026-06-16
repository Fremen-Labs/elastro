"""Node stats and info collector."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from elastro.core.errors import OperationError
from elastro.core.logger import get_logger
from elastro.health.collectors.base import CollectContext, CollectorResult
from elastro.health.manager import HealthManager

logger = get_logger(__name__)

DEFAULT_METRICS = ("jvm", "fs", "os", "breaker", "thread_pool")


class NodesCollector:
    """Collect per-node JVM, filesystem, OS, and circuit-breaker stats."""

    name = "nodes"

    def collect(self, ctx: CollectContext) -> CollectorResult:
        manager = HealthManager(ctx.client)
        metrics = _resolve_metrics(ctx.options.get("metrics"))
        node_id = ctx.options.get("node_id")

        logger.debug(
            "Collecting node stats metrics=%s node_id=%s",
            metrics,
            node_id,
        )
        try:
            stats = manager.node_stats(
                node_id=node_id,
                metrics=list(metrics),
            )
            info = manager.node_info(node_id=node_id)
            nodes = _normalize_nodes(stats, info)
            return CollectorResult(
                name=self.name,
                status="ok",
                data={
                    "metrics": list(metrics),
                    "nodes": nodes,
                    "node_count": len(nodes),
                },
            )
        except OperationError as exc:
            logger.error("Nodes collector failed: %s", exc)
            return CollectorResult(name=self.name, status="error", error=str(exc))


def _resolve_metrics(raw: Any) -> List[str]:
    if raw is None:
        return list(DEFAULT_METRICS)
    if isinstance(raw, str):
        return [part.strip() for part in raw.split(",") if part.strip()]
    if isinstance(raw, (list, tuple)):
        return [str(part).strip() for part in raw if str(part).strip()]
    return list(DEFAULT_METRICS)


def _normalize_nodes(
    stats: Dict[str, Any],
    info: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """Merge nodes.stats and nodes.info payloads keyed by node id."""
    nodes: Dict[str, Dict[str, Any]] = {}
    for node_id, body in (stats.get("nodes") or {}).items():
        if not isinstance(body, dict):
            continue
        nodes[node_id] = {
            "id": node_id,
            "name": body.get("name", node_id),
            "host": body.get("host_name"),
            "roles": (info.get("nodes", {}).get(node_id, {}) or {}).get("roles", []),
            "jvm": body.get("jvm", {}),
            "fs": body.get("fs", {}),
            "os": body.get("os", {}),
            "breakers": body.get("breakers", {}),
            "thread_pool": body.get("thread_pool", {}),
        }
    return nodes
