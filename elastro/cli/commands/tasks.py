"""
Tasks management commands.
"""

from typing import Any

import rich_click as click
from rich.console import Console
from rich.table import Table

from elastro.cli.context import require_client
from elastro.cli.errors import confirm_or_exit, exit_from_exception
from elastro.core.client import ElasticsearchClient
from elastro.core.errors import OperationError
from elastro.core.logger import get_logger

logger = get_logger(__name__)


def _node_failure_summary(failures: Any) -> str:
    """Compact node/status/reason text from a tasks.cancel node_failures list."""
    items = failures if isinstance(failures, list) else [failures]
    parts: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            parts.append(str(item))
            continue
        node = item.get("node_id") or item.get("node") or item.get("node_name")
        status = item.get("status")
        reason = item.get("reason")
        caused = item.get("caused_by")
        if not reason and isinstance(caused, dict):
            reason = caused.get("reason")
        bits = []
        if node:
            bits.append(f"node={node}")
        if status is not None:
            bits.append(f"status={status}")
        if reason:
            bits.append(f"reason={reason}")
        parts.append(" ".join(bits) if bits else str(item))
    return "; ".join(parts)


@click.group(name="tasks")
def tasks_group() -> None:
    """
    Manage long-running cluster tasks.
    """
    pass


@tasks_group.command(name="list")
@click.option(
    "--action", "-a", help="Filter by specific action prefix (e.g. *reindex*)"
)
@click.option("--detailed", "-d", is_flag=True, help="Show full detail payloads")
@click.pass_obj
def list_tasks(client: ElasticsearchClient, action: str, detailed: bool) -> None:
    """
    List active node tasks.
    """
    require_client()
    console = Console()
    logger.info("tasks.list action=%s detailed=%s", action or "*", detailed)
    try:
        es = client.client
        res = es.tasks.list(detailed=detailed, actions=action)

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Task ID")
        table.add_column("Action")
        table.add_column("Type")
        table.add_column("Start Time (ms)")
        table.add_column("Running Time (s)")
        table.add_column("Cancellable")

        nodes = res.get("nodes", {})
        count = 0
        for node_id, node_data in nodes.items():
            for task_id, task in node_data.get("tasks", {}).items():
                if (
                    "indices:data/read/search[phase/fetch/id]" in task.get("action", "")
                    and not detailed
                ):
                    continue  # Skip keeping track of the query itself

                count += 1
                table.add_row(
                    f"{node_id}:{task.get('id')}",
                    task.get("action", "N/A"),
                    task.get("type", "N/A"),
                    str(task.get("start_time_in_millis", "")),
                    f"{task.get('running_time_in_nanos', 0) / 1000000000:.2f}s",
                    (
                        "[green]Yes[/green]"
                        if task.get("cancellable")
                        else "[red]No[/red]"
                    ),
                )

        console.print(f"Found {count} active tasks:")
        console.print(table)
    except Exception as exc:
        exit_from_exception(exc, logger=logger, action="list tasks")


@tasks_group.command(name="cancel")
@click.argument("task_id")
@click.option(
    "--yes",
    is_flag=True,
    help="Confirm cancellation without prompting (required when stdin is not a TTY)",
)
@click.pass_obj
def cancel_task(client: ElasticsearchClient, task_id: str, yes: bool) -> None:
    """
    Cancel an active task.

    TASK_ID must be in format <node_id>:<task_id>.
    """
    require_client()
    confirm_or_exit(f"Cancel task '{task_id}'?", yes=yes)
    console = Console()
    logger.info("tasks.cancel task_id=%s", task_id)
    try:
        es = client.client
        res = es.tasks.cancel(task_id=task_id)

        if res.get("node_failures"):
            summary = _node_failure_summary(res["node_failures"])
            logger.error("task cancel node_failures task_id=%s %s", task_id, summary)
            raise OperationError(
                f"Task cancellation encountered node failures for {task_id}: {summary}"
            )

        console.print(
            f"[bold green]Successfully requested cancellation for: {task_id}[/bold green]"
        )
    except Exception as exc:
        exit_from_exception(exc, logger=logger, action="cancel task")
