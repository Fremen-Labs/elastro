"""Clear custom index routing allocation filters."""

from __future__ import annotations

from typing import Any, Dict

from elastro.core.index import IndexManager

_ROUTING_FILTER_SETTINGS: Dict[str, Any] = {
    "routing.allocation.require._name": None,
    "routing.allocation.include._name": None,
    "routing.allocation.exclude._name": None,
    "routing.allocation.require.*": None,
    "routing.allocation.include.*": None,
    "routing.allocation.exclude.*": None,
}


def planned_clear_routing_filters(index_name: str) -> str:
    return (
        f"PUT /{index_name}/_settings "
        f"body={{'index': {_ROUTING_FILTER_SETTINGS}}}"
    )


def clear_routing_filters(index_manager: IndexManager, index_name: str) -> str:
    """Remove custom routing allocation filters from an index."""
    index_manager.update(index_name, {"index": _ROUTING_FILTER_SETTINGS})
    return f"Custom routing allocation filters cleared for {index_name}"