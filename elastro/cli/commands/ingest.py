"""
Ingest CLI commands — pipeline management + data import/profile/validate.

Extends the existing pipeline listing and simulation commands with
Phase 1 capabilities: multi-format import, data profiling, auto-mapping
inference, and schema validation.
"""

import json
import rich_click as click
from pathlib import Path
from typing import Any, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from elastro.core.client import ElasticsearchClient


@click.group(name="ingest")
def ingest_group() -> None:
    """
    Data ingest engine and pipeline management.

    Import data from CSV, NDJSON, JSON, or SQL sources into Elasticsearch
    with optional schema validation, type coercion, and PII detection.
    """
    pass


# ---------------------------------------------------------------------------
# Existing pipeline commands (preserved)
# ---------------------------------------------------------------------------


@ingest_group.command(name="pipelines")
@click.option("--id", help="Fetch a specific pipeline ID")
@click.pass_obj
def list_pipelines(client: ElasticsearchClient, id: str) -> None:
    """
    List or fetch ingest pipelines.
    """
    console = Console()
    try:
        es = client.client
        res = es.ingest.get_pipeline(id=id) if id else es.ingest.get_pipeline()

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Pipeline ID")
        table.add_column("Description")
        table.add_column("Version")
        table.add_column("Processor Count")

        for k, v in res.items():
            table.add_row(
                k,
                str(v.get("description", "N/A")),
                str(v.get("version", "N/A")),
                str(len(v.get("processors", []))),
            )

        console.print(table)
    except Exception as e:
        console.print(f"[bold red]Ingest Error:[/bold red] {str(e)}")


@ingest_group.command(name="simulate")
@click.argument("id")
@click.option(
    "--doc",
    "-d",
    help="Raw JSON Document String to simulate against the ingest nodes",
)
@click.option(
    "--file",
    "-f",
    type=click.File("r"),
    help="Path to a JSON document file to simulate",
)
@click.pass_obj
def simulate_pipeline(
    client: ElasticsearchClient,
    id: str,
    doc: Optional[str],
    file: Any,
) -> None:
    """
    Simulate a document through an ingest pipeline.

    Provide the document via --doc (JSON string) or --file (JSON file).

    Examples:

    Simulate with inline JSON:
    ```bash
    elastro ingest simulate my-pipeline --doc '{"message": "hello world"}'
    ```

    Simulate from file:
    ```bash
    elastro ingest simulate my-pipeline --file ./sample.json
    ```
    """
    console = Console()

    if not doc and not file:
        console.print("[bold red]Error:[/bold red] Provide either --doc or --file")
        raise SystemExit(1)

    try:
        es = client.client

        if file:
            doc_json = json.load(file)
        else:
            doc_json = json.loads(doc)  # type: ignore[arg-type]

        if "_source" not in doc_json:
            doc_json = {"_source": doc_json}

        body = {"docs": [doc_json]}
        res = es.ingest.simulate(id=id, body=body)

        console.print(f"[bold green]Simulation Results for Pipeline: {id}[/bold green]")
        for doc_res in res.get("docs", []):
            if "error" in doc_res:
                console.print("[bold red]ERROR![/bold red]")
                console.print(doc_res["error"])
            else:
                console.print(doc_res.get("doc", {}))

    except json.JSONDecodeError:
        console.print(
            "[bold red]Simulation Error:[/bold red] The document must be valid JSON."
        )
    except Exception as e:
        console.print(f"[bold red]Simulation Error:[/bold red] {str(e)}")


# ---------------------------------------------------------------------------
# Result display helper
# ---------------------------------------------------------------------------


def _display_result(console: Console, result: Any) -> None:
    """Render an IngestResult summary table to the console."""
    status = (
        "[bold green]SUCCESS[/bold green]"
        if result.total_failed == 0
        else "[bold yellow]COMPLETED WITH ERRORS[/bold yellow]"
    )
    console.print(f"\n{status}")

    results_table = Table(show_header=False, box=None)
    results_table.add_column("Metric", style="dim")
    results_table.add_column("Value", style="bold")

    results_table.add_row("Documents Read", str(result.total_read))
    results_table.add_row("Documents Indexed", f"[green]{result.total_indexed}[/green]")
    results_table.add_row(
        "Documents Failed",
        f"[red]{result.total_failed}[/red]" if result.total_failed else "0",
    )
    results_table.add_row("Success Rate", f"{result.success_rate:.1f}%")
    results_table.add_row("Elapsed", f"{result.elapsed_seconds:.2f}s")

    if result.total_read > 0:
        rate = result.total_read / max(result.elapsed_seconds, 0.001)
        results_table.add_row("Throughput", f"{rate:,.0f} docs/sec")

    if result.dlq_path:
        results_table.add_row("Dead-Letter Queue", result.dlq_path)

    console.print(results_table)


