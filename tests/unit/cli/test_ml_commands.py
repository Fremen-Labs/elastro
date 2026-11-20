"""CLI tests for machine learning commands."""

from unittest.mock import MagicMock

from click.testing import CliRunner

from elastro.cli.commands.ml import ml_group


def _client() -> MagicMock:
    client = MagicMock()
    client.is_connected.return_value = True
    client.get_client.return_value = client.client
    return client


def test_init_job_deploy_failure_exits_1(monkeypatch) -> None:
    monkeypatch.setattr("elastro.cli.commands.ml.stdin_is_tty", lambda: True)

    def fake_prompt(*_args, **kwargs):
        default = kwargs.get("default")
        return default if default is not None else "1"

    monkeypatch.setattr("elastro.cli.commands.ml.Prompt.ask", fake_prompt)
    monkeypatch.setattr("elastro.cli.commands.ml.Confirm.ask", lambda *_a, **_k: True)
    client = _client()
    client.client.ml.put_job.side_effect = Exception("No node reached")
    result = CliRunner().invoke(ml_group, ["init-job"], obj=client)

    assert result.exit_code == 1
    assert "No node reached" in result.stderr
    client.client.ml.put_job.assert_called_once()
    client.client.ml.put_datafeed.assert_not_called()


def test_init_job_non_tty_exits_2() -> None:
    client = _client()
    result = CliRunner().invoke(ml_group, ["init-job"], obj=client)

    assert result.exit_code == 2
    assert "interactive wizard requires a TTY" in result.stderr
    assert result.stdout == ""
    client.client.ml.put_job.assert_not_called()
    client.client.ml.put_datafeed.assert_not_called()
    client.get_client.assert_not_called()
