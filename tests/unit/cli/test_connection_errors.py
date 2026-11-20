"""CLI tests for stored connect failures and the doc-search fast path."""

from __future__ import annotations

import inspect
import socket
import xmlrpc.client
from unittest.mock import MagicMock

from click.testing import CliRunner

from elastro.cli.cli import _try_doc_search_fast_path, cli
from elastro.cli.commands.security import list_users
from elastro.core.client import ElasticsearchClient
from elastro.core.errors import AuthenticationError


def _raise_auth(_self: object) -> None:
    raise AuthenticationError("authentication failed")


def _patch_connect_auth(monkeypatch) -> None:
    monkeypatch.setattr(ElasticsearchClient, "connect", _raise_auth)


def test_security_users_connect_auth_error_exits_1(monkeypatch) -> None:
    _patch_connect_auth(monkeypatch)
    result = CliRunner().invoke(cli, ["security", "users"])

    assert result.exit_code == 1
    assert "authentication" in result.stderr.lower()


def test_health_assess_connect_failure_does_not_call_assessor(monkeypatch) -> None:
    _patch_connect_auth(monkeypatch)
    assessor = MagicMock()
    monkeypatch.setattr("elastro.cli.commands.health.HealthAssessor", assessor)
    result = CliRunner().invoke(cli, ["health", "assess"])

    assert result.exit_code == 1
    assert "authentication" in result.stderr.lower()
    assessor.assert_not_called()


def test_health_assess_usage_checks_run_before_require_client(monkeypatch) -> None:
    _patch_connect_auth(monkeypatch)
    assessor = MagicMock()
    monkeypatch.setattr("elastro.cli.commands.health.HealthAssessor", assessor)
    result = CliRunner().invoke(cli, ["health", "assess", "--dry-run"])

    assert result.exit_code == 2
    assert "--dry-run requires --fix" in result.stderr
    assessor.assert_not_called()


def test_config_list_exits_0_when_connect_fails(monkeypatch) -> None:
    _patch_connect_auth(monkeypatch)
    result = CliRunner().invoke(cli, ["config", "list"])

    assert result.exit_code == 0, result.output


def test_gui_enters_command_when_connect_fails(monkeypatch) -> None:
    _patch_connect_auth(monkeypatch)
    monkeypatch.setattr(
        "elastro.cli.commands.gui.save_config",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "elastro.cli.commands.gui.os.makedirs",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "elastro.server.launch_gui_process",
        lambda: "http://127.0.0.1:8765",
    )
    result = CliRunner().invoke(cli, ["gui"])

    assert result.exit_code == 0, result.output
    assert "http://127.0.0.1:8765" in result.output


def test_daemon_start_reaches_start_daemon_when_connect_fails(monkeypatch) -> None:
    _patch_connect_auth(monkeypatch)
    called: list[dict] = []

    def fake_start_daemon(**kwargs: object) -> None:
        called.append(dict(kwargs))

    monkeypatch.setattr("elastro.core.daemon.start_daemon", fake_start_daemon)
    result = CliRunner().invoke(cli, ["daemon", "start"])

    assert result.exit_code == 0, result.output
    assert called


def test_health_rollback_list_runs_when_connect_fails(monkeypatch) -> None:
    _patch_connect_auth(monkeypatch)
    store = MagicMock()
    store.list_records.return_value = []
    monkeypatch.setattr(
        "elastro.health.remediation.rollback.RollbackStore",
        lambda: store,
    )
    result = CliRunner().invoke(cli, ["health", "rollback", "list"])

    assert result.exit_code == 0, result.output
    store.list_records.assert_called_once()


def test_fast_path_miss_restores_socket_timeout(monkeypatch) -> None:
    class BoomProxy:
        def fast_path_search(self, *_args: object, **_kwargs: object) -> str:
            raise TimeoutError("daemon offline")

    monkeypatch.setenv("ELASTRO_DAEMON_TOKEN", "test-token")
    monkeypatch.setattr(xmlrpc.client, "ServerProxy", lambda *_a, **_k: BoomProxy())
    previous = 1.25
    socket.setdefaulttimeout(previous)
    try:
        handled = _try_doc_search_fast_path(["elastro", "doc", "search", "foo"])
        assert handled is False
        assert socket.getdefaulttimeout() == previous
    finally:
        socket.setdefaulttimeout(None)


def test_pass_obj_callbacks_do_not_gain_ctx_parameter() -> None:
    params = list(inspect.signature(list_users.callback).parameters)
    assert params == ["client", "username"]


def _write_sample_csv(tmp_path) -> str:
    source = tmp_path / "sample.csv"
    source.write_text("name,age\nalice,30\nbob,41\n", encoding="utf-8")
    return str(source)


def test_ingest_profile_runs_when_connect_fails(monkeypatch, tmp_path) -> None:
    _patch_connect_auth(monkeypatch)
    result = CliRunner().invoke(cli, ["ingest", "profile", _write_sample_csv(tmp_path)])

    assert result.exit_code == 0, result.output


def test_ingest_auto_map_runs_when_connect_fails(monkeypatch, tmp_path) -> None:
    _patch_connect_auth(monkeypatch)
    result = CliRunner().invoke(
        cli, ["ingest", "auto-map", _write_sample_csv(tmp_path)]
    )

    assert result.exit_code == 0, result.output


def test_ingest_grok_builder_list_presets_when_connect_fails(monkeypatch) -> None:
    _patch_connect_auth(monkeypatch)
    result = CliRunner().invoke(cli, ["ingest", "grok-builder", "--list-presets"])

    assert result.exit_code == 0, result.output


def test_ingest_validate_local_when_connect_fails(monkeypatch, tmp_path) -> None:
    _patch_connect_auth(monkeypatch)
    result = CliRunner().invoke(
        cli, ["ingest", "validate", _write_sample_csv(tmp_path)]
    )

    assert result.exit_code == 0, result.output


def test_esql_build_without_execute_when_connect_fails(monkeypatch) -> None:
    _patch_connect_auth(monkeypatch)
    result = CliRunner().invoke(cli, ["esql", "build", "-s", "logs-*"])

    assert result.exit_code == 0, result.output


def test_ml_init_job_non_tty_exits_2_when_connect_fails(monkeypatch) -> None:
    _patch_connect_auth(monkeypatch)
    result = CliRunner().invoke(cli, ["ml", "init-job"])

    assert result.exit_code == 2
    assert "interactive wizard requires a TTY" in result.stderr


def test_tasks_cancel_without_yes_exits_2_when_connect_fails(monkeypatch) -> None:
    _patch_connect_auth(monkeypatch)
    result = CliRunner().invoke(cli, ["tasks", "cancel", "node-1:123"])

    assert result.exit_code == 2
    assert "--yes" in result.stderr


def test_cluster_settings_without_yes_exits_2_when_connect_fails(monkeypatch) -> None:
    _patch_connect_auth(monkeypatch)
    result = CliRunner().invoke(cli, ["cluster", "settings", "--enable-routing", "all"])

    assert result.exit_code == 2
    assert "--yes" in result.stderr


def test_script_delete_without_yes_exits_2_when_connect_fails(monkeypatch) -> None:
    _patch_connect_auth(monkeypatch)
    result = CliRunner().invoke(cli, ["script", "delete", "my-script"])

    assert result.exit_code == 2
    assert "--yes" in result.stderr