# ---------------------------------------------------------------------------
# Phase 1: Import
# ---------------------------------------------------------------------------


@ingest_group.command(name="import", no_args_is_help=True)
@click.argument("source", type=str)
@click.option("--index", "-i", required=True, help="Target Elasticsearch index")
@click.option(
    "--format",
    "-f",
    "fmt",
    type=click.Choice(["auto", "csv", "ndjson", "json", "sql"]),
    default="auto",
    help="Source file format (auto-detects from extension)",
)
@click.option("--delimiter", help="CSV delimiter override (default: ',')")
@click.option("--encoding", default="utf-8", help="File encoding")
@click.option("--batch-size", type=int, default=2000, help="Documents per bulk request")
@click.option("--max-errors", type=int, default=100, help="Abort after N errors")
@click.option("--pipeline", help="ES ingest pipeline to apply server-side")
@click.option(
    "--validate/--no-validate", default=False, help="Enable schema validation"
)
@click.option("--strict", is_flag=True, help="Strict mode: reject on type mismatch")
@click.option("--dlq", type=click.Path(), help="Dead-letter queue output file")
@click.option("--refresh", is_flag=True, help="Refresh index after each batch")
@click.option(
    "--sql",
    "sql_query",
    type=str,
    default=None,
    help="SQL SELECT query for live database import (requires --dsn)",
)
@click.option(
    "--dsn",
    type=str,
    default=None,
    help="Database connection string (e.g. postgresql://user:pass@host/db)",
)
@click.pass_obj
def import_data(
    client: ElasticsearchClient,
    source: str,
    index: str,
    fmt: str,
    delimiter: Optional[str],
    encoding: str,
    batch_size: int,
    max_errors: int,
    pipeline: Optional[str],
    validate: bool,
    strict: bool,
    dlq: Optional[str],
    refresh: bool,
    sql_query: Optional[str],
    dsn: Optional[str],
) -> None:
    """
    Import data from CSV, NDJSON, JSON, or SQL into Elasticsearch.

    Supports streaming ingestion with progress reporting, optional schema
    validation, type coercion, and dead-letter queue for failed documents.

    Examples:

    Import a CSV file:
    ```bash
    elastro ingest import customers.csv --index customers
    ```

    Import NDJSON with validation:
    ```bash
    elastro ingest import events.ndjson --index events --validate
    ```

    Import with DLQ and pipeline:
    ```bash
    elastro ingest import data.json --index logs --pipeline my-pipeline --dlq ./failed.ndjson
    ```

    Import from stdin:
    ```bash
    cat data.csv | elastro ingest import - --index logs --format csv
    ```

    Import from a live SQL database:
    ```bash
    elastro ingest import --sql "SELECT * FROM users" --dsn postgresql://user:pass@host/db --index users
    ```

    Import a SQL dump file:
    ```bash
    elastro ingest import dump.sql --index users
    ```
    """
    from elastro.core.ingest.engine import IngestEngine

    console = Console()
    engine = IngestEngine(client)
    docs_override = None

    # SQL live import mode
    if sql_query:
        if not dsn:
            console.print(
                "[bold red]Error:[/bold red] --dsn is required when using --sql"
            )
            raise SystemExit(1)

        from elastro.core.ingest.readers import SQLReader

        sql_reader = SQLReader(dsn, sql_query)
        docs_override = sql_reader.read()

        console.print(
            Panel.fit(
                f"[bold cyan]Elastro Ingest Engine — SQL Import[/bold cyan]\n"
                f"DSN: [green]{dsn.split('@')[-1] if '@' in dsn else dsn}[/green]\n"
                f"Query: [dim]{sql_query[:80]}{'...' if len(sql_query) > 80 else ''}[/dim]\n"
                f"Target: [green]{index}[/green] | Batch: {batch_size}",
                border_style="cyan",
            )
        )
    else:
        console.print(
            Panel.fit(
                f"[bold cyan]Elastro Ingest Engine[/bold cyan]\n"
                f"Source: [green]{source}[/green]\n"
                f"Target: [green]{index}[/green]\n"
                f"Format: {fmt} | Batch: {batch_size} | Validate: {validate}",
                border_style="cyan",
            )
        )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[bold blue]{task.completed} docs"),
        console=console,
    ) as progress:
        task = progress.add_task("Ingesting...", total=None)

        result = engine.ingest(
            source,
            index,
            format=fmt,
            delimiter=delimiter,
            encoding=encoding,
            batch_size=batch_size,
            max_errors=max_errors,
            pipeline=pipeline,
            validate=validate,
            strict=strict,
            dlq_path=dlq,
            refresh=refresh,
            docs_override=docs_override,
        )

        progress.update(task, completed=result.total_read)

    _display_result(console, result)

    if result.total_failed > 0:
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# Phase 1: Profile
# ---------------------------------------------------------------------------


