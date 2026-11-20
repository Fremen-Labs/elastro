"""CLI tests for tasks commands."""

from unittest.mock import MagicMock

from click.testing import CliRunner

from elastro.cli.commands.tasks import tasks_group


def test_cancel_without_yes_non_tty_exits_2() -> None:
    client = MagicMock()
    result = CliRunner().invoke(tasks_group, ["cancel", "node-1:42"], obj=client)

    assert result.exit_code == 2
    assert "--yes" in result.stderr
    assert result.stdout == ""
    client.client.tasks.cancel.assert_not_called()


def test_cancel_interactive_decline_exits_0(monkeypatch) -> None:
    monkeypatch.setattr("elastro.cli.errors.stdin_is_tty", lambda: True)
    client = MagicMock()
    result = CliRunner().invoke(
        tasks_group, ["cancel", "node-1:42"], obj=client, input="n\n"
    )

    assert result.exit_code == 0
    assert "Aborted" in result.stderr
    client.client.tasks.cancel.assert_not_called()


def test_cancel_with_yes_calls_cancel_once() -> None:
    client = MagicMock()
    client.client.tasks.cancel.return_value = {}
    result = CliRunner().invoke(
        tasks_group, ["cancel", "node-1:42", "--yes"], obj=client
    )

    assert result.exit_code == 0, result.stderr
    client.client.tasks.cancel.assert_called_once_with(task_id="node-1:42")


def test_list_transport_error_exits_1() -> None:
    client = MagicMock()
    client.client.tasks.list.side_effect = Exception("No node reached")
    result = CliRunner().invoke(tasks_group, ["list"], obj=client)

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "No node reached" in result.stderr
