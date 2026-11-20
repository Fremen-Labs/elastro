"""
Memory command group for Elastro CLI.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Literal, cast

import rich_click as click

from elastro.agent.models import (
    AGENT_SEMANTIC_MEMORY,
    AGENT_TELEMETRY_DEEP,
    FREMEN_CODEBASE_RAG,
    MemoryNote,
    TokenCountQuery,
    WakeTelemetryDocument,
    memory_search_body,
    tactical_prune_query,
    utc_timestamp,
    wake_search_body,
)
from elastro.agent.store import AgentStore
from elastro.cli.context import require_client
from elastro.cli.errors import confirm_or_exit, exit_from_exception
from elastro.core.client import ElasticsearchClient
from elastro.core.logger import get_logger

logger = get_logger(__name__)


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
    logger.info("memory.ingest note_type=%s subject=%s", note_type, subject)
    require_client()
    note = MemoryNote(
        timestamp=utc_timestamp(),
        note_type=cast(Literal["strategic", "tactical"], note_type),
        subject=subject,
        content=content,
        tags=[t.strip() for t in tags.split(",")] if tags else [],
    )
    try:
        response = AgentStore(client).index(AGENT_SEMANTIC_MEMORY, note)
        click.secho(
            f">> Memory ingested successfully. ID: {response.get('_id', 'unknown')}",
            fg="green",
        )
    except Exception as exc:
        exit_from_exception(exc, logger=logger, action="ingest memory")


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
    logger.info("memory.search note_type=%s size=%s", note_type or "*", size)
    require_client()
    try:
        response = AgentStore(client).search(
            AGENT_SEMANTIC_MEMORY,
            memory_search_body(query, note_type=note_type, size=size),
        )
        hits = response.get("hits", {}).get("hits", [])

        click.secho(f"Found {len(hits)} memory notes:", fg="blue")
        for hit in hits:
            if not isinstance(hit, dict):
                continue
            source = hit.get("_source", {})
            note_kind = source.get("note_type", "unknown").upper()
            subject = source.get("subject", "Untitled")
            click.echo(f"\n[{note_kind}] {subject} ({hit.get('_id', '')})")
            click.echo(f"  {source.get('content', '')}")
            if source.get("tags"):
                click.echo(f"  Tags: {', '.join(source['tags'])}")

    except Exception as exc:
        exit_from_exception(exc, logger=logger, action="search memory")


@memory_group.command("prune")
@click.option("--days", default=7, help="Number of days to retain tactical notes")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Print the delete_by_query body without executing",
)
@click.option(
    "--yes",
    is_flag=True,
    help="Confirm prune without prompting (required when stdin is not a TTY)",
)
@click.pass_obj
def prune_memory(
    client: ElasticsearchClient,
    days: int,
    dry_run: bool,
    yes: bool,
) -> None:
    """
    Prune 'tactical' memory notes older than the specified threshold.
    """
    query = tactical_prune_query(days=days)
    if dry_run:
        logger.info("memory.prune dry_run days=%s", days)
        click.echo(json.dumps(query, indent=2))
        return

    confirm_or_exit(
        f"Prune tactical memory notes older than {days} days?",
        yes=yes,
    )
    require_client()
    logger.info("memory.prune days=%s", days)
    try:
        response = AgentStore(client).delete_by_query(AGENT_SEMANTIC_MEMORY, query)
        deleted = response.get("deleted", 0)
        click.secho(
            f">> Pruned {deleted} tactical memory notes older than {days} days.",
            fg="green",
        )
    except Exception as exc:
        exit_from_exception(exc, logger=logger, action="prune memory")


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
    "--index",
    "-i",
    default=AGENT_SEMANTIC_MEMORY,
    help="Target Elasticsearch index",
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
    logger.info("memory.wake index=%s k=%s", index_name, k)
    require_client()
    store = AgentStore(client)
    search_body = wake_search_body(
        heuristic_query, index=index_name, anchor_hash=anchor_hash, k=k
    )

    try:
        t_start = datetime.now()
        response = store.search(index_name, search_body)
        t_end = datetime.now()

        latency_ms = int((t_end - t_start).total_seconds() * 1000)
        hits = response.get("hits", {}).get("hits", [])

        total_tokens = sum(
            len(str(h.get("_source", {}).get("content", "")).split()) for h in hits
        )
        scores = [h.get("_score", 0.0) for h in hits]
        avg_score = sum(scores) / len(scores) if scores else 0.0

        telemetry_doc = WakeTelemetryDocument(
            timestamp=datetime.now(timezone.utc).isoformat(),
            workload_reference=f"Primed Activation Wake: {heuristic_query}",
            t_elastro_query_ms=latency_ms,
            effective_latency_to_knowing_state_ms=latency_ms + 12,
            similarity_scores=scores,
            avg_similarity_score=avg_score,
            token_count_query=TokenCountQuery(
                input_tokens=total_tokens, bounded_layer=k
            ),
            ast_hit_ratio=1.0,
            trajectory_depth=len(hits),
            complexity_score=float(k),
        )

        try:
            store.index(AGENT_TELEMETRY_DEEP, telemetry_doc)
        except Exception as te:
            logger.warning("memory.wake telemetry index failed: %s", te)
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
            content = str(source.get("content", ""))
            displayed_content = (
                content[:200] + "..."
                if len(content) > 200 and index_name == FREMEN_CODEBASE_RAG
                else content
            )
            click.echo(f"  {displayed_content}")

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

    except Exception as exc:
        exit_from_exception(exc, logger=logger, action="memory wake")
