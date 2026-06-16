"""Assessment history trend intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from elastro.core.client import ElasticsearchClient
from elastro.core.errors import OperationError
from elastro.core.logger import get_logger
from elastro.health.config import DEFAULT_HISTORY_INDEX
from elastro.health.history import parse_window, query_assessment_history
from elastro.health.rules.persistent_yellow import _record_indicates_yellow

logger = get_logger(__name__)

_RECURRING_THRESHOLD = 0.5


@dataclass
class HistoryPoint:
    """Single score sample for sparkline and delta calculations."""

    assessed_at: str
    overall_score: int
    overall_status: str


@dataclass
class TrendReport:
    """Aggregated trend view for a cluster over a time window."""

    cluster_name: str
    window: str
    sample_count: int
    points: List[HistoryPoint] = field(default_factory=list)
    score_delta_7d: Optional[int] = None
    recurring_findings: List[str] = field(default_factory=list)
    persistent_yellow_count: int = 0
    source: str = "history_index"
    message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_name": self.cluster_name,
            "window": self.window,
            "sample_count": self.sample_count,
            "points": [
                {
                    "assessed_at": point.assessed_at,
                    "overall_score": point.overall_score,
                    "overall_status": point.overall_status,
                }
                for point in self.points
            ],
            "score_delta_7d": self.score_delta_7d,
            "recurring_findings": self.recurring_findings,
            "persistent_yellow_count": self.persistent_yellow_count,
            "source": self.source,
            "message": self.message,
        }


def _parse_assessed_at(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _score_delta(points: List[HistoryPoint], *, window: timedelta) -> Optional[int]:
    if len(points) < 2:
        return None

    parsed: List[tuple[datetime, int]] = []
    for point in points:
        assessed_at = _parse_assessed_at(point.assessed_at)
        if assessed_at is not None:
            parsed.append((assessed_at, point.overall_score))

    if len(parsed) < 2:
        return None

    parsed.sort(key=lambda item: item[0])
    newest_at, newest_score = parsed[-1]
    cutoff = newest_at - window
    baseline_score = parsed[0][1]
    for assessed_at, score in parsed:
        if assessed_at >= cutoff:
            baseline_score = score
            break

    return newest_score - baseline_score


def recurring_finding_ids(
    records: List[Dict[str, Any]],
    *,
    finding_filter: Optional[str] = None,
) -> List[str]:
    if not records:
        return []

    counts: Dict[str, int] = {}
    for record in records:
        seen_in_record: set[str] = set()
        for finding in record.get("findings", []):
            if not isinstance(finding, dict):
                continue
            status = str(finding.get("status", "")).lower()
            if status in {"pass", "skipped"}:
                continue
            finding_id = str(finding.get("id", "")).strip()
            if not finding_id:
                continue
            if finding_filter and finding_id != finding_filter:
                continue
            seen_in_record.add(finding_id)
        for finding_id in seen_in_record:
            counts[finding_id] = counts.get(finding_id, 0) + 1

    threshold = max(1, int(len(records) * _RECURRING_THRESHOLD))
    recurring = [
        finding_id
        for finding_id, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        if count >= threshold
    ]
    if finding_filter:
        return [finding_id for finding_id in recurring if finding_id == finding_filter]
    return recurring


def compute_trends(
    client: ElasticsearchClient,
    *,
    history_index: str = DEFAULT_HISTORY_INDEX,
    cluster_name: Optional[str] = None,
    window: str = "7d",
    limit: int = 50,
    finding_id: Optional[str] = None,
) -> TrendReport:
    """Compute score trends and recurring findings from assessment history."""
    resolved_cluster = cluster_name or "all"
    logger.info(
        "Computing health trends cluster=%s window=%s limit=%s finding=%s",
        resolved_cluster,
        window,
        limit,
        finding_id,
    )

    try:
        records = query_assessment_history(
            client,
            history_index=history_index,
            cluster_name=cluster_name,
            window=window,
            limit=limit,
            finding_id=finding_id,
        )
    except OperationError:
        raise
    except Exception as exc:
        logger.error(
            "Failed to query assessment history for trends cluster=%s: %s",
            resolved_cluster,
            exc,
            exc_info=True,
        )
        raise OperationError(
            f"Failed to compute health trends for cluster={resolved_cluster}: {exc}"
        ) from exc

    if not records:
        return TrendReport(
            cluster_name=resolved_cluster,
            window=window,
            sample_count=0,
            message=(
                "No assessment history found. Run "
                "`elastro health assess --history` to populate the index."
            ),
        )

    points = [
        HistoryPoint(
            assessed_at=str(record.get("assessed_at", "")),
            overall_score=int(record.get("overall_score") or 0),
            overall_status=str(record.get("overall_status", "unknown")),
        )
        for record in records
    ]
    points.reverse()

    delta_window = parse_window("7d")
    recurring = recurring_finding_ids(records, finding_filter=finding_id)
    yellow_count = sum(1 for record in records if _record_indicates_yellow(record))

    return TrendReport(
        cluster_name=str(records[0].get("cluster_name", resolved_cluster)),
        window=window,
        sample_count=len(records),
        points=points,
        score_delta_7d=_score_delta(points, window=delta_window),
        recurring_findings=recurring,
        persistent_yellow_count=yellow_count,
    )


def compute_trends_from_records(
    records: List[Dict[str, Any]],
    *,
    cluster_name: str,
    window: str = "7d",
    finding_id: Optional[str] = None,
    source: str = "cache",
) -> TrendReport:
    """Build a trend report from in-memory assessment snapshots."""
    if not records:
        return TrendReport(
            cluster_name=cluster_name,
            window=window,
            sample_count=0,
            source=source,
            message=(
                "No assessment history found. Run "
                "`elastro health assess --history` to populate the index."
            ),
        )

    points = [
        HistoryPoint(
            assessed_at=str(record.get("assessed_at", "")),
            overall_score=int(record.get("overall_score") or 0),
            overall_status=str(record.get("overall_status", "unknown")),
        )
        for record in reversed(records)
    ]
    delta_window = parse_window("7d")
    return TrendReport(
        cluster_name=cluster_name,
        window=window,
        sample_count=len(records),
        points=points,
        score_delta_7d=_score_delta(points, window=delta_window),
        recurring_findings=recurring_finding_ids(
            records,
            finding_filter=finding_id,
        ),
        persistent_yellow_count=sum(
            1 for record in records if _record_indicates_yellow(record)
        ),
        source=source,
    )