"""Integration tests for elastro health nodes CLI."""

import json
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from elastro.cli.cli import cli


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.mark.integration
class TestHealthNodesCLI:
    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.health.collectors.nodes.HealthManager")
    def test_nodes_table_jvm_fs(self, mock_manager_cls, mock_connect, runner):
        mock_connect.return_value = None
        mock_manager = mock_manager_cls.return_value
        mock_manager.node_stats.return_value = {
            "nodes": {
                "n1": {
                    "name": "es-node-1",
                    "jvm": {"mem": {"heap_used_percent": 68}},
                    "fs": {
                        "total": {
                            "total_in_bytes": 100000,
                            "available_in_bytes": 30000,
                        }
                    },
                }
            }
        }
        mock_manager.node_info.return_value = {"nodes": {"n1": {"roles": ["data"]}}}

        result = runner.invoke(
            cli,
            [
                "-h",
                "http://localhost:9205",
                "-o",
                "table",
                "health",
                "nodes",
                "--metric",
                "jvm,fs",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "Node Health" in result.output
        assert "es-node-1" in result.output
        assert "68" in result.output

    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.health.collectors.nodes.HealthManager")
    def test_nodes_json_output(self, mock_manager_cls, mock_connect, runner):
        mock_connect.return_value = None
        mock_manager = mock_manager_cls.return_value
        mock_manager.node_stats.return_value = {"nodes": {}}
        mock_manager.node_info.return_value = {"nodes": {}}

        result = runner.invoke(
            cli,
            ["-h", "http://localhost:9205", "-o", "json", "health", "nodes"],
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output.strip())
        assert payload["node_count"] == 0