@ingest_group.command(name="profile", no_args_is_help=True)
@click.argument("source", type=str)
@click.option(
    "--format",
    "-f",
    "fmt",
    type=click.Choice(["auto", "csv", "ndjson", "json"]),
    default="auto",
)
@click.option("--sample-size", type=int, default=1000, help="Number of rows to sample")
@click.option("--delimiter", help="CSV delimiter override")
@click.pass_obj
def profile_data_cmd(
    client: ElasticsearchClient,
    source: str,
    fmt: str,
    sample_size: int,
    delimiter: Optional[str],
) -> None:
    """
    Profile a data source before importing.

    Analyzes field types, null rates, uniqueness, and PII risk
    without sending any data to Elasticsearch.

    Examples:

    Profile a CSV file:
    ```bash
    elastro ingest profile customers.csv
    ```

    Profile with larger sample:
    ```bash
    elastro ingest profile events.ndjson --sample-size 5000
    ```
    """
    from elastro.core.ingest.readers import read_source
    from elastro.core.ingest.validators import profile_data

    console = Console()

    console.print(
        f"[bold cyan]Profiling[/bold cyan] {source} (sample: {sample_size} rows)\n"
    )

    docs = read_source(source, format=fmt, delimiter=delimiter)
    report = profile_data(docs, sample_size=sample_size)

    # Render table
    table = Table(title=f"Data Profile ({report['total_rows_sampled']} rows sampled)")
    table.add_column("Field", style="bold cyan")
    table.add_column("Type", style="green")
    table.add_column("Non-Null %", justify="right")
    table.add_column("Unique %", justify="right")
    table.add_column("PII Risk", justify="center")
    table.add_column("Sample Values", style="dim")

    for f in report["fields"]:
        pii_style = {
            "NONE": "[green]✅ NONE[/green]",
            "HIGH": "[yellow]⚠️  HIGH[/yellow]",
            "PII": "[red]🔴 PII[/red]",
        }.get(f["pii_risk"], f["pii_risk"])

        samples = ", ".join(f["sample_values"][:3])
        if len(samples) > 50:
            samples = samples[:47] + "..."

        table.add_row(
            f["field"],
            f["inferred_type"],
            f"{f['non_null_pct']}%",
            f"{f['unique_pct']:.1f}%",
            pii_style,
            samples,
        )

    console.print(table)

    pii_count = report["pii_risk_fields"]
    if pii_count:
        console.print(
            f"\n[bold yellow]⚠ {pii_count} field(s) flagged for PII risk.[/bold yellow] "
            "Consider using --sanitize during import."
        )
    console.print(
        f"\n[dim]{report['total_fields']} fields, {report['total_rows_sampled']} rows sampled[/dim]"
    )


# ---------------------------------------------------------------------------
# Phase 1: Auto-Map
# ---------------------------------------------------------------------------


