"""Health assessment and remediation audit logging."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from elastro.core.client import ElasticsearchClient
from elastro.core.logger import get_logger
from elastro.health.config import AUDIT_INDEX_MAPPINGS, DEFAULT_AUDIT_INDEX
from elastro.health.history import ensure_index
from elastro.health.models import AssessmentReport
from elastro.health.remediation.models import RemediationResult
from elastro.health.remediation.rollback import RollbackRecord

logger = get_logger(__name__)


class HealthAuditLogger:
    """Emit structured health events to logs and optionally an ES audit index."""

    def __init__(
        self,
        client: Optional[ElasticsearchClient] = None,
        *,
        audit_index: str = DEFAULT_AUDIT_INDEX,
        profile: str = "default",
        host: str = "unknown",
    ) -> None:
        self._client = client
        self._audit_index = audit_index
        self._profile = profile
        self._host = host

    def log_event(
        self,
        event_type: str,
        session_id: str,
        payload: Dict[str, Any],
        *,
        cluster_name: Optional[str] = None,
    ) -> None:
        """Log a health event to stderr and optionally index it."""
        logger.info(
            "health.%s session_id=%s cluster=%s profile=%s",
            event_type,
            session_id,
            cluster_name or "unknown",
            self._profile,
        )
        logger.debug(
            "health audit payload event=%s session_id=%s keys=%s",
            event_type,
            session_id,
            sorted(payload.keys()),
        )

        if self._client is None:
            return

        document = {
            "event_type": event_type,
            "session_id": session_id,
            "cluster_name": cluster_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "profile": self._profile,
            "host": self._host,
            "payload": payload,
        }
        document.update(
            {
                key: payload[key]
                for key in (
                    "action_id",
                    "index_name",
                    "rollback_id",
                    "success",
                    "dry_run",
                )
                if key in payload
            }
        )

        try:
            ensure_index(self._client, self._audit_index, AUDIT_INDEX_MAPPINGS)
            self._client.client.index(
                index=self._audit_index,
                document=document,
            )
        except Exception as exc:
            logger.warning(
                "Failed to index health audit event type=%s: %s",
                event_type,
                exc,
                exc_info=True,
            )

    def log_assess(self, report: AssessmentReport) -> None:
        """Record a completed health assessment."""
        payload = {
            "overall_score": report.overall_score,
            "overall_status": report.overall_status.value,
            "findings_count": len(report.findings),
            "duration_ms": report.duration_ms,
            "elasticsearch_version": report.elasticsearch_version,
            "collectors_run": report.collectors_run,
            "collectors_failed": report.collectors_failed,
        }
        self.log_event(
            "assess",
            report.session_id,
            payload,
            cluster_name=report.cluster_name,
        )

    def log_fix(self, result: RemediationResult, *, session_id: str) -> None:
        """Record a remediation attempt."""
        payload = {
            "action_id": result.action_id,
            "index_name": result.index_name,
            "rollback_id": result.rollback_id,
            "success": result.success,
            "dry_run": result.dry_run,
            "executed": result.executed,
            "message": result.message,
        }
        self.log_event("fix", session_id, payload)

    def log_rollback(
        self,
        record: RollbackRecord,
        *,
        dry_run: bool,
        success: bool,
        message: str,
    ) -> None:
        """Record a rollback operation."""
        payload = {
            "rollback_id": record.rollback_id,
            "action_id": record.action_id,
            "index_name": record.index_name,
            "dry_run": dry_run,
            "success": success,
            "message": message,
        }
        self.log_event(
            "rollback",
            record.session_id,
            payload,
            cluster_name=record.cluster_name,
        )