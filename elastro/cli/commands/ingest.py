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


# ---------------------------------------------------------------------------
# Phase 2: Pipeline subgroup
# ---------------------------------------------------------------------------


@ingest_group.group(name="pipeline")
def pipeline_group() -> None:
    """Manage Elasticsearch ingest pipelines.

    Build, deploy, and manage ingest pipelines interactively
    or from file definitions.
    """
    pass


# ---------------------------------------------------------------------------
# Phase 2: Pipeline Wizard
# ---------------------------------------------------------------------------

# Available processor types for the wizard
_PROCESSOR_TYPES = [
    ("grok", "Parse unstructured text with Grok patterns"),
    ("date", "Parse and normalize timestamps"),
    ("geoip", "Enrich IP addresses with geo data"),
    ("convert", "Convert field types (string → int, etc.)"),
    ("rename", "Rename fields"),
    ("remove", "Remove fields"),
    ("lowercase", "Convert field values to lowercase"),
    ("uppercase", "Convert field values to uppercase"),
    ("gsub", "Regex find-and-replace on field values"),
    ("set", "Set a field to a static or template value"),
    ("redact", "Redact PII patterns from fields"),
    ("dissect", "Delimiter-based field extraction"),
    ("script", "Custom Painless script"),
]


@pipeline_group.command(name="wizard")
@click.pass_obj
def pipeline_wizard(client: ElasticsearchClient) -> None:
    """Interactively build and deploy an Elasticsearch ingest pipeline.

    Walks through processor selection and configuration, previews
    the resulting JSON, and optionally deploys to the cluster.

    Example:

    ```bash
    elastro ingest pipeline wizard
    ```
    """
    from rich.prompt import Confirm, IntPrompt, Prompt

    from elastro.core.ingest.pipeline_builder import IngestPipelineBuilder

    console = Console()
    console.print(
        Panel.fit(
            "[bold cyan]Elastro Ingest Pipeline Builder[/bold cyan]\n"
            "Build a production-ready ingest pipeline interactively.",
            border_style="cyan",
        )
    )

    # --- Step 1: Pipeline metadata ---
    pipeline_id = Prompt.ask("\n[bold]1. Pipeline ID[/bold]", default="my-pipeline")
    desc = Prompt.ask("[bold]2. Description[/bold]", default="")

    builder = IngestPipelineBuilder(pipeline_id)
    if desc:
        builder.description(desc)

    # --- Step 2: Select processors ---
    console.print("\n[bold]3. Select processors to add:[/bold]")
    for i, (name, description) in enumerate(_PROCESSOR_TYPES, 1):
        console.print(f"   {i:2d}. [cyan]{name:<12}[/cyan] — {description}")

    selected_input = Prompt.ask(
        "\n   Enter processor numbers (comma-separated)",
        default="1",
    )
    selected_indices: list[int] = []
    for part in selected_input.split(","):
        part = part.strip()
        if part.isdigit():
            idx = int(part) - 1
            if 0 <= idx < len(_PROCESSOR_TYPES):
                selected_indices.append(idx)

    if not selected_indices:
        console.print("[yellow]No processors selected. Aborting.[/yellow]")
        return

    selected_processors = [_PROCESSOR_TYPES[i] for i in selected_indices]
    console.print(
        f"\n   [green]✓ Selected:[/green] "
        + ", ".join(p[0] for p in selected_processors)
    )

    # --- Step 3: Configure each processor ---
    for proc_name, proc_desc in selected_processors:
        console.print(f"\n[bold]Configure [cyan]{proc_name}[/cyan]:[/bold]")
        _configure_processor(builder, proc_name, console)

    # --- Step 4: On-failure handler ---
    if Confirm.ask(
        "\n[bold]4. Add on_failure handler?[/bold] (route errors to a DLQ index)",
        default=False,
    ):
        dlq_index = Prompt.ask(
            "   Dead-letter index name", default=f"failed-{pipeline_id}"
        )
        builder.on_failure(dlq_index)
        console.print(f"   [green]✓ On-failure → {dlq_index}[/green]")

    # --- Step 5: Preview ---
    pipeline_json = builder.build()
    json_str = json.dumps(pipeline_json, indent=2)
    console.print("\n[bold]5. Pipeline Preview:[/bold]")
    console.print(Syntax(json_str, "json", theme="monokai"))
    console.print(f"\n[dim]{builder.processor_count} processor(s) configured[/dim]")

    # --- Step 6: Deploy ---
    if Confirm.ask(
        f"\n[bold]Deploy pipeline '{pipeline_id}' to cluster?[/bold]",
        default=False,
    ):
        try:
            builder.deploy(client, pipeline_id=pipeline_id)
            console.print(
                f"\n[bold green]✓ Pipeline '{pipeline_id}' deployed "
                f"successfully![/bold green]"
            )
        except Exception as e:
            console.print(f"\n[bold red]Deploy failed:[/bold red] {e}")
    else:
        # Offer to save to file
        if Confirm.ask("Save pipeline JSON to file?", default=True):
            output_path = Prompt.ask("   Output file", default=f"{pipeline_id}.json")
            Path(output_path).write_text(json_str, encoding="utf-8")
            console.print(f"   [green]✓ Saved to {output_path}[/green]")


