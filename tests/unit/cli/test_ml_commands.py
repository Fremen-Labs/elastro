"""CLI tests for machine learning commands."""

from unittest.mock import MagicMock

from click.testing import CliRunner

from elastro.cli.commands.ml import ml_group


def test_init_job_non_tty_exits_2() -> None:
    client = MagicMock()
    result = CliRunner().invoke(ml_group, ["init-job"], obj=client)

    assert result.exit_code == 2
    assert "interactive wizard requires a TTY" in result.stderr
    assert result.stdout == ""
    client.client.ml.put_job.assert_not_called()
    client.client.ml.put_datafeed.assert_not_called()
