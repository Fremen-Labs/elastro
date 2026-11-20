"""
Security and RBAC management commands.
"""

import rich_click as click
from rich.console import Console
from rich.table import Table

from elastro.cli.context import require_client
from elastro.cli.errors import exit_from_exception
from elastro.core.client import ElasticsearchClient
from elastro.core.logger import get_logger
from elastro.core.security import SecurityManager

logger = get_logger(__name__)


@click.group(name="security")
def security_group() -> None:
    """
    Manage Elasticsearch RBAC native realm users and roles.
    """
    pass


@security_group.command(name="users")
@click.option("--username", "-u", help="Specific username to fetch")
@click.pass_obj
def list_users(client: ElasticsearchClient, username: str) -> None:
    """
    List or fetch native realm users.
    """
    require_client()
    console = Console()
    logger.info("security.users username=%s", username or "*")
    try:
        res = SecurityManager(client).get_users(username)

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Username")
        table.add_column("Full Name")
        table.add_column("Roles")
        table.add_column("Email")
        table.add_column("Enabled")

        for k, v in res.items():
            table.add_row(
                k,
                str(v.get("full_name", "")),
                ", ".join(v.get("roles", [])),
                str(v.get("email", "")),
                "[green]Yes[/green]" if v.get("enabled") else "[red]No[/red]",
            )

        console.print(table)
    except Exception as exc:
        exit_from_exception(exc, logger=logger, action="list users")


@security_group.command(name="roles")
@click.option("--name", "-n", help="Specific role name to fetch")
@click.pass_obj
def list_roles(client: ElasticsearchClient, name: str) -> None:
    """
    List or fetch cluster mapping roles.
    """
    require_client()
    console = Console()
    logger.info("security.roles name=%s", name or "*")
    try:
        res = SecurityManager(client).get_roles(name)

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Role Name")
        table.add_column("Cluster Privileges")
        table.add_column("Index Privileges")
        table.add_column("Applications")

        for k, v in res.items():
            idx_privs = []
            for idx in v.get("indices", []):
                names = ",".join(idx.get("names", []))
                privs = ",".join(idx.get("privileges", []))
                idx_privs.append(f"{names} ({privs})")

            table.add_row(
                k,
                ", ".join(v.get("cluster", [])),
                " | ".join(idx_privs)[:100]
                + ("..." if len(" | ".join(idx_privs)) > 100 else ""),
                "Yes" if v.get("applications") else "None",
            )

        console.print(table)
    except Exception as exc:
        exit_from_exception(exc, logger=logger, action="list roles")
