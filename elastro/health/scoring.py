"""Weighted health scoring from Elasticsearch health report indicators."""

from __future__ import annotations

from typing import Any, Dict, Optional

from elastro.health.models import FindingStatus, cluster_status_to_score

DEFAULT_WEIGHTS: Dict[str, int] = {
    "master_is_stable": 20,
    "shards_availability": 20,
    "disk": 15,
    "shards_capacity": 10,
    "ilm": 8,
    "slm": 5,
    "repository_integrity": 7,
    "data_stream_lifecycle": 5,
    "file_settings": 3,
}

_INDICATOR_STATUS_SCORE = {
    "green": 100,
    "yellow": 50,
    "red": 0,
    "unknown": 75,
    "unavailable": 0,
}


def indicator_status_score(status: str) -> int:
    """Map an indicator status color to a 0-100 sub-score."""
    return _INDICATOR_STATUS_SCORE.get(status, 75)


def compute_weighted_score(
    indicators: Dict[str, Any],
    weights: Optional[Dict[str, int]] = None,
) -> int:
    """Compute a weighted 0-100 score from health report indicators."""
    weight_map = weights or DEFAULT_WEIGHTS
    if not indicators:
        return 0

    total_weight = 0
    weighted_sum = 0

    for name, weight in weight_map.items():
        body = indicators.get(name)
        if body is None or not isinstance(body, dict):
            status = "unknown"
        else:
            status = body.get("status", "unknown")
        weighted_sum += weight * indicator_status_score(status)
        total_weight += weight

    if total_weight == 0:
        return 0

    return int(round(weighted_sum / total_weight))


def compute_fallback_score(cluster_status: str) -> int:
    """Fallback score when _health_report is unavailable."""
    return cluster_status_to_score(cluster_status)
