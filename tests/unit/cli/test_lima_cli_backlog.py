"""CLI tests for Lima live-test backlog fixes."""

from __future__ import annotations

import json
import logging
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from elastro.cli.art import banner_enabled
from elastro.cli.cli import cli
from elastro.cli.commands.cluster import cluster_group
from elastro.cli.commands.document import search_documents
from elastro.cli.commands.health import health_group
from elastro.cli.commands.ilm import ilm_group
from elastro.cli.commands.memory import memory_group
from elastro.cli.commands.painless_commands import painless_group
from elastro.cli.commands.tools import tools_group
from elastro.core.client import ElasticsearchClient
from elastro.core.errors import ConnectionError


def _client() -> MagicMock:
    client = MagicMock()
    client.is_connected.return_value = True
    client.get_client.return_value = client.client
    return client


def test_help_does_not_connect_or_ping(monkeypatch, caplog) -> None:
    connect = MagicMock()
    ping = MagicMock(return_value=False)
    monkeypatch.setattr(ElasticsearchClient, "connect", connect)
    monkeypatch.setattr("elastro.core.client.Elasticsearch.ping", ping)
    caplog.set_level(logging.ERROR)

    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0, result.output
    connect.assert_not_called()
    ping.assert_not_called()
    assert not any("Ping failed" in rec.message for rec in caplog.records)


def test_subcommand_help_does_not_connect(monkeypatch, caplog) -> None:
    connect = MagicMock()
    ping = MagicMock(return_value=False)
    monkeypatch.setattr(ElasticsearchClient, "connect", connect)
    monkeypatch.setattr("elastro.core.client.Elasticsearch.ping", ping)
    caplog.set_level(logging.ERROR)

    result = CliRunner().invoke(cli, ["coverage", "--help"])
    assert result.exit_code == 0, result.output
    connect.assert_not_called()
    ping.assert_not_called()
    assert not any("Ping failed" in rec.message for rec in caplog.records)


def test_coverage_fleet_status_does_not_connect(monkeypatch, caplog) -> None:
    connect = MagicMock()
    ping = MagicMock(return_value=False)
    monkeypatch.setattr(ElasticsearchClient, "connect", connect)
    monkeypatch.setattr("elastro.core.client.Elasticsearch.ping", ping)
    caplog.set_level(logging.ERROR)

    result = CliRunner().invoke(cli, ["coverage", "fleet", "status"])
    assert result.exit_code == 2
    connect.assert_not_called()
    ping.assert_not_called()
    assert not any("Ping failed" in rec.message for rec in caplog.records)


def test_security_users_refused_host_exits_1(monkeypatch) -> None:
    def boom(self: ElasticsearchClient) -> None:
        raise ConnectionError("Failed to connect to Elasticsearch (host unreachable)")

    monkeypatch.setattr(ElasticsearchClient, "connect", boom)
    result = CliRunner().invoke(cli, ["security", "users"])

    assert result.exit_code == 1
    assert "connect" in result.stderr.lower() or "unreachable" in result.stderr.lower()


def test_missing_args_do_not_connect(monkeypatch) -> None:
    connect = MagicMock()
    monkeypatch.setattr(ElasticsearchClient, "connect", connect)
    result = CliRunner().invoke(cli, ["index", "find"])
    assert result.exit_code == 2
    connect.assert_not_called()


def test_help_skips_ascii_art_when_not_tty(monkeypatch) -> None:
    monkeypatch.delenv("ELASTRO_NO_ART", raising=False)
    monkeypatch.delenv("ELASTRO_GUI_MODE", raising=False)
    monkeypatch.setattr("elastro.cli.art.sys.stdout.isatty", lambda: False)
    from elastro.cli.cli import _apply_header_text

    _apply_header_text()
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "_ __|" not in result.output


def test_banner_enabled_respects_no_art_and_tty(monkeypatch) -> None:
    monkeypatch.delenv("ELASTRO_GUI_MODE", raising=False)
    monkeypatch.setenv("ELASTRO_NO_ART", "1")
    monkeypatch.setattr("elastro.cli.art.sys.stdout.isatty", lambda: True)
    assert banner_enabled() is False

    monkeypatch.delenv("ELASTRO_NO_ART", raising=False)
    monkeypatch.setattr("elastro.cli.art.sys.stdout.isatty", lambda: False)
    assert banner_enabled() is False

    monkeypatch.setattr("elastro.cli.art.sys.stdout.isatty", lambda: True)
    assert banner_enabled() is True


