"""Persistent yellow cluster rule — yellow status sustained over time."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from elastro.core.logger import get_logger
from elastro.health.models import Finding, FindingStatus, Severity
from elastro.health.rules.engine import RuleContext

logger = get_logger(__name__)

DEFAULT_PERSISTENT_HOURS = 4.0


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


def _record_indicates_yellow(record: Dict[str, Any]) -> bool:
    for finding in record.get("findings", []):
        if not isinstance(finding, dict):
            continue
        finding_id = str(finding.get("id", ""))
        if finding_id.startswith("cluster.status.yellow"):
            return True
        if (
            finding.get("indicator") == "shards_availability"
            and finding.get("status") in {"warn", "fail"}
        ):
            return True

    overall_status = str(record.get("overall_status", "")).lower()
    overall_score = record.get("overall_score", 100)
    try:
        score = int(overall_score)
    except (TypeError, ValueError):
        score = 100
    return overall_status == "warn" and score <= 80


def persistent_yellow_findings(
    ctx: RuleContext,
    *,
    hours_threshold: float = DEFAULT_PERSISTENT_HOURS,
) -> List[Finding]:
    """Emit a finding when the cluster has remained yellow beyond the threshold."""
    cluster_status = str(
        (ctx.collector_data.get("cluster_health") or {}).get("status", "green")
    ).lower()
    if cluster_status != "yellow":
        return []

    history = ctx.assessment_history
    if len(history) < 2:
        return []

    yellow_streak: List[Dict[str, Any]] = []
    for record in history:
        if _record_indicates_yellow(record):
            yellow_streak.append(record)
        else:
            break

    if len(yellow_streak) < 2:
        return []

    newest_at = _parse_assessed_at(yellow_streak[0].get("assessed_at"))
    oldest_at = _parse_assessed_at(yellow_streak[-1].get("assessed_at"))
    if newest_at is None or oldest_at is None:
        return []

    duration = newest_at - oldest_at
    required = timedelta(hours=hours_threshold)
    if duration < required:
        return []

    hours = round(duration.total_seconds() / 3600, 1)
    cluster_name = ctx.cluster_name
    logger.info(
        "Persistent yellow detected for cluster=%s duration_hours=%s threshold=%s",
        cluster_name,
        hours,
        hours_threshold,
    )
    return [
        Finding(
            id="cluster.persistent_yellow",
            category="cluster",
            title="Cluster persistently yellow",
            status=FindingStatus.WARN,
            severity=Severity.HIGH,
            score_impact=8,
            summary=(
                f"Cluster '{cluster_name}' has been yellow for approximately "
                f"{hours} hour(s) across {len(yellow_streak)} recent assessments."
            ),
            affected_resources=[cluster_name],
            source="rule",
            metadata={
                "duration_hours": hours,
                "threshold_hours": hours_threshold,
                "assessments_in_streak": len(yellow_streak),
            },
        )
    ]