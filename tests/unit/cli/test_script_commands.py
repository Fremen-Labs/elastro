"""CLI tests for stored script commands."""

from unittest.mock import MagicMock

from click.testing import CliRunner

from elastro.cli.commands.script import script_group


def _client() -> MagicMock:
    client = MagicMock()
    client.is_connected.return_value = True
    client.get_client.return_value = client.client
    return client


def test_delete_without_yes_non_tty_exits_2() -> None:
    client = _client()
    result = CliRunner().invoke(script_group, ["delete", "my-script"], obj=client)

    assert result.exit_code == 2
    assert "--yes" in result.stderr
    assert result.stdout == ""
    client.get_client.assert_not_called()
    client.client.delete_script.assert_not_called()


def test_delete_interactive_decline_exits_0(monkeypatch) -> None:
    monkeypatch.setattr("elastro.cli.errors.stdin_is_tty", lambda: True)
    client = _client()
    result = CliRunner().invoke(
        script_group, ["delete", "my-script"], obj=client, input="n\n"
    )

    assert result.exit_code == 0
    assert "Aborted" in result.stderr
    client.get_client.assert_not_called()
    client.client.delete_script.assert_not_called()


def test_delete_with_yes_calls_delete_script() -> None:
    client = _client()
    client.client.delete_script.return_value = {"acknowledged": True}
    result = CliRunner().invoke(
        script_group, ["delete", "my-script", "--yes"], obj=client
    )

    assert result.exit_code == 0, result.stderr
    client.client.delete_script.assert_called_once_with(id="my-script")


def test_get_transport_error_exits_1() -> None:
    client = _client()
    client.client.get_script.side_effect = Exception("No node reached")
    result = CliRunner().invoke(script_group, ["get", "my-script"], obj=client)

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "No node reached" in result.stderr
