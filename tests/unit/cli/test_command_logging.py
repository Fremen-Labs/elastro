"""Logging coverage and stderr pipe-compat for remaining CLI commands."""

from pathlib import Path
from unittest.mock import MagicMock

from click.testing import CliRunner

from elastro.cli import commands as commands_pkg
from elastro.cli.commands.esql import esql_group
from elastro.cli.commands.rag import rag_group
from elastro.cli.commands.snapshot import snapshot_group
from elastro.cli.commands.template import template_group
from elastro.core.errors import OperationError

_SKIP_GET_LOGGER = {"__init__.py", "index_recipes.py"}


def _client() -> MagicMock:
    client = MagicMock()
    client.is_connected.return_value = True
    client.get_client.return_value = client.client
    return client


def test_command_modules_contain_get_logger() -> None:
    commands_dir = Path(commands_pkg.__file__).parent
    missing = [
        path.name
        for path in sorted(commands_dir.glob("*.py"))
        if path.name not in _SKIP_GET_LOGGER and "get_logger" not in path.read_text()
    ]
    assert missing == []


def test_snapshot_list_error_goes_to_stderr(monkeypatch) -> None:
    manager = MagicMock()
    manager.list_snapshots.side_effect = OperationError("repo missing")
    monkeypatch.setattr(
        "elastro.cli.commands.snapshot.SnapshotManager", lambda _client: manager
    )
    result = CliRunner().invoke(snapshot_group, ["list", "backup"], obj=_client())

    assert result.exit_code == 1
    assert "repo missing" in result.stderr
    assert "Error listing snapshots" not in result.stdout


def test_rag_ingest_error_goes_to_stderr(monkeypatch, tmp_path) -> None:
    manager = MagicMock()
    manager.ingest_repository.side_effect = Exception("parse failed")
    monkeypatch.setattr(
        "elastro.cli.commands.rag.GraphRAGManager", lambda *_args, **_kwargs: manager
    )
    result = CliRunner().invoke(rag_group, ["ingest", str(tmp_path)], obj=_client())

    assert result.exit_code == 1
    assert "parse failed" in result.stderr
    assert "RAG Ingestion Failed" not in result.stdout


def test_esql_query_error_goes_to_stderr() -> None:
    client = _client()
    client.client.esql.query.side_effect = Exception("bad query")
    result = CliRunner().invoke(esql_group, ["query", "FROM logs"], obj=client)

    assert result.exit_code == 1
    assert "bad query" in result.stderr
    assert "Query failed" not in result.stdout


def test_template_wizard_deploy_error_exits_1_on_stderr(monkeypatch) -> None:
    prompts = iter(["component", "my-template"])
    confirms = iter([False, False, True])
    monkeypatch.setattr(
        "elastro.cli.commands.template.Prompt.ask",
        lambda *_args, **_kwargs: next(prompts),
    )
    monkeypatch.setattr(
        "elastro.cli.commands.template.Confirm.ask",
        lambda *_args, **_kwargs: next(confirms),
    )
    manager = MagicMock()
    manager.create.side_effect = OperationError("deploy failed")
    monkeypatch.setattr(
        "elastro.cli.commands.template.TemplateManager", lambda _client: manager
    )

    result = CliRunner().invoke(template_group, ["wizard"], obj=_client())

    assert result.exit_code == 1
    assert "deploy failed" in result.stderr
    assert "deploy failed" not in result.stdout