def _configure_processor(
    builder: Any,
    proc_name: str,
    console: Console,
) -> None:
    """Prompt the user for processor-specific configuration."""
    from rich.prompt import Prompt

    if proc_name == "grok":
        field = Prompt.ask("   Field to parse", default="message")
        pattern = Prompt.ask("   Grok pattern", default="%{COMBINEDAPACHELOG}")
        builder.grok(field, [pattern])

    elif proc_name == "date":
        field = Prompt.ask("   Source field", default="timestamp")
        fmt = Prompt.ask("   Date format", default="dd/MMM/yyyy:HH:mm:ss Z")
        target = Prompt.ask("   Target field", default="@timestamp")
        builder.date(field, [fmt], target_field=target)

    elif proc_name == "geoip":
        field = Prompt.ask("   IP address field", default="clientip")
        builder.geoip(field)

    elif proc_name == "convert":
        field = Prompt.ask("   Field to convert", default="status_code")
        target_type = Prompt.ask(
            "   Target type",
            default="integer",
        )
        builder.convert(field, target_type)

    elif proc_name == "rename":
        field = Prompt.ask("   Source field")
        target = Prompt.ask("   Target field name")
        builder.rename(field, target)

    elif proc_name == "remove":
        field = Prompt.ask("   Field to remove")
        builder.remove(field, ignore_missing=True)

    elif proc_name == "lowercase":
        field = Prompt.ask("   Field to lowercase")
        builder.lowercase(field)

    elif proc_name == "uppercase":
        field = Prompt.ask("   Field to uppercase")
        builder.uppercase(field)

    elif proc_name == "gsub":
        field = Prompt.ask("   Field")
        pattern = Prompt.ask("   Regex pattern")
        replacement = Prompt.ask("   Replacement string")
        builder.gsub(field, pattern, replacement)

    elif proc_name == "set":
        field = Prompt.ask("   Field name")
        value = Prompt.ask("   Value (static or {{template}})")
        builder.set_field(field, value)

    elif proc_name == "redact":
        field = Prompt.ask("   Field to redact", default="message")
        pattern = Prompt.ask(
            "   Grok redaction pattern", default="%{EMAILADDRESS:REDACTED}"
        )
        builder.redact(field, [pattern])

    elif proc_name == "dissect":
        field = Prompt.ask("   Field to parse", default="message")
        pattern = Prompt.ask("   Dissect pattern")
        builder.dissect(field, pattern)

    elif proc_name == "script":
        source = Prompt.ask("   Painless script source")
        builder.script(source)

    console.print(f"   [green]✓ {proc_name} configured[/green]")


# ---------------------------------------------------------------------------
# Phase 2: Pipeline create / delete
# ---------------------------------------------------------------------------


@pipeline_group.command(name="create", no_args_is_help=True)
@click.argument("pipeline_id", type=str)
@click.option(
    "--file",
    "-f",
    "pipeline_file",
    type=click.File("r"),
    required=True,
    help="Path to pipeline definition JSON file",
)
@click.pass_obj
def pipeline_create(
    client: ElasticsearchClient,
    pipeline_id: str,
    pipeline_file: Any,
) -> None:
    """Deploy an ingest pipeline from a JSON file.

    Example:

    ```bash
    elastro ingest pipeline create web-logs --file ./pipeline.json
    ```
    """
    console = Console()
    try:
        body = json.load(pipeline_file)
        es = client.client
        es.ingest.put_pipeline(id=pipeline_id, body=body)
        proc_count = len(body.get("processors", []))
        console.print(
            f"[bold green]✓ Pipeline '{pipeline_id}' deployed "
            f"({proc_count} processors)[/bold green]"
        )
    except json.JSONDecodeError:
        console.print("[bold red]Error:[/bold red] File is not valid JSON.")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[bold red]Error deploying pipeline:[/bold red] {e}")
        raise SystemExit(1)


