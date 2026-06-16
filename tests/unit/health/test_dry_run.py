"""Unit tests for dry-run contract and preview safety."""

from unittest.mock import MagicMock, patch

import pytest

from elastro.health.audit import HealthAuditLogger
from elastro.health.remediation.dry_run import (
    assert_no_executions,
    fix_run_payload,
    is_preview_mode,
    planned_rollback_call,
    summarize_fix_run,
)
from elastro.health.remediation.executor import RemediationExecutor
from elastro.health.remediation.models import FixRunResult, IndexDiagnosis, PlannedAction, RemediationResult
from elastro.health.models import RemediationSafety


class TestDryRunContract:
    def test_is_preview_mode(self):
        assert is_preview_mode(dry_run=True) is True
        assert is_preview_mode(plan_only=True) is True
        assert is_preview_mode(dry_run=False, plan_only=False) is False

    def test_planned_rollback_call(self):
        planned = planned_rollback_call(
            "logs-2024",
            {"index": {"number_of_replicas": 1}},
        )
        assert planned.startswith("PUT /logs-2024/_settings body=")

    def test_fix_run_payload_includes_summary(self):
        result = FixRunResult(
            diagnoses=[
                IndexDiagnosis(
                    index_name="logs-2024",
                    health="yellow",
                    suggested_action_id="reduce_replicas",
                )
            ],
            planned_actions=[
                PlannedAction(
                    action_id="reduce_replicas",
                    label="Reduce replicas",
                    safety=RemediationSafety.DESTRUCTIVE,
                    impact="HA loss",
                    index_name="logs-2024",
                    planned_api_call="PUT /logs-2024/_settings body={'index': {'number_of_replicas': 0}}",
                )
            ],
            results=[
                RemediationResult(
                    action_id="reduce_replicas",
                    index_name="logs-2024",
                    success=True,
                    executed=False,
                    dry_run=True,
                    message="Reduce replicas",
                    planned_api_call="PUT /logs-2024/_settings body={'index': {'number_of_replicas': 0}}",
                )
            ],
            dry_run=True,
        )
        payload = fix_run_payload(result)
        assert payload["summary"]["preview_only"] is True
        assert payload["summary"]["executed_count"] == 0
        assert payload["summary"]["planned_action_count"] == 1

    def test_assert_no_executions_raises_on_mutation(self):
        with pytest.raises(RuntimeError, match="Dry-run executed mutations"):
            assert_no_executions(
                [
                    RemediationResult(
                        action_id="reduce_replicas",
                        index_name="logs-2024",
                        success=True,
                        executed=True,
                        dry_run=False,
                        message="done",
                    )
                ]
            )


class TestDryRunExecutorSafety:
    def test_dry_run_never_calls_catalog_execute_or_save_rollback(self):
        client = MagicMock()
        with patch(
            "elastro.health.remediation.executor.RemediationCatalog.execute",
        ) as mock_execute:
            with patch(
                "elastro.health.remediation.executor.RollbackStore.save",
            ) as mock_save:
                executor = RemediationExecutor(client, dry_run=True, interactive=False)
                result = executor.execute_action("reduce_replicas", "logs-2024")

        assert result.dry_run is True
        assert result.executed is False
        assert result.planned_api_call is not None
        mock_execute.assert_not_called()
        mock_save.assert_not_called()

    def test_rollback_dry_run_includes_planned_api_call(self, tmp_path):
        client = MagicMock()
        from elastro.health.remediation.rollback import RollbackRecord, RollbackStore

        store = RollbackStore(root=tmp_path)
        rollback_id = "rb-550e8400-e29b-41d4-a716-446655440000"
        record = RollbackRecord(
            rollback_id=rollback_id,
            session_id="sess-1",
            action_id="reduce_replicas",
            index_name="logs-2024",
            before={"index": {"number_of_replicas": 1}},
        )
        store.save(record)

        executor = RemediationExecutor(
            client,
            interactive=False,
            rollback_store=store,
        )
        result = executor.rollback(rollback_id, dry_run=True)
        assert result.dry_run is True
        assert result.executed is False
        assert result.planned_api_call is not None
        assert "PUT /logs-2024/_settings" in result.planned_api_call


class TestDryRunAudit:
    def test_audit_skips_es_index_on_dry_run(self):
        client = MagicMock()
        logger = HealthAuditLogger(client, profile="test", host="localhost")
        logger.log_fix(
            RemediationResult(
                action_id="reduce_replicas",
                index_name="logs-2024",
                success=True,
                executed=False,
                dry_run=True,
                message="preview",
            ),
            session_id="sess-1",
        )
        client.client.index.assert_not_called()