"""Integration tests for elastro index fix remediation flow."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from elastro.cli.cli import cli


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.mark.integration
class TestIndexFixCLI:
    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.health.remediation.diagnosis.diagnose_unhealthy_indices")
    @patch("elastro.health.remediation.diagnosis.list_unhealthy_indices")
    def test_fix_offers_three_remediation_modes(
        self,
        mock_list_unhealthy,
        mock_diagnose,
        mock_connect,
        runner,
    ):
        from elastro.health.remediation.models import IndexDiagnosis

        mock_connect.return_value = None
        mock_list_unhealthy.return_value = [
            {"index": "logs-2024", "health": "yellow", "status": "open"}
        ]
        mock_diagnose.return_value = [
            IndexDiagnosis(
                index_name="logs-2024",
                health="yellow",
                allocate_explanation="too many copies on same node",
                reason="REPLICA_ADDED",
                suggestion_text="Reduce replicas",
                suggested_action_id="reduce_replicas",
            )
        ]

        with patch(
            "elastro.health.remediation.fix.run_health_fix",
            return_value=MagicMock(
                diagnoses=mock_diagnose.return_value,
                planned_actions=[],
                results=[
                    MagicMock(
                        action_id="reduce_replicas",
                        index_name="logs-2024",
                        executed=False,
                        success=True,
                        message="Skipped by user",
                        planned_api_call="PUT /logs-2024/_settings",
                        dry_run=False,
                    )
                ],
                blocked=[],
                dry_run=False,
                plan_only=False,
            ),
        ):
            result = runner.invoke(
                cli,
                ["-h", "http://localhost:9205", "index", "fix"],
                input="n\n",
            )

        assert result.exit_code == 0, result.output
        assert "Unhealthy Indices Found" in result.output
        assert "Deprecation" in result.stderr
        assert "Reduce replicas" in result.output or "Suggestion" in result.output

    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.health.remediation.diagnosis.list_unhealthy_indices")
    def test_fix_reports_healthy_cluster(
        self, mock_list_unhealthy, mock_connect, runner
    ):
        mock_connect.return_value = None
        mock_list_unhealthy.return_value = []

        result = runner.invoke(cli, ["-h", "http://localhost:9205", "index", "fix"])

        assert result.exit_code == 0, result.output
        assert "No unhealthy indices found" in result.output

    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.health.remediation.diagnosis.diagnose_unhealthy_indices")
    @patch("elastro.health.remediation.diagnosis.list_unhealthy_indices")
    def test_fix_applies_remediation_when_confirmed(
        self,
        mock_list_unhealthy,
        mock_diagnose,
        mock_connect,
        runner,
    ):
        from elastro.health.remediation.models import IndexDiagnosis

        mock_connect.return_value = None
        mock_list_unhealthy.return_value = [
            {"index": "logs-2024", "health": "yellow", "status": "open"}
        ]
        mock_diagnose.return_value = [
            IndexDiagnosis(
                index_name="logs-2024",
                health="yellow",
                allocate_explanation="too many copies on same node",
                reason="REPLICA_ADDED",
                suggestion_text="Reduce replicas",
                suggested_action_id="reduce_replicas",
            )
        ]

        with patch(
            "elastro.health.remediation.fix.run_health_fix",
            return_value=MagicMock(
                diagnoses=mock_diagnose.return_value,
                planned_actions=[],
                results=[
                    MagicMock(
                        action_id="reduce_replicas",
                        index_name="logs-2024",
                        executed=True,
                        success=True,
                        message="Replicas reduced to 0",
                        planned_api_call=None,
                        dry_run=False,
                        rollback_id=None,
                    )
                ],
                blocked=[],
                dry_run=False,
                plan_only=False,
            ),
        ):
            result = runner.invoke(
                cli,
                ["-h", "http://localhost:9205", "index", "fix"],
                input="y\n",
            )

        assert result.exit_code == 0, result.output
        assert "Replicas reduced to" in result.output
        assert "Diagnostics complete" in result.output

    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.health.remediation.diagnosis.diagnose_unhealthy_indices")
    @patch("elastro.health.remediation.diagnosis.list_unhealthy_indices")
    def test_fix_shows_no_automated_fix_without_suggestion(
        self,
        mock_list_unhealthy,
        mock_diagnose,
        mock_connect,
        runner,
    ):
        from elastro.health.remediation.models import IndexDiagnosis

        mock_connect.return_value = None
        mock_list_unhealthy.return_value = [
            {"index": "locked-index", "health": "red", "status": "open"}
        ]
        mock_diagnose.return_value = [
            IndexDiagnosis(
                index_name="locked-index",
                health="red",
                allocate_explanation="Shard locked by snapshot",
                reason="SNAPSHOT",
                suggested_action_id=None,
            )
        ]

        result = runner.invoke(cli, ["-h", "http://localhost:9205", "index", "fix"])

        assert result.exit_code == 0, result.output
        assert "No automated quick fix available" in result.output

    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.health.remediation.diagnosis.list_unhealthy_indices")
    def test_fix_reports_operation_error(
        self, mock_list_unhealthy, mock_connect, runner
    ):
        from elastro.core.errors import OperationError

        mock_connect.return_value = None
        mock_list_unhealthy.side_effect = OperationError("Failed to list indices")

        result = runner.invoke(cli, ["-h", "http://localhost:9205", "index", "fix"])

        assert result.exit_code == 1, result.output
        assert "Failed to list indices" in result.output
