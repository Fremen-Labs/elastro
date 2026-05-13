"""
CLI commands for ES|QL query execution.

Provides:
- ``elastro esql query`` — execute an ES|QL query string or file
- ``elastro esql build`` — interactively build an ES|QL query using the fluent API
"""

import json
import sys
from pathlib import Path
from typing import Optional

import rich_click as click
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich import box

from elastro.core.client import ElasticsearchClient


@click.group("esql")
def esql_group() -> None:
    """
    ES|QL query builder and executor.

    Execute ES|QL queries against Elasticsearch with rich output
    formatting and a fluent query builder.
    """
    pass


@esql_group.command("query")
@click.argument("query_string", required=False)
@click.option(
    "--file",
    "-f",
    "query_file",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    help="Path to a .esql file containing the query",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json", "csv", "raw"], case_sensitive=False),
    default="table",
    help="Output format (default: table)",
)
@click.option(
    "--columnar",
    is_flag=True,
    help="Return results in columnar format",
)
@click.option(
    "--limit",
    "-n",
    type=int,
    default=None,
    help="Override LIMIT in the query (appends if not present)",
)
@click.option(
    "--save",
    type=click.Path(file_okay=True, dir_okay=False),
    default=None,
    help="Save results to a file (JSON or CSV based on extension)",
)
@click.pass_obj
def esql_query(
    client: ElasticsearchClient,
    query_string: Optional[str],
    query_file: Optional[str],
    output_format: str,
    columnar: bool,
    limit: Optional[int],
    save: Optional[str],
) -> None:
    """
    Execute an ES|QL query.

    Pass a query string directly or use --file to load from disk.

    Examples:

    ```bash
    elastro esql query "FROM logs-* | WHERE status >= 400 | LIMIT 10"
    ```

    ```bash
    elastro esql query --file my_query.esql --format json
    ```

    Pipe-friendly with --format csv:
    ```bash
    elastro esql query "FROM metrics-* | STATS avg(cpu) BY host" --format csv
    ```
    """
    console = Console()

    # Resolve query source
    if query_file:
        query_text = Path(query_file).read_text(encoding="utf-8").strip()
    elif query_string:
        query_text = query_string.strip()
    else:
        # Read from stdin if piped
        if not sys.stdin.isatty():
            query_text = sys.stdin.read().strip()
        else:
            console.print(
                "[bold red]Error:[/bold red] Provide a query string, --file, or pipe via stdin."
            )
            raise SystemExit(1)

    if not query_text:
        console.print("[bold red]Error:[/bold red] Empty query.")
        raise SystemExit(1)

    # Append limit override if requested
    if limit is not None:
        # Remove existing LIMIT if present, then append
        lines = query_text.split("|")
        lines = [l.strip() for l in lines if not l.strip().upper().startswith("LIMIT")]
        lines.append(f"LIMIT {limit}")
        query_text = " | ".join(lines)

    # Display the query being executed
    console.print(
        Panel(
            Syntax(query_text, "sql", theme="monokai", word_wrap=True),
            title="[bold cyan]ES|QL Query[/bold cyan]",
            border_style="cyan",
            padding=(0, 1),
        )
    )

    # Execute
    try:
        body = {"query": query_text}
        if columnar:
            body["columnar"] = True

        response = client._client.esql.query(body=body)

        # Handle ObjectApiResponse
        if hasattr(response, "body"):
            result = response.body
        elif isinstance(response, dict):
            result = response
        else:
            result = response

    except AttributeError:
        # Fallback for older elasticsearch-py without esql namespace
        try:
            response = client._client.perform_request(
                "POST",
                "/_query",
                body={"query": query_text, **({"columnar": True} if columnar else {})},
            )
            result = response if isinstance(response, dict) else json.loads(response)
        except Exception as e:
            console.print(
                f"[bold red]Error:[/bold red] ES|QL requires Elasticsearch 8.11+. {e}"
            )
            raise SystemExit(1)
    except Exception as e:
        console.print(f"[bold red]Query failed:[/bold red] {e}")
        raise SystemExit(1)

    # Extract columns and values
    columns = result.get("columns", [])
    values = result.get("values", [])

    col_names = [c.get("name", f"col_{i}") for i, c in enumerate(columns)]

    if not values:
        console.print("[dim]No results returned.[/dim]")
        return

    # Format output
    if output_format == "table":
        _render_table(console, col_names, values)
    elif output_format == "json":
        _render_json(console, col_names, values)
    elif output_format == "csv":
        _render_csv(col_names, values)
    elif output_format == "raw":
        console.print_json(json.dumps(result, default=str))

    # Summary
    console.print(
        f"\n[dim]{len(values)} row(s) returned, {len(col_names)} column(s)[/dim]"
    )

    # Save to file
    if save:
        _save_results(save, col_names, values)
        console.print(f"[green]Results saved to {save}[/green]")


