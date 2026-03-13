"""
Memory command group for Elastro CLI.
"""

import rich_click as click
from datetime import datetime, timezone

from elastro.core.client import ElasticsearchClient


@click.group(name="memory")
def memory_group() -> None:
    """Manage semantic memory for agents."""
    pass


@memory_group.command("ingest")
@click.argument("note_type", type=click.Choice(["strategic", "tactical"]))
@click.argument("subject")
@click.argument("content")
@click.option("--tags", default="", help="Comma-separated tags")
@click.pass_obj
def ingest_memory(
    client: ElasticsearchClient,
    note_type: str,
    subject: str,
    content: str,
    tags: str,
) -> None:
    """
    Ingest a semantic memory note for agent knowledge sharing.

    NOTE_TYPE must be 'strategic' (telemetry/heuristics) or 'tactical' (handoffs).
    """
    index_name = "agent_semantic_memory"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    payload = {
        "timestamp": timestamp,
        "note_type": note_type,
        "subject": subject,
        "content": content,
        "tags": [t.strip() for t in tags.split(",")] if tags else [],
    }

    try:
        response = client.client.index(index=index_name, document=payload)
        click.secho(
            f">> Memory ingested successfully. ID: {response.get('_id', 'unknown')}",
            fg="green",
        )
    except Exception as e:
        click.secho(f"Failed to ingest memory payload: {e}", fg="red", err=True)
        import sys

        sys.exit(1)


@memory_group.command("search")
@click.argument("query")
@click.option(
    "--type",
    "note_type",
    type=click.Choice(["strategic", "tactical"]),
    help="Filter by note type",
)
@click.option("--size", default=10, help="Number of results to return")
@click.pass_obj
def search_memory(
    client: ElasticsearchClient,
    query: str,
    note_type: str,
    size: int,
) -> None:
    """
    Search semantic memory notes via vector/BM25 retrieval.
    """
    index_name = "agent_semantic_memory"

    from typing import Dict, Any, List

    bool_clause: Dict[str, List[Any]] = {
        "must": [
            {
                "multi_match": {
                    "query": query,
                    "fields": ["subject^2", "content", "tags"],
                }
            }
        ]
    }

    if note_type:
        bool_clause["filter"] = [{"term": {"note_type": note_type}}]

    search_body: Dict[str, Any] = {
        "size": size,
        "query": {"bool": bool_clause},
    }

    try:
        response = client.client.search(index=index_name, body=search_body)
        hits = response.get("hits", {}).get("hits", [])

        click.secho(f"Found {len(hits)} memory notes:", fg="blue")
        for hit in hits:
            if not isinstance(hit, dict):
                continue
            source = hit.get("_source", {})
            click.echo(
                f"\n[{source.get('note_type', 'unknown').upper()}] {source.get('subject', 'Untitled')} ({hit.get('_id', '')})"
            )
            click.echo(f"  {source.get('content', '')}")
            if source.get("tags"):
                click.echo(f"  Tags: {', '.join(source['tags'])}")

    except Exception as e:
        click.secho(f"Search failed: {e}", fg="red", err=True)
        import sys

        sys.exit(1)
