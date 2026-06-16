"""Reduce index replica count to recover from yellow states."""

from __future__ import annotations

from typing import Any, Dict, Optional

from elastro.core.index import IndexManager
from elastro.core.logger import get_logger
from elastro.health.rules.replica import smart_replica_target

logger = get_logger(__name__)


def planned_reduce_replicas(
    index_name: str,
    *,
    api_mode: bool = False,
    target_replicas: Optional[int] = None,
) -> str:
    target = target_replicas if target_replicas is not None else 0
    payload = _payload(api_mode=api_mode, target_replicas=target)
    return f"PUT /{index_name}/_settings body={payload}"


def _payload(*, api_mode: bool, target_replicas: int) -> Dict[str, Any]:
    settings: Dict[str, Any] = {"number_of_replicas": target_replicas}
    if api_mode:
        settings["auto_expand_replicas"] = "false"
    return {"index": settings}


def _current_replica_count(index_manager: IndexManager, index_name: str) -> int:
    try:
        raw = index_manager.get(index_name)
    except Exception:
        return 0
    if isinstance(raw, dict) and index_name in raw:
        body = raw[index_name]
    elif isinstance(raw, dict):
        body = next(iter(raw.values()), {})
    else:
        return 0
    settings = (body.get("settings") or {}).get("index") or {}
    try:
        return int(settings.get("number_of_replicas", 0))
    except (TypeError, ValueError):
        return 0


def _data_node_count(index_manager: IndexManager) -> int:
    try:
        es = index_manager._client.get_client()
        health_response = es.cluster.health()
        if hasattr(health_response, "body"):
            health_data = health_response.body
        elif isinstance(health_response, dict):
            health_data = health_response
        else:
            health_data = {}
        if not isinstance(health_data, dict):
            health_data = {}
        return int(health_data.get("number_of_data_nodes", 0))
    except Exception as exc:
        logger.debug("Failed to read data node count: %s", exc)
        return 0


def resolve_replica_target(
    index_manager: IndexManager,
    index_name: str,
    *,
    explicit_target: Optional[int] = None,
) -> int:
    """Choose a safe replica target, preferring smart reduction over zero."""
    if explicit_target is not None:
        return max(0, explicit_target)
    current = _current_replica_count(index_manager, index_name)
    data_nodes = _data_node_count(index_manager)
    if data_nodes > 0 and current > 0:
        return smart_replica_target(current, data_nodes)
    return 0


def reduce_replicas(
    index_manager: IndexManager,
    index_name: str,
    *,
    api_mode: bool = False,
    target_replicas: Optional[int] = None,
) -> str:
    """Reduce replicas to a computed or explicit target."""
    target = resolve_replica_target(
        index_manager,
        index_name,
        explicit_target=target_replicas,
    )
    payload = _payload(api_mode=api_mode, target_replicas=target)
    logger.info(
        "Reducing replicas for index=%s target=%s api_mode=%s",
        index_name,
        target,
        api_mode,
    )
    try:
        index_manager.update(index_name, payload)
    except Exception as primary_exc:
        logger.warning(
            "Primary replica update failed for index=%s; retrying via raw client: %s",
            index_name,
            primary_exc,
            exc_info=True,
        )
        index_manager._client.get_client().indices.put_settings(
            index=index_name,
            body=payload,
            allow_no_indices=False,
            expand_wildcards="all",
            ignore_unavailable=True,
        )
    if api_mode:
        return f"Replicas reduced to {target} and auto-expand disabled for {index_name}"
    return f"Replicas reduced to {target} for {index_name}"
