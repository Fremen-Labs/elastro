"""
Tasks management commands.
"""

import rich_click as click
from rich.console import Console
from rich.table import Table

from elastro.core.client import ElasticsearchClient


@click.group(name="tasks")
def tasks_group() -> None:
    """
    Manage long-running cluster tasks.
    """
    pass


@tasks_group.command(name="list")
@click.option("--action", "-a", help="Filter by specific action prefix (e.g. *reindex*)")
@click.option("--detailed", "-d", is_flag=True, help="Show full detail payloads")
@click.pass_obj
def list_tasks(client: ElasticsearchClient, action: str, detailed: bool) -> None:
    """
    List active node tasks.
    """
    console = Console()
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
                if "indices:data/read/search[phase/fetch/id]" in task.get("action", "") and not detailed:
                    continue # Skip keeping track of the query itself
                
                count += 1
                table.add_row(
                    f"{node_id}:{task.get('id')}",
                    task.get("action", "N/A"),
                    task.get("type", "N/A"),
                    str(task.get("start_time_in_millis", "")),
                    f"{task.get('running_time_in_nanos', 0) / 1000000000:.2f}s",
                    "[green]Yes[/green]" if task.get("cancellable") else "[red]No[/red]"
                )
                
        console.print(f"Found {count} active tasks:")
        console.print(table)
    except Exception as e:
        console.print(f"[bold red]Tasks Error:[/bold red] {str(e)}")


@tasks_group.command(name="cancel")
@click.argument("task_id")
@click.pass_obj
def cancel_task(client: ElasticsearchClient, task_id: str) -> None:
    """
    Cancel an active task.
    
    TASK_ID must be in format <node_id>:<task_id>.
    """
    console = Console()
    try:
        es = client.client
        res = es.tasks.cancel(task_id=task_id)
        
        if res.get("node_failures"):
            console.print("[bold red]Task Cancellation Encountered Node Failures![/bold red]")
            console.print(res["node_failures"])
        else:
             console.print(f"[bold green]Successfully requested cancellation for: {task_id}[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Cancellation Error:[/bold red] {str(e)}")
