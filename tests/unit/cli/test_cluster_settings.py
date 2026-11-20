"""CLI tests for cluster settings mutations."""

from unittest.mock import MagicMock

from click.testing import CliRunner

from elastro.cli.commands.cluster import cluster_group


def _client() -> MagicMock:
    client = MagicMock()
    client.is_connected.return_value = True
    client.get_client.return_value = client.client
    return client


def test_enable_routing_without_yes_non_tty_exits_2() -> None:
    client = MagicMock()
    result = CliRunner().invoke(
        cluster_group, ["settings", "--enable-routing", "all"], obj=client
    )

    assert result.exit_code == 2
    assert "--yes" in result.stderr
    assert result.stdout == ""
    client.client.cluster.put_settings.assert_not_called()
    client.get_client.assert_not_called()


def test_enable_routing_interactive_decline_exits_0(monkeypatch) -> None:
    monkeypatch.setattr("elastro.cli.errors.stdin_is_tty", lambda: True)
    client = MagicMock()
    result = CliRunner().invoke(
        cluster_group,
        ["settings", "--enable-routing", "all"],
        obj=client,
        input="n\n",
    )

    assert result.exit_code == 0
    assert "Aborted" in result.stderr
    client.client.cluster.put_settings.assert_not_called()
    client.get_client.assert_not_called()


def test_enable_routing_with_yes_calls_put_settings() -> None:
    client = _client()
    client.client.cluster.put_settings.return_value = {}
    result = CliRunner().invoke(
        cluster_group, ["settings", "--enable-routing", "all", "--yes"], obj=client
    )

    assert result.exit_code == 0, result.stderr
    client.client.cluster.put_settings.assert_called_once()


def test_enable_routing_transport_error_exits_1() -> None:
    client = _client()
    client.client.cluster.put_settings.side_effect = Exception("No node reached")
    result = CliRunner().invoke(
        cluster_group, ["settings", "--enable-routing", "all", "--yes"], obj=client
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "No node reached" in result.stderr


def test_settings_view_does_not_require_yes() -> None:
    client = _client()
    client.client.cluster.get_settings.return_value = {
        "persistent": {},
        "transient": {},
    }
    result = CliRunner().invoke(cluster_group, ["settings"], obj=client)

    assert result.exit_code == 0, result.stderr
    client.client.cluster.put_settings.assert_not_called()
    client.client.cluster.get_settings.assert_called_once()
