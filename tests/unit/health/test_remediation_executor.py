"""Unit tests for remediation catalog and executor."""

from unittest.mock import MagicMock, patch

import pytest

from elastro.health.remediation.catalog import RemediationCatalog
from elastro.health.remediation.executor import RemediationExecutor
from elastro.health.remediation.models import IndexDiagnosis


class TestRemediationCatalog:
    def test_lists_three_actions(self):
        assert set(RemediationCatalog.list_ids()) == {
            "reduce_replicas",
            "reroute_failed",
            "clear_routing_filters",
        }

    def test_planned_reduce_replicas(self):
        planned = RemediationCatalog.planned_call(
            "reduce_replicas",
            "logs-2024",
            api_mode=True,
        )
        assert "logs-2024" in planned
        assert "number_of_replicas" in planned

    def test_triggers_remediation_scan(self):
        assert RemediationCatalog.triggers_remediation_scan("elastro index fix")
        assert RemediationCatalog.triggers_remediation_scan("elastro cluster allocation")
        assert not RemediationCatalog.triggers_remediation_scan("elastro health report")


class TestRemediationExecutor:
    @pytest.fixture
    def client(self):
        return MagicMock()

    def test_dry_run_does_not_execute(self, client):
        executor = RemediationExecutor(client, dry_run=True, interactive=False)
        result = executor.execute_action("reduce_replicas", "logs-2024")
        assert result.dry_run is True
        assert result.executed is False
        assert result.success is True
        assert "PUT /logs-2024/_settings" in (result.planned_api_call or "")

    def test_non_interactive_executes(self, client):
        with patch(
            "elastro.health.remediation.executor.RemediationCatalog.execute",
            return_value="done",
        ) as mock_execute:
            executor = RemediationExecutor(
                client,
                dry_run=False,
                interactive=False,
                api_mode=True,
            )
            result = executor.execute_action("reroute_failed", None)

        assert result.executed is True
        assert result.success is True
        assert result.message == "done"
        mock_execute.assert_called_once()

    def test_interactive_decline_skips_execution(self, client):
        executor = RemediationExecutor(
            client,
            dry_run=False,
            interactive=True,
            confirm=lambda _prompt, _default: False,
        )
        result = executor.execute_action("reduce_replicas", "logs-2024")
        assert result.executed is False
        assert result.success is True
        assert result.message == "Skipped by user"

    def test_remediate_diagnosis_returns_none_without_action(self, client):
        executor = RemediationExecutor(client, dry_run=True)
        diagnosis = IndexDiagnosis(
            index_name="logs-2024",
            health="yellow",
            suggested_action_id=None,
        )
        assert executor.remediate_diagnosis(diagnosis) is None