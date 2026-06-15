"""Health assessment and status commands."""

from typing import Optional

import rich_click as click

from elastro.core.client import ElasticsearchClient
from elastro.core.errors import OperationError
from elastro.health.manager import HealthManager
from elastro.cli.output import format_output

_VALID_WAIT_STATUSES = ("green", "yellow", "red")


def _render_cluster_health(result: dict) -> None:
    status = result.get("status", "unknown")
    status_colors = {"green": "green", "yellow": "yellow", "red": "red"}

    click.echo(
        click.style(
            f"Cluster: {result.get('cluster_name', 'unknown')} | "
            f"Status: {status} | "
            f"Nodes: {result.get('number_of_nodes', 0)} | "
            f"Data nodes: {result.get('number_of_data_nodes', 0)}",
            fg=status_colors.get(status, "white"),
        )
    )
    click.echo(format_output(result, output_format="json"))


@click.group("health")
def health_group() -> None:
    """Elasticsearch cluster health assessment and diagnostics."""


@health_group.command("status")
@click.option(
    "--level",
    type=click.Choice(["cluster", "indices", "shards"]),
    default="cluster",
    help="Health check level",
)
@click.option(
    "--wait",
    type=click.Choice(_VALID_WAIT_STATUSES),
    default=None,
    help="Wait for specified status (green, yellow, red)",
)
@click.option("--timeout", type=str, default="30s", help="Timeout for health check")
@click.pass_obj
def health_status(
    client: ElasticsearchClient,
    level: str,
    wait: Optional[str],
    timeout: str,
) -> None:
    """
    Check Elasticsearch cluster health.

    Display cluster health status (green, yellow, red).

    Examples:

    Check cluster health:
    ```bash
    elastro health status
    ```

    Wait for green status:
    ```bash
    elastro health status --wait green --timeout 60s
    ```
    """
    health_manager = HealthManager(client)

    try:
        result = health_manager.cluster_health(
            level=level,
            timeout=timeout,
            wait_for_status=wait,
        )
        _render_cluster_health(result)
    except OperationError as e:
        click.echo(f"Error checking health: {str(e)}", err=True)
        raise SystemExit(1) from e