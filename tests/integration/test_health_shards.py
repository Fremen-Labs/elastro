"""Integration tests for health shards and hotspots CLI."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from elastro.cli.cli import cli


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.mark.integration
class TestHealthShardsCLI:
    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.health.collectors.shards.ShardsCollector.collect")
    def test_shards_analyze_table_output(self, mock_collect, mock_connect, runner):
        mock_connect.return_value = None
        mock_collect.return_value = MagicMock(
            status="ok",
            data={
                "analysis": {
                    "total_shards": 1247,
                    "avg_bytes": 2.3 * 1024**3,
                    "oversharded_count": 45,
                    "undersharded_count": 3,
                    "unassigned_count": 0,
                    "overshard_threshold_bytes": 1024 * 1024,
                    "undershard_threshold_bytes": 50 * 1024**3,
                    "oversharded": [],
                    "undersharded": [],
                }
            },
        )

        result = runner.invoke(
            cli,
            ["-h", "http://localhost:9205", "-o", "table", "health", "shards", "--analyze"],
        )

        assert result.exit_code == 0, result.output
        assert "Total shards: 1,247" in result.output
        assert "OVERSHARDED" in result.output
        assert "UNDERSHARDED" in result.output

    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.health.collectors.shards.explain_allocation")
    def test_shards_explain_json(self, mock_explain, mock_connect, runner):
        mock_connect.return_value = None
        mock_explain.return_value = {
            "index": "logs-000001",
            "allocate_explanation": "blocked",
        }

        result = runner.invoke(
            cli,
            [
                "-h",
                "http://localhost:9205",
                "-o",
                "json",
                "health",
                "shards",
                "--explain",
                "--index",
                "logs-000001",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "logs-000001" in result.output


@pytest.mark.integration
class TestHealthHotspotsCLI:
    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.health.collectors.nodes.NodesCollector.collect")
    def test_hotspots_table_output(self, mock_collect, mock_connect, runner):
        mock_connect.return_value = None
        mock_collect.return_value = MagicMock(
            status="ok",
            data={
                "nodes": {
                    "n1": {
                        "name": "hot-node",
                        "jvm": {"mem": {"heap_used_percent": 92}},
                        "fs": {
                            "total": {
                                "total_in_bytes": 1000,
                                "available_in_bytes": 500,
                            }
                        },
                        "os": {"cpu": {"percent": 55}},
                    },
                    "n2": {
                        "name": "cool-node",
                        "jvm": {"mem": {"heap_used_percent": 40}},
                        "fs": {
                            "total": {
                                "total_in_bytes": 1000,
                                "available_in_bytes": 900,
                            }
                        },
                        "os": {"cpu": {"percent": 12}},
                    },
                }
            },
        )

        result = runner.invoke(
            cli,
            ["-h", "http://localhost:9205", "-o", "table", "health", "hotspots"],
        )

        assert result.exit_code == 0, result.output
        assert "Node Hotspots" in result.output
        assert "JVM heap" in result.output