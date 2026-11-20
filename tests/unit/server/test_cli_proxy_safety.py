"""CLI proxy confirm gate: destructive argv without confirm does not spawn."""

import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from elastro.server import ElastroGUI
from elastro.server.routes.cli import (
    _CLI_OUTPUT_CAP_BYTES,
    _is_destructive_cli_argv,
    _parse_user_argv,
    _skip_global_options,
)

CLI_URL = "/api/cluster/docker-cluster/cli"

DESTRUCTIVE_COMMANDS = [
    "index delete logs --force",
    "-o json index delete logs",
    "--output=json index delete logs",
    "--profile=prod index delete logs",
    "--host=http://127.0.0.1:9200 index delete logs",
    "--config=/tmp/elastro.yaml index delete logs",
    "-c /tmp/elastro.yaml index delete logs",
    "-v index delete logs",
    "--verbose index delete logs",
    "elastro index delete logs",
    "health assess --fix --yes --force",
    "health fix --yes --force",
    "cluster settings --enable-routing=all",
    "cluster settings --enable-routing all",
    "index fix",
    "snapshot restore repo snap",
    "snapshot delete repo snap",
    "snapshot repo delete repo",
    "script delete my-script",
    "memory prune",
    "tasks cancel task-1",
    "utils templates delete t",
    "utils aliases delete a i",
    "doc delete idx 1",
    "doc bulk-delete idx",
    "datastream delete logs",
    "ilm delete policy",
    "template delete t",
]

SAFE_COMMANDS = [
    "index list",
    "template create my-template --file -",
    "health assess",
    "health assess --dry-run --fix",
    "health fix --dry-run",
    "cluster settings",
]


def _gui_client(tmp_path, *, password="elastic_password"):
    gui = ElastroGUI()
    gui.token = "test-token"
    gui.config_dir = tmp_path
    gui.config_file = tmp_path / "gui_config.json"
    gui.config_file.write_text(
        json.dumps(
            {
                "clusters": [
                    {
                        "name": "docker-cluster",
                        "host": "http://localhost:9205",
                        "auth": {"username": "elastic", "password": password},
                    }
                ]
            }
        )
    )
    return TestClient(gui.app)


def _auth_headers():
    return {"Authorization": "Bearer test-token"}


def _post(client, command, confirm=None, stdin=None):
    body = {"command": command}
    if confirm is not None:
        body["confirm"] = confirm
    if stdin is not None:
        body["stdin"] = stdin
    return client.post(CLI_URL, headers=_auth_headers(), json=body)


class TestCliArgvMatcher:
    def test_parse_strips_leading_elastro(self):
        assert _parse_user_argv("elastro index delete logs") == [
            "index",
            "delete",
            "logs",
        ]
        assert _parse_user_argv("index delete logs") == ["index", "delete", "logs"]

    def test_skip_attached_and_separate_globals(self):
        assert _skip_global_options(["--output=json", "index", "delete", "logs"]) == [
            "index",
            "delete",
            "logs",
        ]
        assert _skip_global_options(["-o", "json", "index", "delete", "logs"]) == [
            "index",
            "delete",
            "logs",
        ]
        assert _skip_global_options(["--profile=prod", "index", "delete", "logs"]) == [
            "index",
            "delete",
            "logs",
        ]
        assert _skip_global_options(
            ["--host=http://127.0.0.1:9200", "index", "delete", "logs"]
        ) == ["index", "delete", "logs"]
        assert _skip_global_options(
            ["--config=/tmp/elastro.yaml", "index", "delete", "logs"]
        ) == ["index", "delete", "logs"]
        assert _skip_global_options(["-v", "index", "delete", "logs"]) == [
            "index",
            "delete",
            "logs",
        ]

    def test_verbose_does_not_consume_command(self):
        assert _is_destructive_cli_argv(["-v", "index", "delete", "logs"]) is True

    def test_cluster_settings_enable_routing_attached(self):
        assert (
            _is_destructive_cli_argv(["cluster", "settings", "--enable-routing=all"])
            is True
        )
        assert _is_destructive_cli_argv(["cluster", "settings"]) is False

    def test_health_assess_fix_without_dry_run(self):
        assert (
            _is_destructive_cli_argv(["health", "assess", "--fix", "--yes", "--force"])
            is True
        )
        assert (
            _is_destructive_cli_argv(["health", "assess", "--fix", "--dry-run"])
            is False
        )
        assert _is_destructive_cli_argv(["health", "assess"]) is False

    def test_template_create_is_not_destructive(self):
        assert (
            _is_destructive_cli_argv(
                ["template", "create", "my-template", "--file", "-"]
            )
            is False
        )


