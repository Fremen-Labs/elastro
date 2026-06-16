"""Assessment history indexing and retrieval."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urlunparse

from elastro.core.client import ElasticsearchClient
from elastro.core.errors import OperationError
from elastro.core.logger import get_logger
from elastro.health.config import (
    ASSESSMENT_INDEX_MAPPINGS,
    DEFAULT_HISTORY_INDEX,
)
from elastro.health.models import AssessmentReport

logger = get_logger(__name__)

_WINDOW_PATTERN = re.compile(r"^(\d+)([dhm])$", re.IGNORECASE)
_WINDOW_UNITS = {"d": "days", "h": "hours", "m": "minutes"}
_MISSING_INDEX_MARKERS = ("index_not_found", "no such index")


def _is_missing_history_index(exc: Exception) -> bool:
    """Return True when the assessment history index has not been created yet."""
    message = str(exc).lower()
    return any(marker in message for marker in _MISSING_INDEX_MARKERS)


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


def sanitize_host(host: str) -> str:
    """Strip credentials from host URLs before indexing."""
    if not host or host == "unknown":
        return "unknown"
    try:
        normalized = host if "://" in host else f"http://{host}"
        parsed = urlparse(normalized)
        hostname = parsed.hostname or ""
        if not hostname:
            return "unknown"
        netloc = hostname
        if parsed.port:
            netloc = f"{hostname}:{parsed.port}"
        return urlunparse((parsed.scheme or "http", netloc, "", "", "", ""))
    except Exception:
        logger.debug("Failed to sanitize host=%s", host, exc_info=True)
        return "unknown"


def parse_window(window: str) -> timedelta:
    """Parse a duration string such as ``7d``, ``24h``, or ``30m``."""
    match = _WINDOW_PATTERN.match(str(window).strip())
    if not match:
        raise ValueError(
            f"Invalid window '{window}'. Use formats like 7d, 24h, or 30m."
        )
    amount = int(match.group(1))
    unit = match.group(2).lower()
    return timedelta(**{_WINDOW_UNITS[unit]: amount})


def filter_records_by_window(
    records: List[Dict[str, Any]],
    window: str,
) -> List[Dict[str, Any]]:
    """Keep assessment records whose ``assessed_at`` falls inside ``window``."""
    cutoff = datetime.now(timezone.utc) - parse_window(window)
    filtered: List[Dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        assessed_at = _parse_assessed_at(record.get("assessed_at"))
        if assessed_at is None or assessed_at < cutoff:
            continue
        filtered.append(record)
    return filtered


def ensure_index(
    client: ElasticsearchClient,
    index_name: str,
    mappings: Dict[str, Any],
) -> None:
    """Create an index with mappings when it does not exist."""
    es = client.client
    try:
        exists_response = es.indices.exists(index=index_name)
        if hasattr(exists_response, "body"):
            index_exists = bool(exists_response.body)
        else:
            index_exists = bool(exists_response)
        if index_exists:
            return
        es.indices.create(index=index_name, body=mappings)
        logger.info("Created health index=%s", index_name)
    except Exception as exc:
        logger.error(
            "Failed to ensure health index=%s: %s",
            index_name,
            exc,
            exc_info=True,
        )
        raise


def assessment_document(
    report: AssessmentReport,
    *,
    profile: str = "default",
    host: str = "unknown",
) -> Dict[str, Any]:
    """Build an Elasticsearch document for an assessment report."""
    payload = report.model_dump(mode="json")
    payload.pop("raw_health_report", None)
    payload["profile"] = profile
    payload["host"] = sanitize_host(host)
    return payload


def index_assessment(
    client: ElasticsearchClient,
    report: AssessmentReport,
    *,
    history_index: str = DEFAULT_HISTORY_INDEX,
    profile: str = "default",
    host: str = "unknown",
) -> None:
    """Index an assessment report into the history index."""
    ensure_index(client, history_index, ASSESSMENT_INDEX_MAPPINGS)
    document = assessment_document(report, profile=profile, host=host)
    try:
        client.client.index(
            index=history_index,
            id=report.session_id,
            document=document,
        )
        logger.info(
            "Indexed assessment history session_id=%s cluster=%s index=%s",
            report.session_id,
            report.cluster_name,
            history_index,
        )
    except Exception as exc:
        logger.error(
            "Failed to index assessment session_id=%s: %s",
            report.session_id,
            exc,
            exc_info=True,
        )
        raise


def _history_query_filters(
    *,
    cluster_name: Optional[str] = None,
    profile: Optional[str] = None,
    window: Optional[str] = None,
    finding_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    filters: List[Dict[str, Any]] = []
    if cluster_name:
        filters.append({"term": {"cluster_name": cluster_name}})
    if profile:
        filters.append({"term": {"profile": profile}})
    if window:
        cutoff = datetime.now(timezone.utc) - parse_window(window)
        filters.append({"range": {"assessed_at": {"gte": cutoff.isoformat()}}})
    if finding_id:
        filters.append(
            {
                "nested": {
                    "path": "findings",
                    "query": {"term": {"findings.id": finding_id}},
                }
            }
        )
    return filters


def query_assessment_history(
    client: ElasticsearchClient,
    *,
    history_index: str = DEFAULT_HISTORY_INDEX,
    cluster_name: Optional[str] = None,
    profile: Optional[str] = None,
    window: Optional[str] = None,
    finding_id: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Return recent assessment documents from the history index."""
    query: Dict[str, Any] = {
        "size": limit,
        "sort": [{"assessed_at": {"order": "desc"}}],
    }
    filters = _history_query_filters(
        cluster_name=cluster_name,
        profile=profile,
        window=window,
        finding_id=finding_id,
    )
    if filters:
        query["query"] = {"bool": {"filter": filters}}

    try:
        response = client.client.search(index=history_index, body=query)
        hits = response.get("hits", {}).get("hits", [])
        if not isinstance(hits, list):
            logger.warning(
                "Unexpected assessment history response index=%s hits_type=%s",
                history_index,
                type(hits).__name__,
            )
            return []
        return [hit.get("_source", {}) for hit in hits if isinstance(hit, dict)]
    except Exception as exc:
        if _is_missing_history_index(exc):
            logger.debug("Assessment history index missing index=%s", history_index)
            return []
        logger.error(
            "Failed to query assessment history index=%s: %s",
            history_index,
            exc,
            exc_info=True,
        )
        raise OperationError(
            f"Failed to query assessment history index={history_index}: {exc}"
        ) from exc


