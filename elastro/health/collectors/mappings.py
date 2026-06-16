"""Index mapping field-count collector for mapping explosion detection."""

from __future__ import annotations

from typing import Any, Dict, List

from elastro.core.errors import OperationError
from elastro.core.index import IndexManager
from elastro.core.logger import get_logger
from elastro.health.collectors.base import CollectContext, CollectorResult
from elastro.health.mappings import (
    _MAX_INDICES,
    is_system_index,
    summarize_index_mapping,
)

logger = get_logger(__name__)


class MappingsCollector:
    """Sample user indices and count mapped fields."""

    name = "mappings"

    def collect(self, ctx: CollectContext) -> CollectorResult:
        index_manager = IndexManager(ctx.client)
        max_indices = int(ctx.options.get("max_indices", _MAX_INDICES))
        logger.debug("Collecting mapping field counts max_indices=%s", max_indices)

        try:
            indices = index_manager.list()
            summaries = self._summaries(index_manager, indices, max_indices=max_indices)
            logger.info(
                "Mappings collector complete: scanned=%s indices",
                len(summaries),
            )
            return CollectorResult(
                name=self.name,
                status="ok",
                data={
                    "indices": summaries,
                    "scanned_count": len(summaries),
                },
            )
        except OperationError as exc:
            logger.error("Mappings collector failed: %s", exc, exc_info=True)
            return CollectorResult(name=self.name, status="error", error=str(exc))

    def _summaries(
        self,
        index_manager: IndexManager,
        indices: List[Dict[str, Any]],
        *,
        max_indices: int,
    ) -> List[Dict[str, Any]]:
        summaries: List[Dict[str, Any]] = []
        for entry in indices:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("index", "")).strip()
            if not name or is_system_index(name):
                continue
            try:
                raw = index_manager.get(name)
            except OperationError as exc:
                logger.debug("Skipping mapping scan for %s: %s", name, exc)
                continue

            if isinstance(raw, dict) and name in raw:
                body = raw[name]
            elif isinstance(raw, dict):
                body = next(iter(raw.values()), {})
            else:
                continue

            summaries.append(summarize_index_mapping(name, body))
            if len(summaries) >= max_indices:
                break
        return summaries