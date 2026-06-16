"""Integration tests for elastro health fix remediation flow."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from elastro.cli.cli import cli


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.mark.integration
class TestHealthFixCLI:
    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.health.remediation.fix.diagnose_unhealthy_indices")
    def test_fix_dry_run_shows_plan(
        self,
        mock_diagnose,
        mock_connect,
        runner,
    ):
        from elastro.health.remediation.models import IndexDiagnosis

        mock_connect.return_value = None
        mock_diagnose.return_value = [
            IndexDiagnosis(
                index_name="logs-2024",
                health="yellow",
                suggested_action_id="reduce_replicas",
                suggestion_text="Reduce replicas",
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
            ],
        )

        assert result.exit_code == 0, result.output
        assert "Remediation runbook" in result.output
        assert "logs-2024" in result.output

    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.health.remediation.fix.diagnose_unhealthy_indices")
    def test_fix_blocks_destructive_without_force(
        self,
        mock_diagnose,
        mock_connect,
        runner,
    ):
        from elastro.health.remediation.models import IndexDiagnosis

        mock_connect.return_value = None
        mock_diagnose.return_value = [
            IndexDiagnosis(
                index_name="logs-2024",
                health="yellow",
                suggested_action_id="reduce_replicas",
            )
        ]

        result = runner.invoke(
            cli,
            ["-h", "http://localhost:9205", "-o", "table", "health", "fix", "--yes"],
        )

        assert result.exit_code == 0, result.output
        assert "Blocked" in result.output or "blocked" in result.output.lower()

    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.health.remediation.fix.diagnose_unhealthy_indices")
    def test_fix_dry_run_json_is_scriptable(
        self,
        mock_diagnose,
        mock_connect,
        runner,
    ):
        import json

        from elastro.health.remediation.models import IndexDiagnosis

        mock_connect.return_value = None
        mock_diagnose.return_value = [
            IndexDiagnosis(
                index_name="logs-2024",
                health="yellow",
                suggested_action_id="reduce_replicas",
            )
        ]

        with patch(
            "elastro.health.remediation.planner.resolve_replica_target",
            return_value=0,
        ):
            result = runner.invoke(
                cli,
                [
                    "-h",
                    "http://localhost:9205",
                    "-o",
                    "json",
                    "health",
                    "fix",
                    "--dry-run",
                ],
            )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["dry_run"] is True
        assert payload["summary"]["preview_only"] is True
        assert payload["summary"]["executed_count"] == 0
        assert payload["planned_actions"]
        assert payload["results"][0]["planned_api_call"]
        assert payload["results"][0]["executed"] is False

    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.cli.commands.health.run_health_fix")
    def test_assess_plan_only(
        self,
        mock_run_fix,
        mock_connect,
        runner,
    ):
        from elastro.health.remediation.models import (
            FixRunResult,
            IndexDiagnosis,
            PlannedAction,
        )
        from elastro.health.models import RemediationSafety

        mock_connect.return_value = None
        mock_run_fix.return_value = FixRunResult(
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
                    planned_api_call="PUT /logs-2024/_settings",
                )
            ],
            plan_only=True,
            dry_run=True,
        )

        with patch("elastro.cli.commands.health._run_assessment") as mock_assess:
            from elastro.health.models import AssessmentReport, FindingStatus

            mock_assess.return_value = AssessmentReport(
                cluster_name="test-cluster",
                overall_score=40,
                overall_status=FindingStatus.FAIL,
            )
            with patch(
                "elastro.cli.commands.health.render_assessment",
                return_value="assessment output",
            ):
                result = runner.invoke(
                    cli,
                    [
                        "-h",
                        "http://localhost:9205",
                        "-o",
                        "table",
                        "health",
                        "assess",
                        "--plan",
                    ],
                )

        assert result.exit_code == 2, result.output
        assert "Remediation runbook" in result.output
        mock_run_fix.assert_called_once()
        assert mock_run_fix.call_args.kwargs.get("plan_only") is True
