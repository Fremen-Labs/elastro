"""Integration tests for monitoring-friendly health exit codes."""

import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from elastro.cli.cli import cli
from elastro.health.models import (
    AssessmentReport,
    Finding,
    FindingStatus,
    Severity,
)
from elastro.health.remediation.models import FixRunResult, RemediationResult


def _warn_report() -> AssessmentReport:
    return AssessmentReport(
        cluster_name="docker-cluster",
        elasticsearch_version="8.15.2",
        assessed_at=datetime(2026, 6, 15, tzinfo=timezone.utc),
        overall_score=88,
        overall_status=FindingStatus.WARN,
        findings=[
            Finding(
                id="indicator.shards_availability",
                category="shards",
                title="Shards Availability yellow",
                status=FindingStatus.WARN,
                severity=Severity.HIGH,
                summary="15 unavailable replica shards",
            )
        ],
    )


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.mark.integration
class TestHealthExitCodesCLI:
    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.cli.commands.health.HealthAssessor")
    def test_assess_default_fail_on_allows_warn(
        self, mock_assessor_cls, mock_connect, runner
    ):
        mock_connect.return_value = None
        mock_assessor_cls.return_value.run.return_value = _warn_report()

        result = runner.invoke(
            cli,
            ["-h", "http://localhost:9205", "-o", "json", "health", "assess"],
        )

        assert result.exit_code == 0, result.output

    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.cli.commands.health.HealthAssessor")
    def test_assess_fail_on_warn_exits_two(
        self, mock_assessor_cls, mock_connect, runner
    ):
        mock_connect.return_value = None
        mock_assessor_cls.return_value.run.return_value = _warn_report()

        result = runner.invoke(
            cli,
            [
                "-h",
                "http://localhost:9205",
                "-o",
                "json",
                "health",
                "assess",
                "--fail-on",
                "warn",
            ],
        )

        assert result.exit_code == 2, result.output

    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.cli.commands.health._run_assessment")
    def test_score_fail_on_yellow_exits_two(self, mock_assess, mock_connect, runner):
        mock_connect.return_value = None
        mock_assess.return_value = _warn_report()

        result = runner.invoke(
            cli,
            ["-h", "http://localhost:9205", "health", "score", "--fail-on", "yellow"],
        )

        assert result.exit_code == 2, result.output

    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.cli.commands.health.HealthManager")
    def test_status_red_exits_two_with_default_fail_on(
        self, mock_manager_cls, mock_connect, runner
    ):
        mock_connect.return_value = None
        mock_manager_cls.return_value.cluster_health.return_value = {
            "cluster_name": "docker-cluster",
            "status": "red",
            "timed_out": False,
            "number_of_nodes": 3,
            "number_of_data_nodes": 3,
        }

        result = runner.invoke(
            cli,
            ["-h", "http://localhost:9205", "health", "status"],
        )

        assert result.exit_code == 2, result.output

    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.cli.commands.health.HealthManager")
    def test_status_wait_yellow_succeeds_when_green(
        self, mock_manager_cls, mock_connect, runner
    ):
        mock_connect.return_value = None
        mock_manager_cls.return_value.cluster_health.return_value = {
            "cluster_name": "docker-cluster",
            "status": "green",
            "timed_out": False,
            "number_of_nodes": 3,
            "number_of_data_nodes": 3,
        }

        result = runner.invoke(
            cli,
            [
                "-h",
                "http://localhost:9205",
                "health",
                "status",
                "--wait",
                "yellow",
                "--timeout",
                "5s",
            ],
        )

        assert result.exit_code == 0, result.output

    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.cli.commands.health.HealthManager")
    def test_status_wait_timeout_exits_two(
        self, mock_manager_cls, mock_connect, runner
    ):
        mock_connect.return_value = None
        mock_manager_cls.return_value.cluster_health.return_value = {
            "cluster_name": "docker-cluster",
            "status": "yellow",
            "timed_out": True,
            "number_of_nodes": 3,
            "number_of_data_nodes": 3,
        }

        result = runner.invoke(
            cli,
            [
                "-h",
                "http://localhost:9205",
                "health",
                "status",
                "--wait",
                "green",
                "--timeout",
                "5s",
            ],
        )

        assert result.exit_code == 2, result.output

    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.health.collectors.shards.ShardsCollector")
    def test_shards_unassigned_exits_two_with_fail_on_warn(
        self, mock_collector_cls, mock_connect, runner
    ):
        from elastro.health.collectors.base import CollectorResult

        mock_connect.return_value = None
        mock_collector_cls.return_value.collect.return_value = CollectorResult(
            name="shards",
            status="ok",
            data={
                "analysis": {
                    "total_shards": 10,
                    "unassigned_count": 2,
                }
            },
        )

        result = runner.invoke(
            cli,
            [
                "-h",
                "http://localhost:9205",
                "-o",
                "json",
                "health",
                "shards",
                "--fail-on",
                "warn",
            ],
        )

        assert result.exit_code == 2, result.output
        payload = json.loads(result.output)
        assert payload["unassigned_shards"] == 2

    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.health.lint.run_lint")
    def test_lint_warn_only_exits_zero_with_default_fail_on(
        self, mock_run_lint, mock_connect, runner
    ):
        mock_connect.return_value = None
        mock_run_lint.return_value = [
            Finding(
                id="settings.replicas_zero.logs-000001",
                category="settings",
                title="Index has zero replicas",
                status=FindingStatus.WARN,
                severity=Severity.MEDIUM,
                summary="number_of_replicas=0",
            )
        ]

        result = runner.invoke(
            cli,
            ["-h", "http://localhost:9205", "-o", "json", "health", "lint"],
        )

        assert result.exit_code == 0, result.output

    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.health.remediation.fix.diagnose_unhealthy_indices")
    def test_fix_partial_failure_exits_three(
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

        with patch(
            "elastro.cli.commands.health.run_health_fix",
            return_value=FixRunResult(
                results=[
                    RemediationResult(
                        action_id="reduce_replicas",
                        index_name="logs-2024",
                        success=False,
                        executed=True,
                        message="settings update failed",
                    )
                ]
            ),
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
                    "--yes",
                    "--force",
                ],
            )

        assert result.exit_code == 3, result.output

    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.cli.commands.health._run_assessment")
    @patch("elastro.cli.commands.health.run_health_fix")
    def test_assess_fix_health_degradation_beats_partial_fix_failure(
        self,
        mock_run_fix,
        mock_assess,
        mock_connect,
        runner,
    ):
        from elastro.health.remediation.models import FixRunResult, RemediationResult

        mock_connect.return_value = None
        mock_assess.return_value = AssessmentReport(
            cluster_name="test-cluster",
            overall_score=30,
            overall_status=FindingStatus.FAIL,
        )
        mock_run_fix.return_value = FixRunResult(
            results=[
                RemediationResult(
                    action_id="reduce_replicas",
                    index_name="logs-2024",
                    success=False,
                    executed=True,
                    message="failed",
                )
            ]
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
                    "--fix",
                    "--yes",
                    "--force",
                ],
            )

        assert result.exit_code == 2, result.output
