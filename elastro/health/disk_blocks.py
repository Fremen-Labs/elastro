"""Discover indices blocked by flood-stage disk watermarks."""

from __future__ import annotations

import fnmatch
from typing import List, Optional

from elastro.core.index import IndexManager
from elastro.core.logger import get_logger

logger = get_logger(__name__)


def _is_read_only_blocked(value: object) -> bool:
    return str(value).lower() in {"true", "1"}


def discover_read_only_blocked_indices(
    index_manager: IndexManager,
    *,
    pattern: str = "*",
) -> List[str]:
    """Return indices with ``index.blocks.read_only_allow_delete`` enabled."""
    index_manager._ensure_connected()
    es = index_manager._client.get_client()
    try:
        response = es.indices.get_settings(
            index=pattern,
            name="index.blocks.read_only_allow_delete",
            ignore_unavailable=True,
            allow_no_indices=True,
        )
        body = index_manager._handle_response(response)
    except Exception as exc:
        logger.warning("Failed to scan read_only_allow_delete blocks: %s", exc)
        return []

    blocked: List[str] = []
    if not isinstance(body, dict):
        return blocked

    for index_name, payload in body.items():
        if not isinstance(payload, dict):
            continue
        settings = (payload.get("settings") or {}).get("index") or {}
        blocks = settings.get("blocks") or {}
        if _is_read_only_blocked(blocks.get("read_only_allow_delete")):
            blocked.append(index_name)

    blocked.sort()
    logger.info(
        "Read-only block scan complete: pattern=%s blocked=%s",
        pattern,
        len(blocked),
    )
    return blocked


def filter_indices(indices: List[str], pattern: Optional[str]) -> List[str]:
    """Filter index names with shell-style glob matching."""
    if not pattern:
        return indices
    return [name for name in indices if fnmatch.fnmatchcase(name, pattern)]
