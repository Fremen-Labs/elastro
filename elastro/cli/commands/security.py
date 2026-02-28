"""
Security and RBAC management commands.
"""

import rich_click as click
from rich.console import Console
from rich.table import Table

from elastro.core.client import ElasticsearchClient


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
    console = Console()
    try:
        es = client.client
        res = es.security.get_user(username=username) if username else es.security.get_user()
        
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
                "[green]Yes[/green]" if v.get("enabled") else "[red]No[/red]"
            )
            
        console.print(table)
    except Exception as e:
        console.print(f"[bold red]Security Error:[/bold red] {str(e)}")


@security_group.command(name="roles")
@click.option("--name", "-n", help="Specific role name to fetch")
@click.pass_obj
def list_roles(client: ElasticsearchClient, name: str) -> None:
    """
    List or fetch cluster mapping roles.
    """
    console = Console()
    try:
        es = client.client
        res = es.security.get_role(name=name) if name else es.security.get_role()
        
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
                " | ".join(idx_privs)[:100] + ("..." if len(" | ".join(idx_privs)) > 100 else ""),
                "Yes" if v.get("applications") else "None"
            )
            
        console.print(table)
    except Exception as e:
        console.print(f"[bold red]Security Error:[/bold red] {str(e)}")
