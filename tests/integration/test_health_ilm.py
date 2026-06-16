"""Integration tests for health ilm and ILM remediation CLI."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from elastro.cli.cli import cli


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.mark.integration
class TestHealthIlmCLI:
    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.health.ilm_status.list_stuck_ilm_indices")
    def test_ilm_stuck_only_table(self, mock_list_stuck, mock_connect, runner):
        from elastro.health.ilm_status import StuckIlmIndex

        mock_connect.return_value = None
        mock_list_stuck.return_value = [
            StuckIlmIndex(
                index_name="logs-000042",
                health="yellow",
                issue="ILM step failed: snapshot",
                step="ERROR",
            )
        ]

        result = runner.invoke(
            cli,
            [
                "-h",
                "http://localhost:9205",
                "-o",
                "table",
                "health",
                "ilm",
                "--stuck-only",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "logs-000042" in result.output
        assert "ERROR" in result.output

    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.health.remediation.fix.diagnose_unhealthy_indices")
    @patch("elastro.health.remediation.fix.RemediationPlanner.plan_explicit")
    def test_fix_ilm_retry_dry_run(
        self,
        mock_plan_explicit,
        mock_diagnose,
        mock_connect,
        runner,
    ):
        from elastro.health.models import RemediationSafety
        from elastro.health.remediation.models import PlannedAction

        mock_connect.return_value = None
        mock_diagnose.return_value = []
        mock_plan_explicit.return_value = [
            PlannedAction(
                action_id="ilm_retry",
                label="Retry ILM lifecycle step",
                safety=RemediationSafety.CONFIRM,
                impact="Retries ILM step",
                index_name="logs-000042",
                planned_api_call="POST /logs-000042/_ilm/retry",
            )
        ]

        result = runner.invoke(
            cli,
            [
                "-h",
                "http://localhost:9205",
                "-o",
                "table",
                "health",
                "fix",
                "--dry-run",
                "--action",
                "ilm_retry",
                "--index",
                "logs-000042",
            ],
        )

        assert result.exit_code == 0, result.output
        mock_plan_explicit.assert_called_once()
        assert "logs-000042" in result.output
        assert "POST /logs-000042/_ilm/retry" in result.output