def history_cluster_summary(
    client: ElasticsearchClient,
    *,
    history_index: str = DEFAULT_HISTORY_INDEX,
    window: str = "7d",
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Return per-cluster score aggregates for fleet trend views."""
    cutoff = datetime.now(timezone.utc) - parse_window(window)
    body = {
        "size": 0,
        "query": {
            "bool": {
                "filter": [
                    {"range": {"assessed_at": {"gte": cutoff.isoformat()}}},
                ]
            }
        },
        "aggs": {
            "by_cluster": {
                "terms": {"field": "cluster_name", "size": limit},
                "aggs": {
                    "latest": {
                        "top_hits": {
                            "size": 1,
                            "sort": [{"assessed_at": {"order": "desc"}}],
                            "_source": {
                                "includes": [
                                    "cluster_name",
                                    "overall_score",
                                    "overall_status",
                                    "assessed_at",
                                ]
                            },
                        }
                    },
                    "avg_score": {"avg": {"field": "overall_score"}},
                    "sample_count": {"value_count": {"field": "overall_score"}},
                },
            }
        },
    }
    try:
        response = client.client.search(index=history_index, body=body)
    except Exception as exc:
        if _is_missing_history_index(exc):
            logger.debug(
                "Fleet history summary unavailable; index missing index=%s",
                history_index,
            )
            return []
        logger.error(
            "Failed to query fleet history summary index=%s: %s",
            history_index,
            exc,
            exc_info=True,
        )
        raise OperationError(
            f"Failed to query fleet history summary index={history_index}: {exc}"
        ) from exc

    buckets = response.get("aggregations", {}).get("by_cluster", {}).get("buckets", [])
    summary: List[Dict[str, Any]] = []
    for bucket in buckets:
        if not isinstance(bucket, dict):
            continue
        latest_hit = (
            bucket.get("latest", {})
            .get("hits", {})
            .get("hits", [{}])[0]
            .get("_source", {})
        )
        summary.append(
            {
                "cluster_name": bucket.get("key"),
                "sample_count": bucket.get("sample_count", {}).get("value", 0),
                "avg_score": round(bucket.get("avg_score", {}).get("value") or 0, 1),
                "latest_score": latest_hit.get("overall_score"),
                "latest_status": latest_hit.get("overall_status"),
                "latest_assessed_at": latest_hit.get("assessed_at"),
            }
        )
    summary.sort(key=lambda item: str(item.get("cluster_name", "")))
    return summary