def test_health_status_json_has_no_banner(monkeypatch) -> None:
    monkeypatch.setattr(
        ElasticsearchClient,
        "connect",
        lambda self: setattr(self, "_connected", True),
    )
    manager = MagicMock()
    manager.cluster_health.return_value = {
        "cluster_name": "docker-cluster",
        "status": "green",
        "number_of_nodes": 2,
        "number_of_data_nodes": 2,
    }
    monkeypatch.setattr(
        "elastro.cli.commands.health.HealthManager", lambda _client: manager
    )
    result = CliRunner().invoke(cli, ["-o", "json", "health", "status"])

    assert result.exit_code == 0, result.output
    assert "Cluster:" not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["cluster_name"] == "docker-cluster"
    assert payload["status"] == "green"


def test_health_status_table_prints_banner(monkeypatch) -> None:
    monkeypatch.setattr(
        ElasticsearchClient,
        "connect",
        lambda self: setattr(self, "_connected", True),
    )
    manager = MagicMock()
    manager.cluster_health.return_value = {
        "cluster_name": "docker-cluster",
        "status": "green",
        "number_of_nodes": 2,
        "number_of_data_nodes": 2,
    }
    monkeypatch.setattr(
        "elastro.cli.commands.health.HealthManager", lambda _client: manager
    )
    result = CliRunner().invoke(cli, ["-o", "table", "health", "status"])

    assert result.exit_code == 0, result.output
    assert "Cluster:" in result.stdout
    assert "docker-cluster" in result.stdout


def test_painless_scaffold_non_tty_exits_2_no_connect(monkeypatch) -> None:
    connect = MagicMock()
    monkeypatch.setattr(ElasticsearchClient, "connect", connect)
    result = CliRunner().invoke(cli, ["painless", "scaffold"])

    assert result.exit_code == 2
    assert "interactive wizard requires a TTY" in result.stderr
    connect.assert_not_called()


def test_painless_scaffold_group_non_tty_exits_2() -> None:
    result = CliRunner().invoke(painless_group, ["scaffold"])
    assert result.exit_code == 2
    assert "interactive wizard requires a TTY" in result.stderr


def test_ilm_start_without_yes_exits_2_zero_calls() -> None:
    client = _client()
    result = CliRunner().invoke(ilm_group, ["start"], obj=client)

    assert result.exit_code == 2
    assert "--yes" in result.stderr
    client.client.ilm.start.assert_not_called()
    client.get_client.assert_not_called()


def test_ilm_stop_without_yes_exits_2_zero_calls() -> None:
    client = _client()
    result = CliRunner().invoke(ilm_group, ["stop"], obj=client)

    assert result.exit_code == 2
    assert "--yes" in result.stderr
    client.client.ilm.stop.assert_not_called()
    client.get_client.assert_not_called()


def test_ilm_start_dry_run_prints_call_no_api() -> None:
    client = _client()
    result = CliRunner().invoke(ilm_group, ["start", "--dry-run"], obj=client)

    assert result.exit_code == 0, result.output
    assert "POST /_ilm/start" in result.output
    client.client.ilm.start.assert_not_called()
    client.get_client.assert_not_called()


def test_ilm_stop_dry_run_prints_call_no_api() -> None:
    client = _client()
    result = CliRunner().invoke(ilm_group, ["stop", "--dry-run"], obj=client)

    assert result.exit_code == 0, result.output
    assert "POST /_ilm/stop" in result.output
    client.client.ilm.stop.assert_not_called()


def test_ilm_start_with_yes_calls_start() -> None:
    client = _client()
    client.client.ilm.start.return_value = {"acknowledged": True}
    result = CliRunner().invoke(ilm_group, ["start", "--yes"], obj=client)

    assert result.exit_code == 0, result.output
    client.client.ilm.start.assert_called_once()


def test_utils_templates_without_subcommand_lists() -> None:
    client = _client()
    with patch("elastro.cli.commands.utils.TemplateManager") as cls:
        cls.return_value.list.return_value = [{"name": "logs"}]
        result = CliRunner().invoke(cli, ["utils", "templates"], obj=client)
    assert result.exit_code == 0, result.output
    cls.return_value.list.assert_called_once()


def test_utils_aliases_without_subcommand_lists() -> None:
    client = _client()
    with patch("elastro.cli.commands.utils.AliasManager") as cls:
        cls.return_value.list.return_value = [{"alias": "logs"}]
        result = CliRunner().invoke(cli, ["utils", "aliases"], obj=client)
    assert result.exit_code == 0, result.output
    cls.return_value.list.assert_called_once()


def test_utils_templates_list_subcommand_still_works() -> None:
    client = _client()
    with patch("elastro.cli.commands.utils.TemplateManager") as cls:
        cls.return_value.list.return_value = []
        result = CliRunner().invoke(cli, ["utils", "templates", "list"], obj=client)
    assert result.exit_code == 0, result.output
    cls.return_value.list.assert_called_once()


