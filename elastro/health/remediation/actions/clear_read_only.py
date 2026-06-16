"""Clear flood-stage read_only_allow_delete index blocks."""

from __future__ import annotations

from typing import Any, Dict

from elastro.core.index import IndexManager
from elastro.core.logger import get_logger

logger = get_logger(__name__)

_CLEAR_READ_ONLY_SETTINGS: Dict[str, Any] = {
    "index": {"blocks": {"read_only_allow_delete": False}}
}


def planned_clear_read_only(index_name: str) -> str:
    return (
        f"PUT /{index_name}/_settings "
        f"body={{'index': {{'blocks': {{'read_only_allow_delete': false}}}}}}"
    )


def clear_read_only(index_manager: IndexManager, index_name: str, **kwargs: object) -> str:
    """Allow writes and deletes again on a flood-stage blocked index."""
    logger.info("Clearing read_only_allow_delete block for index %s", index_name)
    index_manager.update(index_name, _CLEAR_READ_ONLY_SETTINGS)
    return f"read_only_allow_delete block cleared for {index_name}"