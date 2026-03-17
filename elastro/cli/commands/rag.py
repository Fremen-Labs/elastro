from elastro.utils.async_cli import coro
"""
Graph RAG Commands for Code Flow Mapping.
"""

import rich_click as click
import os
from typing import Optional
from elastro.core.client import ElasticsearchClient
from elastro.core.rag.ingestor import GraphRAGManager
from elastro.cli.output import format_output
from rich.console import Console

console = Console()


@click.group("rag")
def rag_group() -> None:
    """
    Manage Graph RAG (Retrieval Augmented Generation) capabilities.

    Includes native Code Flow mapping, AST extraction for Python, Go, TypeScript, and Vue,
    and direct injection into local Elasticsearch for Agentic Codebase Memory.
    """
    pass


@rag_group.command("ingest")
@click.argument(
    "repo_path", type=click.Path(exists=True, file_okay=False, dir_okay=True)
)
@click.option(
    "--index",
    "-i",
    type=str,
    default="fremen_codebase_rag",
    help="Target Elasticsearch index name (default: fremen_codebase_rag)",
)
@click.pass_obj
@coro
async def ingest_repo(client: ElasticsearchClient, repo_path: str, index: str)-> None:
    """
    Ingest a repository with AST Code Flow Mapping.

    This command scans your codebase, utilizes Tree-sitter polyglot AST parsers
    to extract 'functions_defined' and 'functions_called', and uses the
    Elasticsearch Bulk API to stripe the Graph RAG data perfectly into an index.

    Example:
    ```bash
    elastro rag ingest /path/to/my/go-repo
    ```
    """
    repo_name = os.path.basename(os.path.abspath(repo_path))
    console.print(
        f"[bold cyan]🔍 Initializing Graph RAG AST Parsing for '{repo_name}'[/bold cyan]"
    )

    manager = GraphRAGManager(client, index)

    try:
        # We handle index scaffolding internally in GraphRAGManager
        success_count = manager.ingest_repository(repo_path)

        console.print(
            f"[bold green]✅ Success![/bold green] Ingested and mapped Code Flows for [bold]{success_count}[/bold] files."
        )
        console.print(
            f"[dim]The AST Graph RAG context is now active in index '{index}'.[/dim]"
        )

    except Exception as e:
        console.print(f"[bold red]❌ RAG Ingestion Failed:[/bold red] {str(e)}")
        exit(1)


@rag_group.command("update")
@click.argument(
    "file_path", type=click.Path(exists=True, file_okay=True, dir_okay=False)
)
@click.option(
    "--index",
    "-i",
    type=str,
    default="fremen_codebase_rag",
    help="Target Elasticsearch index name (default: fremen_codebase_rag)",
)
@click.pass_obj
@coro
async def update_file(client: ElasticsearchClient, file_path: str, index: str)-> None:
    """
    Surgically perfectly sync the AST of a single modified file.

    Ideal for Agentic usage where building the entire directory tree takes
    unnecessary toll compared to syncing only the latest refactored Python file.

    Example:
    ```bash
    elastro rag update elastro/core/rag/ingestor.py
    ```
    """
    file_name = os.path.basename(file_path)
    console.print(
        f"[bold cyan]🔍 Surgically syncing AST Graph RAG for '{file_name}'[/bold cyan]"
    )

    manager = GraphRAGManager(client, index)

    try:
        success_count = manager.update_file(file_path)

        console.print(
            f"[bold green]✅ Success![/bold green] Refreshed [bold]{success_count}[/bold] AST chunks for the file."
        )

    except Exception as e:
        console.print(f"[bold red]❌ RAG File Update Failed:[/bold red] {str(e)}")
        exit(1)