@pipeline_group.command(name="delete", no_args_is_help=True)
@click.argument("pipeline_id", type=str)
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.pass_obj
def pipeline_delete(
    client: ElasticsearchClient,
    pipeline_id: str,
    yes: bool,
) -> None:
    """Delete an ingest pipeline.

    Example:

    ```bash
    elastro ingest pipeline delete web-logs
    ```
    """
    from rich.prompt import Confirm

    console = Console()

    if not yes:
        if not Confirm.ask(
            f"Delete pipeline [bold red]{pipeline_id}[/bold red]?",
            default=False,
        ):
            console.print("[dim]Aborted.[/dim]")
            return

    try:
        es = client.client
        es.ingest.delete_pipeline(id=pipeline_id)
        console.print(f"[bold green]✓ Pipeline '{pipeline_id}' deleted[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# Phase 2: Grok Builder
# ---------------------------------------------------------------------------


@ingest_group.command(name="grok-builder")
@click.option(
    "--sample",
    "-s",
    "samples",
    multiple=True,
    help="Sample log line(s) to analyze (repeatable)",
)
@click.option(
    "--file",
    "-f",
    "sample_file",
    type=click.File("r"),
    help="File containing sample log lines (one per line)",
)
@click.option(
    "--preset",
    type=str,
    default=None,
    help="Use a named preset (apache_combined, syslog, nginx_combined, etc.)",
)
@click.option(
    "--list-presets",
    is_flag=True,
    help="List available preset log formats",
)
@click.option(
    "--field",
    "source_field",
    default="message",
    help="Source field name for the Grok processor",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Save generated pipeline JSON to file",
)
@click.pass_obj
def grok_builder_cmd(
    client: ElasticsearchClient,
    samples: tuple,  # type: ignore[type-arg]
    sample_file: Any,
    preset: Optional[str],
    list_presets: bool,
    source_field: str,
    output: Optional[str],
) -> None:
    """Smart Grok pattern builder — generate patterns from sample log lines.

    Analyzes sample text and deterministically generates Grok patterns by
    matching against a comprehensive library of built-in patterns.  Supports
    preset log formats and multi-sample cross-validation.

    Examples:

    List available presets:
    ```bash
    elastro ingest grok-builder --list-presets
    ```

    Generate from inline samples:
    ```bash
    elastro ingest grok-builder -s '192.168.1.1 - - [10/Oct/2000:13:55:36 -0700] "GET / HTTP/1.0" 200 2326'
    ```

    Generate from a file of samples:
    ```bash
    elastro ingest grok-builder --file ./sample_logs.txt
    ```

    Use a preset:
    ```bash
    elastro ingest grok-builder --preset syslog
    ```
    """
    from elastro.core.ingest.grok_builder import GrokBuilder

    console = Console()
    builder = GrokBuilder()

    # --- List presets ---
    if list_presets:
        presets = builder.list_presets()
        table = Table(title="Available Grok Presets")
        table.add_column("Name", style="bold cyan")
        table.add_column("Description")
        table.add_column("Example", style="dim", max_width=60)

        for key, info in presets.items():
            table.add_row(key, info["name"], info.get("example", "")[:60])

        console.print(table)
        return

    # --- Preset mode ---
    if preset:
        result = builder.get_preset(preset)
        if result is None:
            console.print(f"[bold red]Unknown preset:[/bold red] {preset}")
            console.print("[dim]Use --list-presets to see available formats[/dim]")
            raise SystemExit(1)

        console.print(
            Panel.fit(
                f"[bold cyan]Grok Preset: {preset}[/bold cyan]",
                border_style="cyan",
            )
        )
        _display_grok_result(console, result, source_field, output)
        return

    # --- Collect samples ---
    sample_lines: list[str] = list(samples)
    if sample_file:
        sample_lines.extend(line.strip() for line in sample_file if line.strip())

    if not sample_lines:
        # Interactive mode
        from rich.prompt import Prompt

        console.print(
            Panel.fit(
                "[bold cyan]Elastro Grok Pattern Builder[/bold cyan]\n"
                "Paste sample log lines to generate a Grok pattern.\n"
                "Enter an empty line when done.",
                border_style="cyan",
            )
        )
        while True:
            line = Prompt.ask("   Sample line (empty to finish)", default="")
            if not line:
                break
            sample_lines.append(line)

    if not sample_lines:
        console.print("[yellow]No samples provided. Aborting.[/yellow]")
        return

    # --- Build pattern ---
    console.print(
        f"\n[bold cyan]Analyzing {len(sample_lines)} sample(s)...[/bold cyan]\n"
    )
    result = builder.build_pattern(sample_lines, source_field=source_field)
    _display_grok_result(console, result, source_field, output)


def _display_grok_result(
    console: Console,
    result: Any,
    source_field: str,
    output: Optional[str],
) -> None:
    """Render a GrokResult to the console."""
    # Pattern
    console.print("[bold]Generated Grok Pattern:[/bold]")
    console.print(Syntax(result.pattern, "text", theme="monokai"))

    # Fields
    if result.fields:
        console.print(f"\n[bold]Captured Fields:[/bold] {', '.join(result.fields)}")

    # Stats
    stats = Table(show_header=False, box=None)
    stats.add_column("Metric", style="dim")
    stats.add_column("Value", style="bold")

    if result.preset_name:
        stats.add_row("Preset", result.preset_name)
    stats.add_row("Confidence", f"{result.confidence:.0%}")
    if result.total_samples > 0:
        stats.add_row(
            "Match Rate",
            f"{result.matched_samples}/{result.total_samples} "
            f"({result.match_rate:.0f}%)",
        )
    stats.add_row("Fields", str(len(result.fields)))

    console.print(stats)

    # Warnings
    for w in result.warnings:
        console.print(f"[yellow]⚠ {w}[/yellow]")

    # Processor JSON
    proc = result.to_processor_dict(source_field)
    json_str = json.dumps(proc, indent=2)
    console.print("\n[bold]ES Grok Processor:[/bold]")
    console.print(Syntax(json_str, "json", theme="monokai"))

    # Save
    if output:
        Path(output).write_text(json_str, encoding="utf-8")
        console.print(f"\n[green]✓ Saved to {output}[/green]")
