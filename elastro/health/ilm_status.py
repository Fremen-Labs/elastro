"""ILM lifecycle status helpers for health commands."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from elastro.core.client import ElasticsearchClient
from elastro.core.ilm import IlmManager
from elastro.core.index import IndexManager
from elastro.core.logger import get_logger
from elastro.health.collectors.ilm import _lifecycle_issue, _select_explain_targets

logger = get_logger(__name__)

_MAX_EXPLAIN = 100


class StuckIlmIndex(BaseModel):
    """Index with a stuck or failed ILM lifecycle step."""

    index_name: str
    health: str = "unknown"
    issue: str
    step: str = ""
    explain: Dict[str, Any] = Field(default_factory=dict)


def list_ilm_indices(
    client: ElasticsearchClient,
    *,
    index_pattern: Optional[str] = None,
    stuck_only: bool = True,
    health_report: Optional[Dict[str, Any]] = None,
    limit: int = _MAX_EXPLAIN,
) -> List[StuckIlmIndex]:
    """Return ILM lifecycle rows, optionally limited to stuck indices only."""
    if stuck_only:
        return list_stuck_ilm_indices(
            client,
            index_pattern=index_pattern,
            health_report=health_report,
            limit=limit,
        )

    index_manager = IndexManager(client)
    ilm_manager = IlmManager(client)
    indices = index_manager.list(index_pattern or "*")
    targets = _select_explain_targets(indices, health_report)

    if index_pattern:
        import fnmatch

        targets = {
            name
            for name in targets
            if fnmatch.fnmatchcase(name, index_pattern)
        }

    health_by_index = {
        str(entry.get("index", "")): str(entry.get("health", "unknown")).lower()
        for entry in indices
        if isinstance(entry, dict)
    }

    rows: List[StuckIlmIndex] = []
    for index_name in sorted(targets)[:limit]:
        try:
            explain = ilm_manager.explain_lifecycle(index_name)
        except Exception as exc:
            logger.debug("Skipping ILM explain for %s: %s", index_name, exc)
            continue

        issue = _lifecycle_issue(explain)
        rows.append(
            StuckIlmIndex(
                index_name=index_name,
                health=health_by_index.get(index_name, "unknown"),
                issue=issue or "ok",
                step=str(explain.get("step", "")),
                explain=explain,
            )
        )

    logger.info("ILM scan complete: targets=%s rows=%s", len(targets), len(rows))
    return rows


def list_stuck_ilm_indices(
    client: ElasticsearchClient,
    *,
    index_pattern: Optional[str] = None,
    health_report: Optional[Dict[str, Any]] = None,
    limit: int = _MAX_EXPLAIN,
) -> List[StuckIlmIndex]:
    """Return indices whose ILM lifecycle is in ERROR or otherwise stuck."""
    index_manager = IndexManager(client)
    ilm_manager = IlmManager(client)
    indices = index_manager.list(index_pattern or "*")
    targets = _select_explain_targets(indices, health_report)

    if index_pattern:
        import fnmatch

        targets = {
            name
            for name in targets
            if fnmatch.fnmatchcase(name, index_pattern)
        }

    health_by_index = {
        str(entry.get("index", "")): str(entry.get("health", "unknown")).lower()
        for entry in indices
        if isinstance(entry, dict)
    }

    stuck: List[StuckIlmIndex] = []
    for index_name in sorted(targets)[:limit]:
        try:
            explain = ilm_manager.explain_lifecycle(index_name)
        except Exception as exc:
            logger.debug("Skipping ILM explain for %s: %s", index_name, exc)
            continue

        issue = _lifecycle_issue(explain)
        if issue is None:
            continue

        stuck.append(
            StuckIlmIndex(
                index_name=index_name,
                health=health_by_index.get(index_name, "unknown"),
                issue=issue,
                step=str(explain.get("step", "")),
                explain=explain,
            )
        )

    logger.info("ILM stuck scan complete: targets=%s stuck=%s", len(targets), len(stuck))
    return stuck