class TestCliProxySafety:
    def test_confirm_false_does_not_spawn_destructive(self, tmp_path):
        client = _gui_client(tmp_path)
        for command in DESTRUCTIVE_COMMANDS:
            with patch("elastro.server.routes.cli.subprocess.run") as mock_run:
                response = _post(client, command, confirm=False)
            assert response.status_code == 409, command
            mock_run.assert_not_called()
            detail = response.json()["detail"]
            assert detail["code"] == "confirmation_required"
            assert isinstance(detail["argv"], list)
            assert detail["argv"]

    def test_omitted_confirm_does_not_spawn_destructive(self, tmp_path):
        client = _gui_client(tmp_path)
        with patch("elastro.server.routes.cli.subprocess.run") as mock_run:
            response = _post(client, "--output=json index delete logs")
        assert response.status_code == 409
        mock_run.assert_not_called()

    def test_acceptance_global_option_forms(self, tmp_path):
        client = _gui_client(tmp_path)
        commands = [
            "--output=json index delete logs",
            "--profile=prod index delete logs",
            "--host=http://127.0.0.1:9200 index delete logs",
            "--config=/tmp/elastro.yaml index delete logs",
            "-v index delete logs",
            "cluster settings --enable-routing=all",
        ]
        for command in commands:
            with patch("elastro.server.routes.cli.subprocess.run") as mock_run:
                response = _post(client, command, confirm=False)
            assert response.status_code == 409, command
            mock_run.assert_not_called()

    def test_template_create_still_spawns(self, tmp_path):
        client = _gui_client(tmp_path)
        mock_result = MagicMock(returncode=0, stdout="created", stderr="")
        with patch(
            "elastro.server.routes.cli.subprocess.run", return_value=mock_result
        ) as mock_run:
            response = _post(client, "template create my-template --file -")
        assert response.status_code == 200
        mock_run.assert_called_once()
        spawned = mock_run.call_args[0][0]
        assert spawned[0] == "elastro"
        assert spawned[1] == "--host"
        assert spawned[3:] == ["template", "create", "my-template", "--file", "-"]

    def test_safe_commands_spawn_without_confirm(self, tmp_path):
        client = _gui_client(tmp_path)
        mock_result = MagicMock(returncode=0, stdout="ok", stderr="")
        for command in SAFE_COMMANDS:
            with patch(
                "elastro.server.routes.cli.subprocess.run", return_value=mock_result
            ) as mock_run:
                response = _post(client, command)
            assert response.status_code == 200, command
            mock_run.assert_called_once()

    def test_confirm_true_spawns_destructive(self, tmp_path):
        client = _gui_client(tmp_path)
        mock_result = MagicMock(returncode=0, stdout="deleted", stderr="")
        with patch(
            "elastro.server.routes.cli.subprocess.run", return_value=mock_result
        ) as mock_run:
            response = _post(client, "--output=json index delete logs", confirm=True)
        assert response.status_code == 200
        mock_run.assert_called_once()
        spawned = mock_run.call_args[0][0]
        assert spawned[0] == "elastro"
        assert spawned[1] == "--host"
        assert spawned[3:] == ["--output=json", "index", "delete", "logs"]

    def test_output_capped_and_truncated_flag(self, tmp_path):
        client = _gui_client(tmp_path)
        huge = "x" * (_CLI_OUTPUT_CAP_BYTES + 64)
        mock_result = MagicMock(returncode=0, stdout=huge, stderr="")
        with patch(
            "elastro.server.routes.cli.subprocess.run", return_value=mock_result
        ):
            response = _post(client, "index list")
        assert response.status_code == 200
        payload = response.json()
        assert payload["truncated"] is True
        assert len(payload["output"].encode("utf-8")) <= _CLI_OUTPUT_CAP_BYTES

    def test_small_output_not_truncated(self, tmp_path):
        client = _gui_client(tmp_path)
        mock_result = MagicMock(returncode=0, stdout="ok", stderr="")
        with patch(
            "elastro.server.routes.cli.subprocess.run", return_value=mock_result
        ):
            response = _post(client, "index list")
        assert response.json()["truncated"] is False
        assert response.json()["output"] == "ok"

    def test_does_not_log_env_or_stdin(self, tmp_path):
        password = "super-secret-cli-password"
        stdin_body = "SECRET_STDIN_BODY"
        client = _gui_client(tmp_path, password=password)
        mock_result = MagicMock(returncode=0, stdout="ok", stderr="")
        with (
            patch(
                "elastro.server.routes.cli.subprocess.run", return_value=mock_result
            ) as mock_run,
            patch("elastro.server.routes.cli.logger.info") as mock_info,
            patch("elastro.server.routes.cli.logger.warning") as mock_warning,
            patch("elastro.server.routes.cli.logger.error") as mock_error,
        ):
            response = _post(client, "index list", confirm=True, stdin=stdin_body)
        assert response.status_code == 200
        mock_run.assert_called_once()
        assert mock_run.call_args.kwargs.get("input") == stdin_body
        logged = " ".join(
            str(call.args) + str(call.kwargs)
            for mock in (mock_info, mock_warning, mock_error)
            for call in mock.call_args_list
        )
        assert password not in logged
        assert stdin_body not in logged
        assert "ELASTIC_PASSWORD" not in logged
        assert "index" in logged
        assert mock_info.call_args.args[0] == (
            "CLI proxy spawn argv=%s exit_code=%s duration_ms=%s truncated=%s"
        )
