"""CLI tests for painless commands."""

from unittest.mock import MagicMock

from click.testing import CliRunner

from elastro.cli.commands.painless_commands import painless_group


def test_painless_test_transport_error_exits_1(tmp_path) -> None:
    script = tmp_path / "job.painless"
    script.write_text("return 1;\n")
    client = MagicMock()
    client.get_client.return_value.perform_request.side_effect = Exception(
        "No node reached"
    )
    result = CliRunner().invoke(painless_group, ["test", str(script)], obj=client)

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "No node reached" in result.stderr
    client.get_client.return_value.perform_request.assert_called_once()
