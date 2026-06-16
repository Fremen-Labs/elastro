"""Health assessment configuration defaults."""

from __future__ import annotations

from typing import Any, Dict

DEFAULT_HISTORY_INDEX = "elastro-health-assessments"
DEFAULT_AUDIT_INDEX = "elastro-health-audit"
DEFAULT_ENABLE_HISTORY = False

ASSESSMENT_INDEX_MAPPINGS: Dict[str, Any] = {
    "mappings": {
        "properties": {
            "session_id": {"type": "keyword"},
            "cluster_name": {"type": "keyword"},
            "assessed_at": {"type": "date"},
            "overall_score": {"type": "integer"},
            "overall_status": {"type": "keyword"},
            "findings": {"type": "nested"},
            "elasticsearch_version": {"type": "keyword"},
            "profile": {"type": "keyword"},
            "host": {"type": "keyword"},
            "duration_ms": {"type": "integer"},
        }
    }
}

AUDIT_INDEX_MAPPINGS: Dict[str, Any] = {
    "mappings": {
        "properties": {
            "event_type": {"type": "keyword"},
            "session_id": {"type": "keyword"},
            "cluster_name": {"type": "keyword"},
            "timestamp": {"type": "date"},
            "action_id": {"type": "keyword"},
            "index_name": {"type": "keyword"},
            "rollback_id": {"type": "keyword"},
            "success": {"type": "boolean"},
            "dry_run": {"type": "boolean"},
            "profile": {"type": "keyword"},
            "host": {"type": "keyword"},
            "payload": {"type": "object", "enabled": True},
        }
    }
}
