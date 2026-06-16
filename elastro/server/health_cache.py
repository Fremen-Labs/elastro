"""In-memory TTL cache for health assessment reports (GUI API)."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, List, Optional

from elastro.health.models import AssessmentReport

DEFAULT_TTL_SECONDS = 60
MAX_HISTORY = 20


@dataclass
class _CacheEntry:
    report: AssessmentReport
    expires_at: float


_assessment_cache: Dict[str, _CacheEntry] = {}
_history: Dict[str, Deque[Dict[str, Any]]] = {}


def get_cached_report(cluster_name: str) -> Optional[AssessmentReport]:
    """Return a cached assessment if still valid."""
    entry = _assessment_cache.get(cluster_name)
    if entry is None:
        return None
    if time.monotonic() >= entry.expires_at:
        _assessment_cache.pop(cluster_name, None)
        return None
    return entry.report


def store_report(
    cluster_name: str,
    report: AssessmentReport,
    *,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> None:
    """Cache an assessment and append to per-cluster history."""
    _assessment_cache[cluster_name] = _CacheEntry(
        report=report,
        expires_at=time.monotonic() + ttl_seconds,
    )
    payload = report.model_dump(mode="json")
    payload.pop("raw_health_report", None)
    history = _history.setdefault(cluster_name, deque(maxlen=MAX_HISTORY))
    history.appendleft(payload)


def get_history(cluster_name: str, *, limit: int = 10) -> List[Dict[str, Any]]:
    """Return recent cached assessment snapshots for a cluster."""
    items = list(_history.get(cluster_name, []))
    return items[:limit]


def clear_cache(cluster_name: Optional[str] = None) -> None:
    """Clear cache entries (used in tests)."""
    if cluster_name is None:
        _assessment_cache.clear()
        _history.clear()
        return
    _assessment_cache.pop(cluster_name, None)
    _history.pop(cluster_name, None)