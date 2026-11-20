"""
Cluster management commands.
"""

from typing import Any

import rich_click as click
from rich.console import Console
from rich.table import Table

from elastro.cli.errors import confirm_or_exit, exit_from_exception
from elastro.core.client import ElasticsearchClient
from elastro.core.logger import get_logger

logger = get_logger(__name__)


@click.group(name="cluster")
def cluster_group() -> None:
    """
    Manage Elasticsearch cluster diagnostics and routing settings.
    """
    pass


@cluster_group.command(name="allocation")
@click.option("--index", "-i", help="Specific index name to check allocation for")
@click.pass_obj
def explain_allocation(client: ElasticsearchClient, index: str) -> None:
    """
    Explain unassigned shards.

    Runs GET _cluster/allocation/explain to diagnose exactly why a shard is
    sitting in an unassigned (UNASSIGNED) state, returning the node decision logic.
    """
    click.echo(
        click.style(
            "Deprecation: use 'elastro health shards --explain' instead (removal in 2.0)",
            fg="yellow",
        ),
        err=True,
    )
    console = Console()
    logger.info("cluster.allocation index=%s", index or "*")
    try:
        es = client.client

        kwargs: dict[str, Any] = {}
        if index:
            kwargs["index"] = index

        res = es.cluster.allocation_explain(**kwargs)

        console.print(f"[bold cyan]Index:[/bold cyan] {res.get('index', 'N/A')}")
        console.print(f"[bold cyan]Shard:[/bold cyan] {res.get('shard', 'N/A')}")
        console.print(f"[bold cyan]Primary:[/bold cyan] {res.get('primary', False)}")
        console.print(
            f"[bold red]Current State:[/bold red] {res.get('current_state', 'N/A')}"
        )
        console.print(
            f"[bold yellow]Unassigned Info:[/bold yellow] {res.get('unassigned_info', {}).get('reason', 'N/A')}"
        )
        console.print(
            f"[bold white]Details:[/bold white] {res.get('unassigned_info', {}).get('details', 'N/A')}"
        )

        # Check node decisions
        if "node_allocation_decisions" in res:
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Node Name")
            table.add_column("Decision")
            table.add_column("Explanation")

            for dec in res["node_allocation_decisions"]:
                table.add_row(
                    dec.get("node_name", "Unknown"),
                    dec.get("node_decision", "N/A"),
                    (
                        dec.get("deciders", [{}])[0].get("explanation", "N/A")
                        if dec.get("deciders")
                        else "N/A"
                    ),
                )
            console.print("\n[bold]Node Allocation Decisions:[/bold]")
            console.print(table)

    except Exception as exc:
        exit_from_exception(exc, logger=logger, action="explain allocation")


@cluster_group.command(name="settings")
@click.option(
    "--enable-routing",
    type=click.Choice(["all", "primaries", "new_primaries", "none"]),
    help="Update cluster.routing.allocation.enable setting (Transient)",
)
@click.option(
    "--yes",
    is_flag=True,
    help="Confirm routing changes without prompting (required when stdin is not a TTY)",
)
@click.pass_obj
def cluster_settings(
    client: ElasticsearchClient, enable_routing: str, yes: bool
) -> None:
    """
    View or update cluster routing allocation settings.

    If no options are passed, prints the current persistent and transient settings.
    """
    if enable_routing:
        confirm_or_exit(
            f"Set cluster.routing.allocation.enable to '{enable_routing}'?",
            yes=yes,
        )
    console = Console()
    logger.info(
        "cluster.settings enable_routing=%s yes=%s",
        enable_routing or "show",
        yes,
    )
    try:
        es = client.client

        if enable_routing:
            body = {"transient": {"cluster.routing.allocation.enable": enable_routing}}
            es.cluster.put_settings(body=body)
            console.print(
                f"[bold green]Successfully updated routing allocation to:[/bold green] {enable_routing}"
            )
            return

        res = es.cluster.get_settings(flat_settings=True)
        console.print("[bold cyan]Persistent Settings:[/bold cyan]")
        console.print(res.get("persistent", {}))

        console.print("\n[bold cyan]Transient Settings:[/bold cyan]")
        console.print(res.get("transient", {}))

    except Exception as exc:
        exit_from_exception(exc, logger=logger, action="cluster settings")
