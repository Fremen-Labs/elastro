"""
Painless scripting CLI commands.
"""

import os
import json
import click
import rich_click as rich_click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich import print as rprint
import rich.prompt
from typing import Any, Dict

console = Console()


@rich_click.group(name="painless", invoke_without_command=False, no_args_is_help=True)
def painless_group() -> None:
    """
    Develop, test, and deploy Elasticsearch Painless scripts perfectly.

    The painless CLI provides a pristine developer experience for Painless by standardizing
    context-aware scaffolding, robust null-handling, and instant mock-data execution loops.
    """
    pass


@painless_group.command(name="scaffold")
def scaffold() -> None:
    """
    Interactively scaffold a new Painless script with perfect boilerplate.

    Generates a strongly typed `.painless` file locally, specifically tailored
    to your target context (Runtime Field, Ingest Pipeline, Update, etc).
    """
    console.print(
        Panel(
            "[bold cyan]Elastro Painless Scaffolder[/bold cyan]\nLet's generate a bullet-proof script.",
            border_style="cyan",
        )
    )

    console.print("\n[bold]Painless Script Contexts:[/bold]")
    console.print(
        "The context determines what variables are available to your script (e.g., [cyan]doc[/cyan] vs [cyan]ctx[/cyan]) and how it returns data."
    )
    console.print(
        "  [bold cyan]1)[/bold cyan] Runtime Field   (Outputs a value via emit)"
    )
    console.print(
        "  [bold cyan]2)[/bold cyan] Script Field    (Returns a mapped value directly)"
    )
    console.print(
        "  [bold cyan]3)[/bold cyan] Ingest Pipeline (Mutates incoming document via 'ctx')"
    )
    console.print(
        "  [bold cyan]4)[/bold cyan] Update Script   (Mutates existing document via 'ctx._source')"
    )
    console.print()

    context_choice = rich.prompt.Prompt.ask(
        "Select the Script Context", choices=["1", "2", "3", "4"], default="1"
    )

    filename = rich.prompt.Prompt.ask(
        "Output Filename (without extension)", default="script"
    )
    filename = f"{filename}.painless"

    if os.path.exists(filename):
        overwrite = rich.prompt.Confirm.ask(
            f"[yellow]File {filename} exists. Overwrite?[/yellow]", default=False
        )
        if not overwrite:
            console.print("[red]Aborted.[/red]")
            return

    expected_inputs = rich.prompt.Prompt.ask(
        "Expected input fields (comma-separated, e.g., 'host.name, @timestamp')"
    )
    fields = [f.strip() for f in expected_inputs.split(",")] if expected_inputs else []

    # Map choice to template logic
    template = []
    template.append("// --- Elastro Painless Scaffold ---")

    if context_choice == "1":
        template.append("// Context: Runtime Field mapping")
        template.append(
            "// Objective: Use emit(value) to output data. Do NOT use return."
        )
    elif context_choice == "2":
        template.append("// Context: Script Field")
        template.append("// Objective: Return a computed value directly.")
    elif context_choice == "3":
        template.append("// Context: Ingest Pipeline Processor")
        template.append("// Objective: Mutate the document via the 'ctx' map.")
    elif context_choice == "4":
        template.append("// Context: Update API Script")
        template.append("// Objective: Mutate the document via 'ctx._source'.")

    template.append("")

    if fields and context_choice in ["1", "2"]:
        template.append("// --- Robust Null Checking ---")
        for field in fields:
            template.append(
                f"if (!doc.containsKey('{field}') || doc['{field}'].empty) {{"
            )
            if context_choice == "1":
                template.append("    // Handle missing data without crashing.")
                template.append("    return; // Fast exit for runtime fields")
            else:
                template.append("    return null;")
            template.append("}\n")

            template.append(
                f"def val_{field.replace('.', '_').replace('@', '')} = doc['{field}'].value;"
            )
        template.append("")

    template.append("// --- Logic Implementation ---")

    if context_choice == "1":
        template.append("emit('your_result_here');")
    elif context_choice == "2":
        template.append("return 'your_result_here';")
    elif context_choice == "3":
        template.append("ctx['my_new_field'] = 'computed_value';")
    elif context_choice == "4":
        template.append("ctx._source['my_new_field'] = 'computed_value';")

    with open(filename, "w") as f:
        f.write("\n".join(template))

    console.print(f"[green]✔ Successfully scaffolded {filename}[/green]")
    syntax = Syntax("\n".join(template), "java", theme="monokai", line_numbers=True)
    console.print(syntax)


from elastro.core.client import ElasticsearchClient


@painless_group.command(name="test")
@click.argument("script_file", type=click.File("r"))
@click.option("--doc", type=str, help="Mock JSON document string to test against.")
@click.option(
    "--context",
    type=str,
    default="painless_test",
    help="Painless context to test within (e.g., painless_test, score, filter).",
)
@click.option(
    "--index", type=str, help="Optional index name if the context requires it."
)
@click.pass_obj
def test_command(
    client: ElasticsearchClient,
    script_file: Any,
    doc: str,
    context: str,
    index: str,
) -> None:
    """
    Test a Painless script locally against a mock JSON document.

    Submits the local `.painless` file directly to the Elasticsearch
    `_scripts/painless/_execute` API and gracefully formats the result.

    Examples:

    Test a script field calculation:
    $ elastro painless test ./my_script.painless --doc '{"price": 10.50}'
    """
    script_source = script_file.read()

    payload: Dict[str, Any] = {"script": {"source": script_source}, "context": context}

    if index:
        payload["context_setup"] = payload.get("context_setup", {})
        payload["context_setup"]["index"] = index

    if doc:
        try:
            parsed_doc = json.loads(doc)
            payload["context_setup"] = payload.get("context_setup", {})
            payload["context_setup"]["document"] = parsed_doc
        except json.JSONDecodeError:
            console.print("[red]Error: --doc must be a valid JSON string.[/red]")
            return

    try:
        es = client.get_client()
        # the es python client perform_request signature in 8.x:
        # perform_request(method, path, headers=None, params=None, body=None)
        with console.status(
            f"[cyan]Executing script remotely in `{context}` context...[/cyan]"
        ):
            response = es.perform_request(
                "POST",
                "/_scripts/painless/_execute",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                body=payload,
            )

        console.print(
            Panel("[bold green]✔ Execution Success[/bold green]", border_style="green")
        )

        # In es python 8.x, the response object returns a named tuple where response is `.body`
        body = response.body if hasattr(response, "body") else response
        # rich print the JSON body
        console.print_json(data=body)

    except Exception as e:
        console.print(
            Panel("[bold red]✖ Execution Failed[/bold red]", border_style="red")
        )
        # Elastro custom error handling standard
        rprint(e)
