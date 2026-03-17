from elastro.utils.async_cli import coro
"""
Painless scripting management commands for the CLI.
"""

import os
import json
import tempfile
import subprocess
import rich_click as click
from typing import Any
from rich.console import Console
from rich.prompt import Prompt, Confirm
from elastro.core.client import ElasticsearchClient
from elastro.cli.output import format_output

console = Console()


@click.group("script")
def script_group() -> None:
    """
    Manage stored Painless scripts.
    """
    pass


@script_group.command("list")
@click.pass_obj
@coro
async def list_scripts(client: ElasticsearchClient)-> None:
    """
    List all stored Painless scripts.

    Warning: Elasticsearch does not natively provide an endpoint to list all
    scripts. This fetches cluster state metadata, which may be heavy.
    """
    try:
        # Pull cluster state selecting only metadata.stored_scripts
        response = await client.client.cluster.state(
            metric="metadata", filter_path="metadata.stored_scripts"
        )

        scripts = response.get("metadata", {}).get("stored_scripts", {})
        if not scripts:
            console.print("[dim]No scripts found.[/dim]")
            return

        console.print(format_output(scripts, output_format="json"))
    except Exception as e:
        console.print(f"[bold red]Error listing scripts:[/bold red] {str(e)}")


@script_group.command("get")
@click.argument("id", type=str)
@click.pass_obj
@coro
async def get_script(client: ElasticsearchClient, id: str)-> None:
    """
    Get a stored Painless script by its ID.
    """
    try:
        response = await client.client.get_script(id=id)
        console.print(format_output(response, output_format="json"))
    except Exception as e:
        console.print(f"[bold red]Error getting script '{id}':[/bold red] {str(e)}")


@script_group.command("delete")
@click.argument("id", type=str)
@click.pass_obj
@coro
async def delete_script(client: ElasticsearchClient, id: str)-> None:
    """
    Delete a stored Painless script.
    """
    if Confirm.ask(f"Are you sure you want to delete script '{id}'?"):
        try:
            response = await client.client.delete_script(id=id)
            if response.get("acknowledged"):
                console.print(
                    f"[bold green]Success![/bold green] Script '{id}' deleted."
                )
            else:
                console.print(format_output(response, output_format="json"))
        except Exception as e:
            console.print(
                f"[bold red]Error deleting script '{id}':[/bold red] {str(e)}"
            )


@script_group.command("create")
@click.argument("id", type=str)
@click.option(
    "--file",
    "-f",
    type=click.Path(exists=True),
    help="Load script payload from a file (.painless)",
)
@click.option(
    "--interactive", "-i", is_flag=True, help="Open nano/vim to write visually"
)
@click.pass_obj
@coro
async def create_script(
    client: ElasticsearchClient, id: str, file: str, interactive: bool
)-> None:
    """
    Create or update a stored Painless script.

    You can optionally open your default local editor to compose the script interactively.
    """
    script_source = ""

    if file:
        with open(file, "r") as f:
            script_source = f.read()
    elif interactive:
        # Create a temporary file and open it in the default system EDITOR
        editor = os.environ.get("EDITOR", "nano")
        with tempfile.NamedTemporaryFile(
            suffix=".painless", delete=False, mode="w+"
        ) as tf:
            tf.write(
                "// Write your Painless script here.\n// e.g., ctx._source.visits += 1\n"
            )
            tf.flush()
            temp_path = tf.name

        try:
            subprocess.call([editor, temp_path])
            with open(temp_path, "r") as f:
                script_source = f.read()
        finally:
            os.remove(temp_path)
    else:
        # Fallback to stdin prompt
        console.print(
            "Enter Painless script source (press Enter on empty line to finish):"
        )
        lines = []
        while True:
            line = input()
            if not line:
                break
            lines.append(line)
        script_source = "\n".join(lines)

    if not script_source or script_source.strip().startswith("//"):
        console.print("[dim]Empty script provided. Aborting.[/dim]")
        return

    script_payload = {"script": {"lang": "painless", "source": script_source}}

    try:
        response = await client.client.put_script(id=id, body=script_payload)
        if response.get("acknowledged"):
            console.print(f"[bold green]Success![/bold green] Script '{id}' stored.")
        else:
            console.print(format_output(response, output_format="json"))
    except Exception as e:
        console.print(f"[bold red]Error pushing script:[/bold red] {str(e)}")


@script_group.command("execute")
@click.option("--source", "-s", type=str, help="Raw script string source to test")
@click.option("--id", type=str, help="Stored script ID to execute")
@click.option(
    "--context", "-c", type=str, help="JSON context (e.g. {'score': 2})", default="{}"
)
@click.pass_obj
@coro
async def execute_script(
    client: ElasticsearchClient, source: str, id: str, context: str
)-> None:
    """
    Validate and execute a Painless script temporarily against dummy contexts.

    This heavily relies on the _scripts/painless/_execute endpoint to test syntax
    without permanently altering production data structures.
    """
    if not source and not id:
        console.print(
            "[bold red]Error:[/bold red] Must provide either --source or --id."
        )
        return

    try:
        ctx_data = json.loads(context)
    except json.JSONDecodeError:
        console.print("[bold red]Error:[/bold red] Invalid JSON context maps provided.")
        return

    payload: dict[str, Any] = {}
    if source:
        payload["script"] = {"lang": "painless", "source": source}
    elif id:
        payload["script"] = {"id": id}

    # Bind test context
    if ctx_data:
        payload["context"] = "score"  # default test endpoint context
        payload["context_setup"] = {"document": ctx_data}

    try:
        response = await client.client.perform_request(
            "POST", "/_scripts/painless/_execute", body=payload
        )
        console.print("[bold green]Execution Result:[/bold green]")
        console.print(format_output(response, output_format="json"))
    except Exception as e:
        console.print(f"[bold red]Execution Error:[/bold red] {str(e)}")