@esql_group.command("build")
@click.option("--source", "-s", required=True, help="Index pattern for FROM clause")
@click.option(
    "--where",
    "-w",
    "where_clauses",
    multiple=True,
    help="WHERE condition(s) — can be repeated",
)
@click.option(
    "--eval",
    "-e",
    "eval_exprs",
    multiple=True,
    help="EVAL expression(s) — can be repeated",
)
@click.option(
    "--stats",
    "stats_exprs",
    multiple=True,
    help="STATS aggregation(s) — can be repeated",
)
@click.option("--by", "stats_by", default=None, help="STATS ... BY field(s)")
@click.option(
    "--sort",
    "sort_fields",
    multiple=True,
    help="SORT field(s) — can be repeated",
)
@click.option("--sort-order", type=click.Choice(["ASC", "DESC"]), default="ASC")
@click.option("--keep", "keep_fields", multiple=True, help="KEEP field(s)")
@click.option("--drop", "drop_fields", multiple=True, help="DROP field(s)")
@click.option("--limit", "-n", type=int, default=None, help="LIMIT value")
@click.option(
    "--execute",
    "-x",
    is_flag=True,
    help="Execute the built query immediately",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json", "csv", "raw"], case_sensitive=False),
    default="table",
    help="Output format when --execute is used",
)
@click.pass_obj
def esql_build(
    client: ElasticsearchClient,
    source: str,
    where_clauses: tuple,
    eval_exprs: tuple,
    stats_exprs: tuple,
    stats_by: Optional[str],
    sort_fields: tuple,
    sort_order: str,
    keep_fields: tuple,
    drop_fields: tuple,
    limit: Optional[int],
    execute: bool,
    output_format: str,
) -> None:
    """
    Build an ES|QL query using CLI flags.

    Constructs a query using the fluent builder API and either
    prints the rendered ES|QL or executes it directly.

    Examples:

    Build and print:
    ```bash
    elastro esql build -s "logs-*" -w "status >= 400" --stats "count = COUNT(*)" --by host --limit 10
    ```

    Build and execute:
    ```bash
    elastro esql build -s "logs-*" -w "status >= 400" --limit 5 --execute
    ```
    """
    from elastro.core.esql import ESQLQuery

    console = Console()

    q = ESQLQuery(source)
    for w in where_clauses:
        q.where(w)
    for e in eval_exprs:
        q.eval(e)
    if stats_exprs:
        by = [b.strip() for b in stats_by.split(",")] if stats_by else None
        q.stats(*stats_exprs, by=by)
    for s in sort_fields:
        q.sort(s, order=sort_order)
    if keep_fields:
        q.keep(*keep_fields)
    if drop_fields:
        q.drop(*drop_fields)
    if limit is not None:
        q.limit(limit)

    query_text = q.build()

    console.print(
        Panel(
            Syntax(query_text, "sql", theme="monokai", word_wrap=True),
            title="[bold cyan]Built ES|QL Query[/bold cyan]",
            border_style="cyan",
            padding=(0, 1),
        )
    )

    if execute:
        # Re-invoke query execution
        ctx = click.get_current_context()
        ctx.invoke(
            esql_query,
            query_string=query_text,
            query_file=None,
            output_format=output_format,
            columnar=False,
            limit=None,
            save=None,
        )


# ---------------------------------------------------------------------------
# Output renderers
# ---------------------------------------------------------------------------


def _render_table(console: Console, columns: list, values: list) -> None:
    """Render results as a Rich table."""
    table = Table(box=box.ROUNDED, show_lines=False, highlight=True)
    for col in columns:
        table.add_column(col, style="cyan", overflow="fold")

    for row in values:
        table.add_row(*(str(v) if v is not None else "[dim]null[/dim]" for v in row))

    console.print(table)


def _render_json(console: Console, columns: list, values: list) -> None:
    """Render results as JSON array of objects."""
    rows = [dict(zip(columns, row)) for row in values]
    console.print_json(json.dumps(rows, default=str, indent=2))


def _render_csv(columns: list, values: list) -> None:
    """Render results as CSV to stdout (pipe-friendly)."""
    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    for row in values:
        writer.writerow(row)
    print(output.getvalue(), end="")


def _save_results(path: str, columns: list, values: list) -> None:
    """Save results to a file (JSON or CSV based on extension)."""
    p = Path(path)
    if p.suffix.lower() == ".csv":
        import csv

        with open(p, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            for row in values:
                writer.writerow(row)
    else:
        rows = [dict(zip(columns, row)) for row in values]
        with open(p, "w") as f:
            json.dump(rows, f, indent=2, default=str)
