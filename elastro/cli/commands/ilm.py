import rich_click as click
import json
from typing import Dict, Any, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from elastro.core.client import ElasticsearchClient
from elastro.core.ilm import IlmManager
from elastro.core.errors import OperationError
from elastro.cli.completion import complete_policies, complete_indices

console = Console()


@click.group("ilm")
def ilm_group() -> None:
    """Manage Index Lifecycle Management (ILM) policies."""
    pass


@ilm_group.command("list")
@click.option(
    "--full", is_flag=True, help="Show full JSON definition (limited to 2 policies)"
)
@click.pass_obj
def list_policies(client: ElasticsearchClient, full: bool) -> None:
    """
    List all ILM policies.

    Shows a summary of all Index Lifecycle Management policies.

    Examples:

    List all policies (summary table):
    ```bash
    elastro ilm list
    ```

    Show full JSON details (limited to first 2):
    ```bash
    elastro ilm list --full
    ```
    """
    manager = IlmManager(client)
    try:
        policies = manager.list_policies()

        if full:
            # Full JSON Output limited to 2
            console.print(
                Panel(
                    "[yellow]Displaying first 2 policies only. Use 'get' command for specific policy details.[/]",
                    title="⚠️  Output Limit",
                    border_style="yellow",
                )
            )
            limited_policies = policies[:2]
            click.echo(json.dumps(limited_policies, indent=2))
        else:
            # Table Output
            table = Table(title="ILM Policies", box=box.ROUNDED)
            table.add_column("Name", style="cyan", no_wrap=True)
            table.add_column("Phases", style="green")
            table.add_column("Managed", justify="center")
            table.add_column("Modified", style="dim")

            for p in policies:
                name = p.get("name", "N/A")
                policy_def = p.get("policy", {})
                phases = ", ".join(policy_def.get("phases", {}).keys())
                managed = "Yes" if p.get("_meta", {}).get("managed", False) else "No"
                modified = p.get("modified_date", "")

                table.add_row(name, phases, managed, modified)

            console.print(table)

    except OperationError as e:
        click.echo(f"Error listing policies: {str(e)}", err=True)
        exit(1)


@ilm_group.command("get", no_args_is_help=True)
@click.argument("name", type=str, shell_complete=complete_policies)
@click.pass_obj
def get_policy(client: ElasticsearchClient, name: str) -> None:
    """
    Get an ILM policy definition.

    Retrieves the full JSON definition of a specific lifecycle policy.

    Examples:

    Get full definition of a policy:
    ```bash
    elastro ilm get my-lifecycle-policy
    ```
    """
    manager = IlmManager(client)
    try:
        policy = manager.get_policy(name)
        click.echo(json.dumps(policy, indent=2))
    except OperationError as e:
        click.echo(f"Error getting policy: {str(e)}", err=True)
        exit(1)


@ilm_group.command("create", no_args_is_help=True)
@click.argument("name", type=str)
@click.option(
    "--file",
    type=click.Path(exists=True, readable=True),
    required=False,
    help="Policy definition file (JSON)",
)
@click.pass_obj
def create_policy(client: ElasticsearchClient, name: str, file: Optional[str]) -> None:
    """
    Create or update an ILM policy.

    If [--file] is provided, the policy is created from the JSON file.
    Otherwise, an interactive wizard will launch to help you build the policy.

    Examples:

    Launch Interactive Wizard:
    ```bash
    elastro ilm create my-new-policy
    ```

    Create from JSON file:
    ```bash
    elastro ilm create my-policy --file ./policy.json
    ```
    """
    manager = IlmManager(client)

    try:
        if file:
            with open(file, "r") as f:
                policy = json.load(f)
        else:
            policy = run_ilm_wizard(name)
            if not policy:  # User cancelled
                return

        if manager.create_policy(name, policy):
            click.echo(f"Policy '{name}' created/updated.")
        else:
            click.echo("Creation not acknowledged.")
    except Exception as e:
        click.echo(f"Error creating policy: {str(e)}", err=True)
        exit(1)


