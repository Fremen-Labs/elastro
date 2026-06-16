"""Integration tests for health trends CLI."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from elastro.cli.cli import cli
from elastro.core.client import ElasticsearchClient


def _history_record(score: int, hours_ago: float):
    assessed_at = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return {
        "cluster_name": "docker-cluster",
        "assessed_at": assessed_at.isoformat(),
        "overall_score": score,
        "overall_status": "warn",
        "findings": [{"id": "disk.watermark.high", "status": "warn"}],
    }


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_client():
    client = MagicMock(spec=ElasticsearchClient)
    client.hosts = ["http://localhost:9205"]
    return client


@pytest.mark.integration
class TestHealthTrendsCLI:
    @patch("elastro.health.trends.compute_trends")
    def test_trends_cluster_json(self, mock_compute, runner, mock_client):
        from elastro.health.trends import HistoryPoint, TrendReport

        mock_compute.return_value = TrendReport(
            cluster_name="docker-cluster",
            window="7d",
            sample_count=2,
            points=[
                HistoryPoint("2026-06-14T00:00:00+00:00", 70, "warn"),
                HistoryPoint("2026-06-15T00:00:00+00:00", 80, "warn"),
            ],
            score_delta_7d=10,
            recurring_findings=["disk.watermark.high"],
            persistent_yellow_count=1,
        )

        result = runner.invoke(
            cli,
            ["-o", "json", "health", "trends", "--cluster", "docker-cluster"],
            obj=mock_client,
        )

        assert result.exit_code == 0
        assert '"score_delta_7d": 10' in result.output
        assert '"recurring_findings"' in result.output

    @patch("elastro.health.history.history_cluster_summary")
    def test_trends_fleet_table(self, mock_summary, runner, mock_client):
        mock_summary.return_value = [
            {
                "cluster_name": "docker-cluster",
                "latest_score": 82,
                "latest_status": "warn",
                "avg_score": 80.0,
                "sample_count": 4,
                "latest_assessed_at": "2026-06-15T00:00:00+00:00",
            }
        ]

        result = runner.invoke(
            cli,
            ["-o", "table", "health", "trends"],
            obj=mock_client,
        )

        assert result.exit_code == 0
        assert "Fleet Health" in result.output
        assert "docker-cluster" in result.output

    @patch("elastro.health.history.query_assessment_history")
    def test_score_history_table_sparkline(self, mock_query, runner, mock_client):
        mock_query.return_value = [
            _history_record(60, 48),
            _history_record(70, 24),
            _history_record(80, 1),
        ]

        result = runner.invoke(
            cli,
            ["-o", "table", "health", "score", "--history", "--last", "3"],
            obj=mock_client,
        )

        assert result.exit_code == 0
        assert "Assessment History" in result.output
        assert "Trend:" in result.output

    def test_trends_invalid_window_exits_2(self, runner, mock_client):
        result = runner.invoke(
            cli,
            ["health", "trends", "--window", "bad"],
            obj=mock_client,
        )
        assert result.exit_code == 2
