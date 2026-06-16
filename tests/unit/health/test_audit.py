"""Unit tests for health audit logging."""

from unittest.mock import MagicMock

from elastro.health.audit import HealthAuditLogger
from elastro.health.models import AssessmentReport, FindingStatus
from elastro.health.remediation.models import RemediationResult


class TestHealthAuditLogger:
    def test_log_assess_emits_without_client(self):
        logger = HealthAuditLogger(client=None)
        report = AssessmentReport(
            cluster_name="docker-cluster",
            overall_score=88,
            overall_status=FindingStatus.WARN,
        )
        logger.log_assess(report)

    def test_log_fix_indexes_when_client_available(self):
        client = MagicMock()
        client.client.indices.exists.return_value = True
        client.client.index.return_value = {"result": "created"}
        logger = HealthAuditLogger(client)
        result = RemediationResult(
            action_id="reduce_replicas",
            index_name="logs-2024",
            success=True,
            executed=True,
            message="done",
            rollback_id="rb-1",
        )
        logger.log_fix(result, session_id="sess-1")
        client.client.index.assert_called()