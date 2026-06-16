"""Integration tests for health rollback and history CLI."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from elastro.cli.cli import cli


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.mark.integration
class TestHealthRollbackCLI:
    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.health.remediation.executor.RemediationExecutor.rollback")
    def test_rollback_command_success(self, mock_rollback, mock_connect, runner):
        from elastro.health.remediation.models import RemediationResult

        mock_connect.return_value = None
        mock_rollback.return_value = RemediationResult(
            action_id="rollback",
            index_name="logs-2024",
            success=True,
            executed=True,
            message="Restored settings for 'logs-2024'",
            rollback_id="rb-550e8400-e29b-41d4-a716-446655440000",
        )

        result = runner.invoke(
            cli,
            [
                "-h",
                "http://localhost:9205",
                "health",
                "rollback",
                "apply",
                "--id",
                "rb-550e8400-e29b-41d4-a716-446655440000",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "Restored settings" in result.output


@pytest.mark.integration
class TestHealthHistoryCLI:
    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.health.history.query_assessment_history")
    def test_score_history_table(self, mock_query, mock_connect, runner):
        mock_connect.return_value = None
        mock_query.return_value = [
            {
                "cluster_name": "docker-cluster",
                "overall_score": 88,
                "overall_status": "warn",
                "assessed_at": "2026-06-15T12:00:00+00:00",
            }
        ]

        result = runner.invoke(
            cli,
            [
                "-h",
                "http://localhost:9205",
                "-o",
                "table",
                "health",
                "score",
                "--history",
                "--last",
                "1",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "88/100" in result.output
        assert "docker-cluster" in result.output