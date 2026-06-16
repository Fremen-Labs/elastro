"""Local rollback store for reversible remediation actions."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from elastro.core.index import IndexManager
from elastro.core.logger import get_logger

logger = get_logger(__name__)

DEFAULT_ROLLBACK_DIR = Path.home() / ".elastic" / "health-rollbacks"
_ROLLBACK_ID_PATTERN = re.compile(r"^rb-[0-9a-f-]{36}$")
_ROLLBACK_SETTINGS_KEYS = (
    "number_of_replicas",
    "auto_expand_replicas",
    "routing.allocation.require",
    "routing.allocation.include",
    "routing.allocation.exclude",
    "blocks",
)


class RollbackRecord(BaseModel):
    """Snapshot of index settings before a remediation was applied."""

    rollback_id: str
    session_id: str
    action_id: str
    index_name: str
    before: Dict[str, Any]
    applied_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    cluster_name: Optional[str] = None


class RollbackStore:
    """Persist rollback records under ~/.elastic/health-rollbacks/."""

    def __init__(self, root: Optional[Path] = None) -> None:
        self._root = root or DEFAULT_ROLLBACK_DIR

    @property
    def root(self) -> Path:
        return self._root

    def save(self, record: RollbackRecord) -> str:
        """Write a rollback record with restrictive file permissions."""
        self._root.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self._root, 0o700)
        except OSError:
            pass

        path = self._root / f"{record.rollback_id}.json"
        path.write_text(
            record.model_dump_json(indent=2),
            encoding="utf-8",
        )
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        logger.info(
            "Rollback snapshot saved rollback_id=%s action=%s index=%s",
            record.rollback_id,
            record.action_id,
            record.index_name,
        )
        return record.rollback_id

    def get(self, rollback_id: str) -> Optional[RollbackRecord]:
        """Load a rollback record by id."""
        if not _ROLLBACK_ID_PATTERN.match(rollback_id):
            logger.warning("Invalid rollback_id format: %s", rollback_id)
            return None
        path = (self._root / f"{rollback_id}.json").resolve()
        root = self._root.resolve()
        if not path.is_relative_to(root):
            logger.warning("Rollback path escapes store root: %s", rollback_id)
            return None
        if not path.exists():
            return None
        return RollbackRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def list_records(self, *, limit: int = 50) -> List[RollbackRecord]:
        """Return recent rollback records sorted by applied_at descending."""
        if not self._root.exists():
            return []
        records: List[RollbackRecord] = []
        for path in self._root.glob("*.json"):
            try:
                records.append(
                    RollbackRecord.model_validate_json(path.read_text(encoding="utf-8"))
                )
            except Exception as exc:
                logger.warning(
                    "Skipping invalid rollback file %s: %s",
                    path.name,
                    exc,
                )
        records.sort(key=lambda item: item.applied_at, reverse=True)
        return records[:limit]


def capture_index_settings(
    index_manager: IndexManager,
    index_name: str,
) -> Optional[Dict[str, Any]]:
    """Capture index settings relevant for rollback."""
    try:
        raw = index_manager.get(index_name)
    except Exception as exc:
        logger.warning(
            "Failed to capture settings for rollback index=%s: %s",
            index_name,
            exc,
            exc_info=True,
        )
        return None

    if isinstance(raw, dict) and index_name in raw:
        index_body = raw[index_name]
    elif isinstance(raw, dict):
        index_body = next(iter(raw.values()), {})
    else:
        return None

    settings = (index_body.get("settings") or {}).get("index") or {}
    if not isinstance(settings, dict):
        return None

    captured: Dict[str, Any] = {}
    for key, value in settings.items():
        if key in _ROLLBACK_SETTINGS_KEYS or key.startswith("routing.allocation."):
            captured[key] = value

    if not captured:
        return None
    return {"index": captured}


def create_rollback_record(
    *,
    session_id: str,
    action_id: str,
    index_name: str,
    before: Dict[str, Any],
    cluster_name: Optional[str] = None,
) -> RollbackRecord:
    """Build a rollback record with a generated id."""
    return RollbackRecord(
        rollback_id=f"rb-{uuid4()}",
        session_id=session_id,
        action_id=action_id,
        index_name=index_name,
        before=before,
        cluster_name=cluster_name,
    )


def describe_rollback_restore(record: RollbackRecord) -> str:
    """Return the API call that would restore a rollback snapshot."""
    from elastro.health.remediation.dry_run import planned_rollback_call

    return planned_rollback_call(record.index_name, record.before)


def apply_rollback(
    index_manager: IndexManager,
    record: RollbackRecord,
    *,
    dry_run: bool = False,
) -> str:
    """Restore index settings captured in a rollback record."""
    if dry_run:
        keys = sorted((record.before.get("index") or {}).keys())
        planned = describe_rollback_restore(record)
        return (
            f"Would restore settings for '{record.index_name}' "
            f"from rollback {record.rollback_id} (keys={','.join(keys)}). "
            f"Planned: {planned}"
        )

    logger.info(
        "Applying rollback rollback_id=%s index=%s action=%s",
        record.rollback_id,
        record.index_name,
        record.action_id,
    )
    try:
        index_manager.update(record.index_name, record.before)
    except Exception as exc:
        logger.error(
            "Rollback apply failed rollback_id=%s index=%s: %s",
            record.rollback_id,
            record.index_name,
            exc,
            exc_info=True,
        )
        raise
    return (
        f"Restored settings for '{record.index_name}' "
        f"from rollback {record.rollback_id}"
    )
