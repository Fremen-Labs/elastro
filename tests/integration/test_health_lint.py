"""Integration tests for health lint CLI."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from elastro.cli.cli import cli
from elastro.health.models import Finding, FindingStatus, Severity


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.mark.integration
class TestHealthLintCLI:
    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.health.lint.run_lint")
    def test_lint_table_output(self, mock_run_lint, mock_connect, runner):
        mock_connect.return_value = None
        mock_run_lint.return_value = [
            Finding(
                id="settings.replicas_zero.logs-000001",
                category="settings",
                title="Index has zero replicas: logs-000001",
                status=FindingStatus.WARN,
                severity=Severity.MEDIUM,
                summary="Index 'logs-000001' sets number_of_replicas=0.",
            )
        ]

        result = runner.invoke(
            cli,
            ["-h", "http://localhost:9205", "-o", "table", "health", "lint"],
        )

        assert result.exit_code == 1, result.output
        assert "zero replicas" in result.output.lower()

    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.health.lint.run_lint")
    def test_lint_json_output(self, mock_run_lint, mock_connect, runner):
        mock_connect.return_value = None
        mock_run_lint.return_value = []

        result = runner.invoke(
            cli,
            [
                "-h",
                "http://localhost:9205",
                "-o",
                "json",
                "health",
                "lint",
                "--category",
                "shards",
            ],
        )

        assert result.exit_code == 0, result.output
        assert '"issue_count": 0' in result.output