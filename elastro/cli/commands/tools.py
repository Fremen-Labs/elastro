from elastro.utils.async_cli import coro
"""
Tools registry command group for Elastro CLI.
"""

import rich_click as click
from datetime import datetime, timezone

from elastro.core.client import ElasticsearchClient


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
@coro
async def register_tool(
    client: ElasticsearchClient,
    tool_name: str,
    file_path: str,
    purpose: str,
    parameters: str,
)-> None:
    """
    Register a custom pipeline script or CLI into the tools registry.
    """
    index_name = "flow_tools"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    import os
    import hashlib

    file_hash = "unknown"
    if os.path.isfile(file_path):
        with open(file_path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
    else:
        click.secho(
            f"Warning: File '{file_path}' not found at registration time.", fg="yellow"
        )

    payload = {
        "timestamp": timestamp,
        "tool_name": tool_name,
        "file_path": file_path,
        "purpose": purpose,
        "parameters": parameters,
        "file_hash": file_hash,
    }

    try:
        response = await client.client.index(index=index_name, id=tool_name, document=payload)
        click.secho(
            f">> Tool '{tool_name}' registered successfully.",
            fg="green",
        )
    except Exception as e:
        click.secho(f"Failed to register tool payload: {e}", fg="red", err=True)
        import sys

        sys.exit(1)


@tools_group.command("search")
@click.argument("query")
@click.option("--size", default=10, help="Number of results to return")
@click.pass_obj
@coro
async def search_tools(
    client: ElasticsearchClient,
    query: str,
    size: int,
)-> None:
    """
    Search the flow_tools custom tool registry.
    """
    index_name = "flow_tools"

    search_body = {
        "size": size,
        "query": {
            "multi_match": {
                "query": query,
                "fields": ["tool_name^3", "purpose^2", "parameters"],
            }
        },
    }

    try:
        response = await client.client.search(index=index_name, body=search_body)
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

            import os
            import hashlib

            if file_path != "unknown" and os.path.isfile(file_path):
                with open(file_path, "rb") as f:
                    current_hash = hashlib.sha256(f.read()).hexdigest()

                if indexed_hash == "unknown":
                    click.secho(
                        "  Hash Status: [UNTRACKED] No index hash recorded.",
                        fg="yellow",
                    )
                elif current_hash != indexed_hash:
                    click.secho(
                        "  Hash Status: [STALE] Local file modified since registration!",
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

    except Exception as e:
        click.secho(f"Search failed: {e}", fg="red", err=True)
        import sys

        sys.exit(1)
