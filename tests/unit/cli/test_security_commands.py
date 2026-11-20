"""CLI tests for security commands."""

from unittest.mock import MagicMock

from click.testing import CliRunner

from elastro.cli.commands.security import security_group


def test_users_transport_error_exits_1() -> None:
    client = MagicMock()
    client.client.security.get_user.side_effect = Exception("No node reached")
    result = CliRunner().invoke(security_group, ["users"], obj=client)

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "No node reached" in result.stderr
    assert "Security Error" not in result.stdout


def test_roles_transport_error_exits_1() -> None:
    client = MagicMock()
    client.client.security.get_role.side_effect = Exception("No node reached")
    result = CliRunner().invoke(security_group, ["roles"], obj=client)

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "No node reached" in result.stderr


def test_users_success_exits_0() -> None:
    client = MagicMock()
    client.client.security.get_user.return_value = {
        "elastic": {
            "full_name": "Elastic",
            "roles": ["superuser"],
            "email": "",
            "enabled": True,
        }
    }
    result = CliRunner().invoke(security_group, ["users"], obj=client)

    assert result.exit_code == 0, result.stderr
    assert "elastic" in result.output
