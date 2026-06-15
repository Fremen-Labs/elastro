"""Reduce index replica count to recover from yellow states."""

from __future__ import annotations

from typing import Any, Dict

from elastro.core.index import IndexManager
from elastro.core.logger import get_logger

logger = get_logger(__name__)


def planned_reduce_replicas(index_name: str, *, api_mode: bool = False) -> str:
    payload = _payload(api_mode=api_mode)
    return (
        f"PUT /{index_name}/_settings "
        f"body={payload}"
    )


def _payload(*, api_mode: bool) -> Dict[str, Any]:
    settings: Dict[str, Any] = {"number_of_replicas": 0}
    if api_mode:
        settings["auto_expand_replicas"] = "false"
    return {"index": settings}


def reduce_replicas(
    index_manager: IndexManager,
    index_name: str,
    *,
    api_mode: bool = False,
) -> str:
    """Set number_of_replicas to 0 for the target index."""
    payload = _payload(api_mode=api_mode)
    logger.info("Reducing replicas for index %s (api_mode=%s)", index_name, api_mode)
    try:
        index_manager.update(index_name, payload)
    except Exception:
        index_manager._client.get_client().indices.put_settings(
            index=index_name,
            body=payload,
            allow_no_indices=False,
            expand_wildcards="all",
            ignore_unavailable=True,
        )
    if api_mode:
        return (
            f"Replicas reduced to 0 and auto-expand disabled for {index_name}"
        )
    return f"Replicas reduced to 0 for {index_name}"