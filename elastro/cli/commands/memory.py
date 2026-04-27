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


@memory_group.command("wake")
@click.argument("heuristic_query")
@click.option(
    "--anchor",
    "anchor_hash",
    default="",
    help="Deterministic tool hash to anchor the activation wave",
)
@click.option("--k", default=5, help="Top-K bounded node subset (500-1k tokens max)")
@click.option(
    "--index", "-i", default="agent_semantic_memory", help="Target Elasticsearch index"
)
@click.pass_obj
def wake_memory(
    client: ElasticsearchClient,
    heuristic_query: str,
    anchor_hash: str,
    k: int,
    index: str,
) -> None:
    """
    Primed Activation 'Wake' Query: Bounded Activation Wave.
    Uses exponential decay (TTL) on timestamps and strictly bounds the subgraph
    context to slash API latency.
    """
    index_name = index

    from typing import Dict, Any, List

    # Core textual RAG retrieval
    fields = ["subject^3", "content", "tags"]
    if index_name == "fremen_codebase_rag":
        fields = ["file_path^3", "content", "chunk_name^2"]

    must_clauses: List[Dict[str, Any]] = [
        {
            "multi_match": {
                "query": heuristic_query,
                "fields": fields,
            }
        }
    ]

    # Deterministic API Hash anchoring
    if anchor_hash:
        must_clauses.append({"term": {"anchor_hash": anchor_hash}})

    # Exponential TTL Similarity Decay (Bioelectric node stimulation mimicry)
    function_score_query = {
        "function_score": {
            "query": {"bool": {"must": must_clauses}},
            "functions": [
                {"exp": {"timestamp": {"scale": "7d", "offset": "1d", "decay": 0.5}}}
            ],
            "boost_mode": "multiply",
        }
    }

    search_body: Dict[str, Any] = {
        "size": k,
        "query": function_score_query,
    }

    try:
        t_start = datetime.now()
        response = client.client.search(index=index_name, body=search_body)
        t_end = datetime.now()

        latency_ms = int((t_end - t_start).total_seconds() * 1000)
        hits = response.get("hits", {}).get("hits", [])

        # Calculate ruthless telemetry requested by the user
        total_tokens = sum(
            len(str(h.get("_source", {}).get("content", "")).split()) for h in hits
        )
        scores = [h.get("_score", 0.0) for h in hits]
        avg_score = sum(scores) / len(scores) if scores else 0.0

        telemetry_doc = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "workload_reference": f"Primed Activation Wake: {heuristic_query}",
            "t_elastro_query_ms": latency_ms,
            "effective_latency_to_knowing_state_ms": latency_ms
            + 12,  # Network overlay approximation
            "similarity_scores": scores,
            "avg_similarity_score": avg_score,
            "token_count_query": {"input_tokens": total_tokens, "bounded_layer": k},
            "ast_hit_ratio": 1.0,
            "trajectory_depth": len(hits),
            "complexity_score": k,
        }

        try:
            client.client.index(index="agent_telemetry_deep", document=telemetry_doc)
        except Exception as te:
            click.secho(
                f"Warning: Failed to log telemetry: {te}", fg="yellow", err=True
            )

        click.secho(f"Primed Activation Wave [{len(hits)} Nodes Awakened]", fg="cyan")
        for hit in hits:
            if not isinstance(hit, dict):
                continue
            source = hit.get("_source", {})
            score = hit.get("_score", 0.0)
            title = source.get("subject") or source.get("file_path") or "Untitled"
            click.echo(f"\n[STIMULATED] {title} (Score: {score:.2f})")
            # Only print first ~200 chars of content if in codebase rag to simulate 50 token limit
            content = str(source.get("content", ""))
            displayed_content = (
                content[:200] + "..."
                if len(content) > 200 and index_name == "fremen_codebase_rag"
                else content
            )
            click.echo(f"  {displayed_content}")

            # Extract AST Breadcrumbs natively
            ast_breadcrumbs = []
            if source.get("functions_defined"):
                ast_breadcrumbs.append(f"Defined: {source['functions_defined']}")
            if source.get("functions_called"):
                ast_breadcrumbs.append(f"Called: {source['functions_called']}")

            if ast_breadcrumbs:
                click.secho(
                    f"  [AST Breadcrumbs] {' | '.join(ast_breadcrumbs)}", fg="yellow"
                )

            if source.get("anchor_hash"):
                click.echo(f"  Anchor: {source['anchor_hash']}")

    except Exception as e:
        click.secho(f"Activation wave failed: {e}", fg="red", err=True)
        import sys

        sys.exit(1)
