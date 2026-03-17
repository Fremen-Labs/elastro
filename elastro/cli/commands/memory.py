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
@click.option(
    "--half-life",
    default="",
    help="Time interval string for exp decay (e.g. '5m', '1d'). Mimics node stimulation decay.",
)
@click.pass_obj
def search_memory(
    client: ElasticsearchClient,
    query: str,
    note_type: str,
    size: int,
    half_life: str,
) -> None:
    """
    Search semantic memory notes via vector/BM25 retrieval.
    Optionally applies Primed Activation decay via --half-life.
    """
    index_name = "agent_semantic_memory"

    from typing import Dict, Any, List
    import time

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

    base_query: Dict[str, Any] = {"bool": bool_clause}

    # Bioelectric Node Priming: Apply exponential decay based on TTL
    if half_life:
        base_query = {
            "function_score": {
                "query": base_query,
                "functions": [
                    {
                        "exp": {
                            "timestamp": {
                                "origin": "now",
                                "scale": half_life,
                                "decay": 0.5,
                            }
                        }
                    }
                ],
                "score_mode": "multiply",
                "boost_mode": "multiply",
            }
        }

    search_body: Dict[str, Any] = {
        "size": size,
        "query": base_query,
    }

    t0 = time.perf_counter()
    try:
        response = client.client.search(index=index_name, body=search_body)
        duration_ms = (time.perf_counter() - t0) * 1000
        hits = response.get("hits", {}).get("hits", [])

        click.secho(
            f"Found {len(hits)} memory nodes connected in {duration_ms:.2f}ms:",
            fg="blue",
            bold=True,
        )

        total_injected_tokens = 0

        for hit in hits:
            if not isinstance(hit, dict):
                continue
            source = hit.get("_source", {})
            score = hit.get("_score", 0.0)

            # Approximate token extraction proxy based on text chunks length
            raw_text = f"{source.get('subject', '')} {source.get('content', '')}"
            token_proxy_count = len(raw_text.split())
            total_injected_tokens += token_proxy_count

            click.echo(
                f"\n[{source.get('note_type', 'unknown').upper()}] {source.get('subject', 'Untitled')} "
                f"(ID: {hit.get('_id', '')} | Similarity Score: {score:.4f} | Tokens: ~{token_proxy_count})"
            )
            click.echo(f"  {source.get('content', '')}")
            if source.get("tags"):
                click.echo(f"  Tags: {', '.join(source['tags'])}")

        if half_life:
            click.secho(
                f"\n[METRICS] Wake Priming Completed - Injected Tokens: {total_injected_tokens} | Effective Latency: {duration_ms:.2f}ms | Decay Profile: Exp(50%/{half_life})",
                fg="cyan",
            )


    except Exception as e:
        click.secho(f"Search failed: {e}", fg="red", err=True)
        import sys

        sys.exit(1)


@memory_group.command("prune")
@click.option("--days", default=7, help="Number of days to retain tactical notes")
@click.pass_obj
def prune_memory(
    client: ElasticsearchClient,
    days: int,
) -> None:
    """
    Prune 'tactical' memory notes older than the specified threshold.
    """
    index_name = "agent_semantic_memory"

    from datetime import datetime, timezone, timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

    delete_query = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"note_type": "tactical"}},
                    {"range": {"timestamp": {"lt": cutoff_str}}},
                ]
            }
        }
    }

    try:
        response = client.client.delete_by_query(index=index_name, body=delete_query)
        deleted = response.get("deleted", 0)
        click.secho(
            f">> Pruned {deleted} tactical memory notes older than {days} days.",
            fg="green",
        )
    except Exception as e:
        click.secho(f"Failed to prune memory notes: {e}", fg="red", err=True)
        import sys

        sys.exit(1)
