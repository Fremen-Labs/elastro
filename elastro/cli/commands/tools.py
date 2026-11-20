"""
Tools registry command group for Elastro CLI.
"""

from __future__ import annotations

import hashlib
import os

import rich_click as click

from elastro.agent.models import (
    FLOW_TOOLS,
    ToolRecord,
    tools_search_body,
    utc_timestamp,
)
from elastro.agent.store import AgentStore
from elastro.cli.context import require_client
from elastro.cli.errors import exit_from_exception
from elastro.core.client import ElasticsearchClient
from elastro.core.logger import get_logger

logger = get_logger(__name__)


@click.group(name="tools")
def tools_group() -> None:
    """Manage the Custom Agentic Toolchain registry."""
    pass


@tools_group.command("register")
@click.argument("tool_name")
@click.argument("file_path")
@click.argument("purpose")
@click.option(
    "--parameters", default="", help="JSON string or comma-separated list of params"
)
@click.pass_obj
def register_tool(
    client: ElasticsearchClient,
    tool_name: str,
    file_path: str,
    purpose: str,
    parameters: str,
) -> None:
    """
    Register a custom pipeline script or CLI into the tools registry.
    """
    logger.info("tools.register tool_name=%s", tool_name)
    file_hash = "unknown"
    if os.path.isfile(file_path):
        with open(file_path, "rb") as handle:
            file_hash = hashlib.sha256(handle.read()).hexdigest()
    else:
        click.secho(
            f"Warning: File '{file_path}' not found at registration time.", fg="yellow"
        )

    payload = ToolRecord(
        timestamp=utc_timestamp(),
        tool_name=tool_name,
        file_path=file_path,
        purpose=purpose,
        parameters=parameters,
        file_hash=file_hash,
    )

    require_client()
    try:
        AgentStore(client).index(FLOW_TOOLS, payload, id=tool_name)
        click.secho(
            f">> Tool '{tool_name}' registered successfully.",
            fg="green",
        )
    except Exception as exc:
        exit_from_exception(exc, logger=logger, action="register tool")


@tools_group.command("search")
@click.argument("query")
@click.option("--size", default=10, help="Number of results to return")
@click.pass_obj
def search_tools(
    client: ElasticsearchClient,
    query: str,
    size: int,
) -> None:
    """
    Search the flow_tools custom tool registry.
    """
    logger.info("tools.search size=%s", size)
    require_client()
    try:
        response = AgentStore(client).search(
            FLOW_TOOLS, tools_search_body(query, size=size)
        )
        hits = response.get("hits", {}).get("hits", [])

        click.secho(f"Found {len(hits)} registered tools:", fg="blue")
        for hit in hits:
            if not isinstance(hit, dict):
                continue
            source = hit.get("_source", {})
            tool_name = source.get("tool_name", "Unknown")
            file_path = source.get("file_path", "unknown")
            indexed_hash = source.get("file_hash", "unknown")

            click.echo(f"\n[TOOL] {tool_name}")
            click.echo(f"  Path: {file_path}")
            click.echo(f"  Purpose: {source.get('purpose', '')}")
            click.echo(f"  Parameters: {source.get('parameters', '')}")

            if file_path != "unknown" and os.path.isfile(file_path):
                with open(file_path, "rb") as handle:
                    current_hash = hashlib.sha256(handle.read()).hexdigest()

                if indexed_hash == "unknown":
                    click.secho(
                        "  Hash Status: [UNTRACKED] No index hash recorded.",
                        fg="yellow",
                    )
                elif current_hash != indexed_hash:
                    click.secho(
                        "  Hash Status: [STALE] Local file modified"
                        " since registration!",
                        fg="red",
                        bold=True,
                    )
                else:
                    click.secho(
                        "  Hash Status: [VERIFIED] Local file matches index exact.",
                        fg="green",
                    )
            else:
                click.secho(
                    "  Hash Status: [MISSING] File not found on disk.", fg="red"
                )

    except Exception as exc:
        exit_from_exception(exc, logger=logger, action="search tools")
