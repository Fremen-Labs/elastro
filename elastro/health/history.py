"""Assessment history indexing and retrieval."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from elastro.core.client import ElasticsearchClient
from elastro.core.logger import get_logger
from elastro.health.config import (
    ASSESSMENT_INDEX_MAPPINGS,
    DEFAULT_HISTORY_INDEX,
)
from elastro.health.models import AssessmentReport

logger = get_logger(__name__)


def ensure_index(
    client: ElasticsearchClient,
    index_name: str,
    mappings: Dict[str, Any],
) -> None:
    """Create an index with mappings when it does not exist."""
    es = client.client
    try:
        exists = es.indices.exists(index=index_name)
        if hasattr(exists, "body"):
            exists = bool(exists.body)
        if exists:
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
    payload["host"] = host
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


def query_assessment_history(
    client: ElasticsearchClient,
    *,
    history_index: str = DEFAULT_HISTORY_INDEX,
    cluster_name: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Return recent assessment documents from the history index."""
    query: Dict[str, Any] = {
        "size": limit,
        "sort": [{"assessed_at": {"order": "desc"}}],
    }
    if cluster_name:
        query["query"] = {"term": {"cluster_name": cluster_name}}

    try:
        response = client.client.search(index=history_index, body=query)
        hits = response.get("hits", {}).get("hits", [])
        return [hit.get("_source", {}) for hit in hits if isinstance(hit, dict)]
    except Exception as exc:
        logger.error(
            "Failed to query assessment history index=%s: %s",
            history_index,
            exc,
            exc_info=True,
        )
        raise