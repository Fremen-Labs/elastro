"""Collector for APM and Beats index, ILM, stats, and freshness signals."""

from __future__ import annotations

from typing import Any, Dict, List

from elastro.core.datastream import DatastreamManager
from elastro.core.document import DocumentManager
from elastro.core.errors import DocumentError, OperationError
from elastro.core.ilm import IlmManager
from elastro.core.index import IndexManager
from elastro.core.logger import get_logger
from elastro.health.collectors.base import CollectContext, CollectorResult
from elastro.health.manager import HealthManager

logger = get_logger(__name__)

_INDEX_PATTERNS = (
    "traces-apm*",
    "metrics-apm*",
    "logs-apm*",
    "filebeat-*",
    "metricbeat-*",
)
_APM_SEARCH = "traces-apm*,metrics-apm*,logs-apm*"
_BEATS_SEARCH = "filebeat-*,metricbeat-*"
_MAX_EXPLAIN = 20
_MISSING_INDEX_MARKERS = ("index_not_found", "no such index")


class ApmBeatsCollector:
    """Collect APM/Beats streams, ILM explain, indexing stats, and freshness."""

    name = "apm_beats"

    def collect(self, ctx: CollectContext) -> CollectorResult:
        try:
            data = _collect(ctx)
        except Exception as exc:
            logger.error("APM/Beats collector failed: %s", exc, exc_info=True)
            return CollectorResult(name=self.name, status="error", error=str(exc))
        logger.info(
            "APM/Beats collector complete: indices=%s streams=%s",
            len(data.get("indices") or []),
            len(data.get("data_streams") or []),
        )
        return CollectorResult(name=self.name, status="ok", data=data)


def _collect(ctx: CollectContext) -> Dict[str, Any]:
    index_manager = IndexManager(ctx.client)
    datastreams = DatastreamManager(ctx.client)
    ilm_manager = IlmManager(ctx.client)
    documents = DocumentManager(ctx.client)
    health_manager = HealthManager(ctx.client)

    indices = _unique_indices(
        [_list_indices(index_manager, pattern) for pattern in _INDEX_PATTERNS]
    )
    streams = _unique_streams(
        [_list_streams(datastreams, pattern) for pattern in _INDEX_PATTERNS]
    )
    explains: Dict[str, Any] = {}
    for entry in indices[:_MAX_EXPLAIN]:
        name = str(entry.get("index") or "").strip()
        if not name:
            continue
        try:
            explains[name] = ilm_manager.explain_lifecycle(name)
        except OperationError as exc:
            logger.debug("Skipping ILM explain for %s: %s", name, exc)

    stats: Dict[str, Any] = {}
    try:
        raw_stats = health_manager.index_stats(",".join(_INDEX_PATTERNS))
        maybe_indices = (
            raw_stats.get("indices") if isinstance(raw_stats, dict) else None
        )
        if isinstance(maybe_indices, dict):
            stats = maybe_indices
    except OperationError as exc:
        logger.debug("APM/Beats index stats unavailable: %s", exc)

    return {
        "indices": indices,
        "data_streams": streams,
        "ilm": explains,
        "stats": stats,
        "freshness": {
            "apm": _freshness(documents, _APM_SEARCH),
            "beats": _freshness(documents, _BEATS_SEARCH),
        },
    }


def _list_indices(manager: IndexManager, pattern: str) -> List[Dict[str, Any]]:
    try:
        rows = manager.list(pattern)
    except Exception as exc:
        logger.debug("Index list failed for %s: %s", pattern, exc)
        return []
    return [row for row in rows if isinstance(row, dict)]


def _list_streams(manager: DatastreamManager, pattern: str) -> List[Dict[str, Any]]:
    try:
        rows = manager.list(pattern)
    except Exception as exc:
        logger.debug("Data stream list failed for %s: %s", pattern, exc)
        return []
    return [row for row in rows if isinstance(row, dict)]


def _unique_indices(groups: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []
    for group in groups:
        for row in group:
            name = str(row.get("index") or "")
            if not name or name in seen:
                continue
            seen.add(name)
            out.append(row)
    return out


def _unique_streams(groups: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []
    for group in groups:
        for row in group:
            name = str(row.get("name") or "")
            if not name or name in seen:
                continue
            seen.add(name)
            out.append(row)
    return out


def _freshness(documents: DocumentManager, pattern: str) -> Dict[str, Any]:
    try:
        raw = documents.search(
            index=pattern,
            query={"range": {"@timestamp": {"gte": "now-15m"}}},
            options={"size": 0, "track_total_hits": 1},
        )
    except DocumentError as exc:
        if _is_missing_index(exc):
            return {"doc_count": 0}
        logger.debug("Freshness search failed for %s: %s", pattern, exc)
        return {"doc_count": 0, "error": "search_failed"}
    except Exception as exc:
        logger.debug("Freshness search failed for %s: %s", pattern, exc)
        return {"doc_count": 0, "error": "search_failed"}
    if not isinstance(raw, dict):
        return {"doc_count": 0}
    total = (raw.get("hits") or {}).get("total", 0)
    if isinstance(total, dict):
        count = int(total.get("value") or 0)
    else:
        try:
            count = int(total or 0)
        except (TypeError, ValueError):
            count = 0
    return {"doc_count": count}


def _is_missing_index(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in _MISSING_INDEX_MARKERS)