def test_doc_index_refreshes_by_default() -> None:
    client = _client()
    with patch("elastro.cli.commands.document.DocumentManager") as cls:
        cls.return_value.index.return_value = {"result": "created", "_id": "1"}
        result = CliRunner().invoke(
            cli,
            ["doc", "index", "products", "--id", "1"],
            input='{"name": "Laptop", "category": "electronics"}\n',
            obj=client,
        )
    assert result.exit_code == 0, result.output
    kwargs = cls.return_value.index.call_args.kwargs
    assert kwargs.get("refresh") is True


def test_doc_index_no_refresh_flag() -> None:
    client = _client()
    with patch("elastro.cli.commands.document.DocumentManager") as cls:
        cls.return_value.index.return_value = {"result": "created", "_id": "1"}
        result = CliRunner().invoke(
            cli,
            ["doc", "index", "products", "--id", "1", "--no-refresh"],
            input='{"name": "Laptop"}\n',
            obj=client,
        )
    assert result.exit_code == 0, result.output
    assert cls.return_value.index.call_args.kwargs.get("refresh") is False


def test_doc_search_query_option() -> None:
    client = _client()
    with patch("elastro.cli.commands.document.DocumentManager") as cls:
        cls.return_value.search.return_value = {"hits": {"hits": []}}
        result = CliRunner().invoke(
            search_documents,
            ["my-logs", "--query", "status:error"],
            obj=client,
        )
    assert result.exit_code == 0, result.output
    args, kwargs = cls.return_value.search.call_args
    query_body = args[1] if len(args) > 1 else kwargs.get("query")
    assert "status:error" in json.dumps(query_body)


def test_doc_search_query_help_mentions_flag() -> None:
    result = CliRunner().invoke(cli, ["doc", "search", "--help"])
    assert result.exit_code == 0
    assert "--query" in result.output


def test_cluster_allocation_no_unassigned_exits_0() -> None:
    client = _client()

    class BadRequest(Exception):
        status_code = 400

        def __str__(self) -> str:
            return "No shard was specified"

    client.client.cluster.allocation_explain.side_effect = BadRequest()
    result = CliRunner().invoke(cluster_group, ["allocation"], obj=client)

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["message"] == "no unassigned shards to explain"


def test_cluster_allocation_other_400_exits_1() -> None:
    client = _client()

    class BadRequest(Exception):
        status_code = 400

        def __str__(self) -> str:
            return "invalid allocation request"

    client.client.cluster.allocation_explain.side_effect = BadRequest()
    result = CliRunner().invoke(cluster_group, ["allocation"], obj=client)

    assert result.exit_code == 1
    assert "invalid allocation request" in result.stderr


def test_health_shards_explain_no_unassigned_exits_0() -> None:
    client = _client()

    class BadRequest(Exception):
        status_code = 400

        def __str__(self) -> str:
            return "No shard was specified"

    client.client.cluster.allocation_explain.side_effect = BadRequest()
    result = CliRunner().invoke(health_group, ["shards", "--explain"], obj=client)

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["message"] == "no unassigned shards to explain"


def test_health_shards_explain_other_400_exits_1() -> None:
    client = _client()

    class BadRequest(Exception):
        status_code = 400

        def __str__(self) -> str:
            return "invalid allocation request"

    client.client.cluster.allocation_explain.side_effect = BadRequest()
    result = CliRunner().invoke(health_group, ["shards", "--explain"], obj=client)

    assert result.exit_code == 1
    assert "invalid allocation request" in result.stderr


def test_memory_search_missing_index_exits_0(caplog) -> None:
    client = _client()

    class NotFound(Exception):
        status_code = 404

        def __str__(self) -> str:
            return "index_not_found_exception"

    client.client.search.side_effect = NotFound()
    caplog.set_level(logging.INFO)
    result = CliRunner().invoke(memory_group, ["search", "foo"], obj=client)

    assert result.exit_code == 0, result.output
    assert "Found 0" in result.output
    assert result.stderr == "" or "Traceback" not in result.stderr
    assert not any(
        rec.exc_info for rec in caplog.records if rec.levelno >= logging.ERROR
    )


def test_tools_search_missing_index_exits_0() -> None:
    client = _client()

    class NotFound(Exception):
        status_code = 404

        def __str__(self) -> str:
            return "index_not_found_exception"

    client.client.search.side_effect = NotFound()
    result = CliRunner().invoke(tools_group, ["search", "foo"], obj=client)

    assert result.exit_code == 0, result.output
    assert "Found 0" in result.output
    assert "Traceback" not in result.stderr


def test_memory_search_transport_error_exits_1() -> None:
    client = _client()
    client.client.search.side_effect = Exception("No node reached")
    result = CliRunner().invoke(memory_group, ["search", "foo"], obj=client)

    assert result.exit_code == 1
    assert "No node reached" in result.stderr
