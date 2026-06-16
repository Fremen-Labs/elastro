"""Retry failed shard allocations via cluster reroute."""

from __future__ import annotations

from elastro.core.index import IndexManager
from elastro.core.logger import get_logger

logger = get_logger(__name__)


def planned_reroute_failed(index_name: str | None = None) -> str:
    target = f" for index {index_name}" if index_name else ""
    return f"POST /_cluster/reroute?retry_failed=true{target}"


def reroute_failed(index_manager: IndexManager) -> str:
    """Ask Elasticsearch to retry failed shard allocations."""
    logger.info("Requesting cluster reroute with retry_failed=true")
    index_manager.reroute(retry_failed=True)
    return "Cluster rerouted to retry failed shards"
