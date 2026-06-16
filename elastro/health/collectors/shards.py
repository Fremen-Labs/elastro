"""Shard listing and size analysis collector."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from elastro.core.errors import OperationError
from elastro.core.index import IndexManager
from elastro.core.logger import get_logger
from elastro.health.collectors.base import CollectContext, CollectorResult
from elastro.health.shards import (
    DEFAULT_OVERSHARD_THRESHOLD_MB,
    DEFAULT_UNDERSHARD_THRESHOLD_GB,
    ShardAnalysis,
    analyze_shards,
)

logger = get_logger(__name__)

_CAT_HEADERS = "index,shard,prirep,state,store,node"


class ShardsCollector:
    """Collect cat.shards output and derive size analysis."""

    name = "shards"

    def collect(self, ctx: CollectContext) -> CollectorResult:
        index_pattern = ctx.options.get("index")
        overshard_mb = float(
            ctx.options.get("overshard_threshold_mb", DEFAULT_OVERSHARD_THRESHOLD_MB)
        )
        undershard_gb = float(
            ctx.options.get("undershard_threshold_gb", DEFAULT_UNDERSHARD_THRESHOLD_GB)
        )

        logger.debug(
            "Collecting shard stats index=%s overshard_mb=%s undershard_gb=%s",
            index_pattern,
            overshard_mb,
            undershard_gb,
        )
        try:
            rows = _fetch_cat_shards(ctx, index_pattern=index_pattern)
            analysis = analyze_shards(
                rows,
                overshard_threshold_mb=overshard_mb,
                undershard_threshold_gb=undershard_gb,
            )
            logger.info(
                "Shards collector complete: total=%s unassigned=%s",
                analysis.total_shards,
                analysis.unassigned_count,
            )
            return CollectorResult(
                name=self.name,
                status="ok",
                data={
                    "shards": rows,
                    "analysis": _analysis_to_dict(analysis),
                    "index": index_pattern,
                },
            )
        except OperationError as exc:
            logger.error("Shards collector failed: %s", exc, exc_info=True)
            return CollectorResult(name=self.name, status="error", error=str(exc))


def _fetch_cat_shards(
    ctx: CollectContext,
    *,
    index_pattern: Optional[str],
) -> List[Dict[str, Any]]:
    client = ctx.client.client
    params: Dict[str, Any] = {
        "format": "json",
        "h": _CAT_HEADERS,
        "bytes": "b",
    }
    if index_pattern:
        params["index"] = index_pattern

    try:
        response = client.cat.shards(**params)
    except Exception as exc:
        logger.error("cat.shards request failed: %s", exc, exc_info=True)
        raise OperationError(f"Failed to list shards: {exc}") from exc

    if isinstance(response, list):
        return [row for row in response if isinstance(row, dict)]
    body = getattr(response, "body", response)
    if isinstance(body, list):
        return [row for row in body if isinstance(row, dict)]
    return []


def explain_allocation(
    ctx: CollectContext,
    *,
    index_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Explain shard allocation for a cluster or specific index."""
    if index_name:
        manager = IndexManager(ctx.client)
        return manager.allocation_explain(index_name)
    try:
        return dict(ctx.client.client.cluster.allocation_explain())
    except Exception as exc:
        logger.error("cluster.allocation_explain failed: %s", exc, exc_info=True)
        raise OperationError(f"Failed to explain allocation: {exc}") from exc


def _analysis_to_dict(analysis: ShardAnalysis) -> Dict[str, Any]:
    return {
        "total_shards": analysis.total_shards,
        "measured_shards": analysis.measured_shards,
        "avg_bytes": analysis.avg_bytes,
        "oversharded_count": analysis.oversharded_count,
        "undersharded_count": analysis.undersharded_count,
        "unassigned_count": analysis.unassigned_count,
        "overshard_threshold_bytes": analysis.overshard_threshold_bytes,
        "undershard_threshold_bytes": analysis.undershard_threshold_bytes,
        "oversharded": [
            {
                "index": item.index,
                "shard": item.shard,
                "prirep": item.prirep,
                "store_bytes": item.store_bytes,
                "node": item.node,
            }
            for item in analysis.oversharded[:50]
        ],
        "undersharded": [
            {
                "index": item.index,
                "shard": item.shard,
                "prirep": item.prirep,
                "store_bytes": item.store_bytes,
                "node": item.node,
            }
            for item in analysis.undersharded[:50]
        ],
    }