@ingest_group.command(name="auto-map", no_args_is_help=True)
@click.argument("source", type=str)
@click.option(
    "--format",
    "-f",
    "fmt",
    type=click.Choice(["auto", "csv", "ndjson", "json"]),
    default="auto",
)
@click.option("--sample-size", type=int, default=500, help="Documents to sample")
@click.option("--delimiter", help="CSV delimiter override")
@click.option("--output", "-o", type=click.Path(), help="Write mapping JSON to file")
@click.pass_obj
def auto_map(
    client: ElasticsearchClient,
    source: str,
    fmt: str,
    sample_size: int,
    delimiter: Optional[str],
    output: Optional[str],
) -> None:
    """
    Infer an Elasticsearch mapping from a data source.

    Samples the source file and uses heuristics to determine optimal
    field types. Outputs a ready-to-use ES mapping JSON.

    Examples:

    Auto-map a CSV:
    ```bash
    elastro ingest auto-map customers.csv
    ```

    Save mapping to file:
    ```bash
    elastro ingest auto-map events.ndjson --output mapping.json
    ```
    """
    from elastro.core.ingest.readers import read_source
    from elastro.core.ingest.validators import infer_mapping

    console = Console()

    console.print(
        f"[bold cyan]Inferring mapping[/bold cyan] from {source} (sample: {sample_size})\n"
    )

    docs = read_source(source, format=fmt, delimiter=delimiter)
    mapping = infer_mapping(docs, sample_size=sample_size)

    json_str = json.dumps(mapping, indent=2)

    if output:
        Path(output).write_text(json_str, encoding="utf-8")
        console.print(f"[bold green]✓[/bold green] Mapping written to {output}")
    else:
        console.print(Syntax(json_str, "json", theme="monokai"))

    props = mapping.get("mappings", {}).get("properties", {})
    console.print(f"\n[dim]{len(props)} fields inferred[/dim]")


# ---------------------------------------------------------------------------
# Phase 1: Validate (dry-run)
# ---------------------------------------------------------------------------


@ingest_group.command(name="validate", no_args_is_help=True)
@click.argument("source", type=str)
@click.option("--index", "-i", required=True, help="Target index to validate against")
@click.option(
    "--format",
    "-f",
    "fmt",
    type=click.Choice(["auto", "csv", "ndjson", "json"]),
    default="auto",
)
@click.option("--sample-size", type=int, default=500, help="Documents to validate")
@click.option("--strict", is_flag=True, help="Strict mode (no type coercion)")
@click.option("--delimiter", help="CSV delimiter override")
@click.pass_obj
def validate_data(
    client: ElasticsearchClient,
    source: str,
    index: str,
    fmt: str,
    sample_size: int,
    strict: bool,
    delimiter: Optional[str],
) -> None:
    """
    Validate data against an index mapping (dry-run).

    Fetches the mapping from the target index, validates sample documents,
    and reports any type mismatches or missing fields — without indexing.

    Examples:

    Validate CSV against existing index:
    ```bash
    elastro ingest validate customers.csv --index customers
    ```

    Strict validation (no coercion):
    ```bash
    elastro ingest validate data.json --index logs --strict
    ```
    """
    from elastro.core.ingest.readers import read_source
    from elastro.core.ingest.validators import SchemaValidator

    console = Console()

    # Fetch mapping from index
    try:
        es = client.client
        idx_info = es.indices.get(index=index)
        if hasattr(idx_info, "body"):
            idx_info = idx_info.body
        idx_data = idx_info.get(index, {})
        props = idx_data.get("mappings", {}).get("properties", {})

        if not props:
            console.print(
                f"[yellow]No mapping found for index '{index}'. Skipping validation.[/yellow]"
            )
            return

        console.print(
            f"[bold cyan]Validating[/bold cyan] {source} against [green]{index}[/green] ({len(props)} mapped fields)\n"
        )

    except Exception as e:
        console.print(f"[bold red]Error fetching mapping:[/bold red] {e}")
        raise SystemExit(1)

    validator = SchemaValidator(props, strict=strict)
    docs = read_source(source, format=fmt, delimiter=delimiter)

    total = 0
    valid = 0
    invalid = 0
    all_errors: list[dict[str, Any]] = []

    for doc in docs:
        if total >= sample_size:
            break
        total += 1
        is_valid, _, errors = validator.validate(doc)
        if is_valid:
            valid += 1
        else:
            invalid += 1
            if len(all_errors) < 20:
                all_errors.append({"row": total, "errors": errors})

    # Results
    if invalid == 0:
        console.print(f"[bold green]✓ All {total} documents valid[/bold green]")
    else:
        console.print(
            f"[bold yellow]⚠ {invalid}/{total} documents have validation errors[/bold yellow]\n"
        )

        err_table = Table(title="Validation Errors (first 20)")
        err_table.add_column("Row", style="dim", justify="right")
        err_table.add_column("Errors", style="red")

        for entry in all_errors:
            err_table.add_row(
                str(entry["row"]),
                "; ".join(entry["errors"]),
            )

        console.print(err_table)

    mode = "strict" if strict else "coerce"
    console.print(
        f"\n[dim]Mode: {mode} | {total} docs checked | {valid} valid, {invalid} invalid[/dim]"
    )