def run_ilm_wizard(name: str) -> Optional[Dict[str, Any]]:
    """Run interactive wizard to build ILM policy."""
    from rich.prompt import Prompt, Confirm, IntPrompt

    console.print(
        Panel(
            f"🧙 [bold blue]ILM Policy Wizard: {name}[/]\nBuild a policy with Hot, Warm, Cold, and Delete phases.",
            border_style="blue",
        )
    )

    phases = {}

    # --- HOT PHASE ---
    if Confirm.ask("Enable [bold red]HOT[/] phase (Rollover)?", default=True):
        hot_actions: Dict[str, Any] = {}
        if Confirm.ask("  Enable Rollover?", default=True):
            rollover: Dict[str, Any] = {}
            if Confirm.ask("    Max Age?", default=True):
                rollover["max_age"] = Prompt.ask("      Value", default="30d")
            if Confirm.ask("    Max Primary Shard Size?", default=True):
                rollover["max_primary_shard_size"] = Prompt.ask(
                    "      Value", default="50gb"
                )
            if Confirm.ask("    Max Docs?", default=False):
                rollover["max_docs"] = IntPrompt.ask("      Value")
            hot_actions["rollover"] = rollover

        phases["hot"] = {"min_age": "0ms", "actions": hot_actions}

    # --- WARM PHASE ---
    if Confirm.ask("Enable [bold yellow]WARM[/] phase?", default=False):
        min_age = Prompt.ask("  Min Age (from rollover)", default="7d")
        warm_actions: Dict[str, Any] = {}

        if Confirm.ask("  Shrink Shards?", default=False):
            num_shards = IntPrompt.ask("    Number of Shards", default=1)
            warm_actions["shrink"] = {"number_of_shards": num_shards}

        if Confirm.ask("  Force Merge?", default=False):
            num_segments = IntPrompt.ask("    Max Num Segments", default=1)
            warm_actions["forcemerge"] = {"max_num_segments": num_segments}

        phases["warm"] = {"min_age": min_age, "actions": warm_actions}

    # --- COLD PHASE ---
    if Confirm.ask("Enable [bold cyan]COLD[/] phase?", default=False):
        min_age = Prompt.ask("  Min Age", default="30d")
        phases["cold"] = {
            "min_age": min_age,
            "actions": {},  # Usually allocate or freeze, keeping simple for now
        }

    # --- DELETE PHASE ---
    if Confirm.ask("Enable [bold grey]DELETE[/] phase?", default=False):
        min_age = Prompt.ask("  Min Age", default="90d")
        phases["delete"] = {"min_age": min_age, "actions": {"delete": {}}}

    policy = {"policy": {"phases": phases}}

    console.print(
        Panel(
            json.dumps(policy, indent=2),
            title="Generated Policy Preview",
            border_style="green",
        )
    )

    if Confirm.ask("Create this policy?", default=True):
        return policy
    return None


@ilm_group.command("delete", no_args_is_help=True)
@click.argument("name", type=str, shell_complete=complete_policies)
@click.option("--force", is_flag=True, help="Force deletion")
@click.pass_obj
def delete_policy(client: ElasticsearchClient, name: str, force: bool) -> None:
    """
    Delete an ILM policy.

    Removes a lifecycle policy. Note: Indices using this policy may continue to move through phases unless updated.

    Examples:

    Delete a policy:
    ```bash
    elastro ilm delete my-old-policy
    ```
    """
    manager = IlmManager(client)
    if not force and not click.confirm(f"Delete policy '{name}'?"):
        return

    try:
        if manager.delete_policy(name):
            click.echo(f"Policy '{name}' deleted.")
        else:
            click.echo("Deletion not acknowledged.")
    except OperationError as e:
        click.echo(f"Error deleting policy: {str(e)}", err=True)
        exit(1)


@ilm_group.command("explain", no_args_is_help=True)
@click.argument("index", type=str, shell_complete=complete_indices)
@click.pass_obj
def explain_lifecycle(client: ElasticsearchClient, index: str) -> None:
    """
    Explain the lifecycle state of an index.

    Detailed breakdown of step, phase, and any errors in lifecycle execution for a specific index.

    Examples:

    Explain lifecycle status for an index:
    ```bash
    elastro ilm explain my-logs-00001
    ```
    """
    manager = IlmManager(client)
    try:
        explanation = manager.explain_lifecycle(index)

        # This is a "killer feature" so let's make it look good
        console.print(
            Panel(
                json.dumps(explanation, indent=2),
                title=f"Lifecycle Explanation: [bold]{index}[/bold]",
                border_style="blue",
            )
        )

        # Highlight key issues if any (e.g. step_info)
        if "step_info" in explanation:
            console.print("[bold red]Step Info (Potential Error):[/]")
            console.print(explanation["step_info"])

    except OperationError as e:
        click.echo(f"Error explaining lifecycle: {str(e)}", err=True)
        exit(1)


@ilm_group.command("start")
@click.pass_obj
def start_ilm(client: ElasticsearchClient) -> None:
    """
    Start the ILM service.

    Starts the Index Lifecycle Management feature if it is stopped.

    Examples:

    Start ILM service:
    ```bash
    elastro ilm start
    ```
    """
    manager = IlmManager(client)
    try:
        if manager.start_ilm():
            click.echo("ILM service started.")
        else:
            click.echo("Start not acknowledged.")
    except OperationError as e:
        click.echo(f"Error starting ILM: {str(e)}", err=True)
        exit(1)


@ilm_group.command("stop")
@click.pass_obj
def stop_ilm(client: ElasticsearchClient) -> None:
    """
    Stop the ILM service.

    Halts all lifecycle management operations.

    Examples:

    Stop ILM service:
    ```bash
    elastro ilm stop
    ```
    """
    manager = IlmManager(client)
    try:
        if manager.stop_ilm():
            click.echo("ILM service stopped.")
        else:
            click.echo("Stop not acknowledged.")
    except OperationError as e:
        click.echo(f"Error stopping ILM: {str(e)}", err=True)
        exit(1)
