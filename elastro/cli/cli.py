"""
Command-line interface main module.

This module defines the main CLI structure using Click.
"""

import sys

# --- FAST PATH INTERCEPTOR ---
# Must run before any other heavy imports to avoid the ~214ms startup penalty
if len(sys.argv) >= 3 and sys.argv[1] == "doc" and sys.argv[2] == "search":
    # Only use the fast path if '--help' is not requested
    if "--help" not in sys.argv and "-h" not in sys.argv:
        try:
            import os
            import socket
            import xmlrpc.client

            # Set a very short timeout so we fallback to heavy CLI if daemon is offline
            socket.setdefaulttimeout(0.05)
            token = os.environ.get("ELASTRO_DAEMON_TOKEN")
            if not token:
                token_path = os.path.expanduser("~/.elastic/daemon.token")
                try:
                    with open(token_path, encoding="utf-8") as token_file:
                        token = token_file.read().strip()
                except OSError:
                    token = None
            if not token:
                raise RuntimeError("daemon token missing")
            proxy = xmlrpc.client.ServerProxy("http://127.0.0.1:9201")

            result = proxy.fast_path_search(token, sys.argv[3:])
            if result:
                print(result, end="")
                sys.exit(0)
        except Exception as e:
            # If the daemon is offline or crashes, silently fall through
            # to the normal heavy Click execution.
            import logging

            logging.getLogger("elastro.cli").debug(f"Fast-path daemon bypass: {e}")
# --- END FAST PATH INTERCEPTOR ---

import os
from typing import Optional

import rich_click as click

from elastro.cli.art import ELASTRO_ART

# Configure rich-click
click.rich_click.USE_RICH_MARKUP = True
click.rich_click.USE_MARKDOWN = True  # Enable Markdown in docstrings
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
click.rich_click.STYLE_ERRORS_SUGGESTION = "magenta italic"
click.rich_click.ERRORS_SUGGESTION = (
    "Missing arguments? Run with --help to see examples and usage."
)
click.rich_click.ERRORS_EPILOGUE = "To find out more, visit [link=https://github.com/Fremen-Labs/elastro]https://github.com/Fremen-Labs/elastro[/link]"
if os.environ.get("ELASTRO_GUI_MODE") == "1":
    click.rich_click.HEADER_TEXT = None
else:
    click.rich_click.HEADER_TEXT = ELASTRO_ART

from elastro import __version__
from elastro.cli.commands.cluster import cluster_group
from elastro.cli.commands.config import (
    get_config_value,
    init_config,
    list_config,
    set_config_value,
)
from elastro.cli.commands.datastream import (
    create_datastream,
    delete_datastream,
    get_datastream,
    list_datastreams,
    rollover_datastream,
)
from elastro.cli.commands.document import (
    bulk_delete,
    bulk_index,
    delete_document,
    get_document,
    index_document,
    search_documents,
    update_document,
)
from elastro.cli.commands.esql import esql_group
from elastro.cli.commands.health import health_group
from elastro.cli.commands.ilm import ilm_group

# Import command groups
from elastro.cli.commands.index import (
    close_index,
    create_index,
    delete_index,
    find_indices,
    fix_indices,
    get_index,
    index_exists,
    index_wizard,
    list_indices,
    open_index,
    update_index,
)
from elastro.cli.commands.ingest import ingest_group
from elastro.cli.commands.memory import memory_group
from elastro.cli.commands.ml import ml_group
from elastro.cli.commands.painless_commands import painless_group
from elastro.cli.commands.script import script_group
from elastro.cli.commands.security import security_group
from elastro.cli.commands.snapshot import snapshot_group
from elastro.cli.commands.tasks import tasks_group
from elastro.cli.commands.telemetry import telemetry_group
from elastro.cli.commands.template import template_group
from elastro.cli.commands.tools import tools_group
from elastro.cli.commands.utils import aliases, health
from elastro.cli.commands.utils import templates as utils_templates
from elastro.config import load_config
from elastro.core.client import ElasticsearchClient

# Register Top-Level Groups


@click.group()
@click.option(
    "--config",
    "-c",
    help="Path to configuration file",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True),
)
@click.option("--profile", "-p", help="Configuration profile to use", default="default")
@click.option("--host", "-h", help="Elasticsearch host(s)", multiple=True)
@click.option(
    "--output",
    "-o",
    help="Output format (json, yaml, table)",
    type=click.Choice(["json", "yaml", "table"]),
    default="json",
)
@click.option(
    "--verbose", "-v", help="Enable verbose output", is_flag=True, default=False
)
@click.version_option(version=__version__)
@click.pass_context
def cli(
    ctx: click.Context,
    config: Optional[str],
    profile: str,
    host: tuple,
    output: str,
    verbose: bool,
) -> None:
    """
    Elasticsearch management CLI.

    This CLI provides commands for managing Elasticsearch indices, documents, and
    datastreams.
    """
    # Load configuration
    cfg = load_config(config, profile)

    # Override with command-line options
    if host:
        cfg["elasticsearch"]["hosts"] = list(host)

    if output:
        cfg["cli"]["output_format"] = output

    if verbose:
        cfg["cli"]["verbose"] = verbose

    # Initialize client
    client = ElasticsearchClient(
        hosts=cfg["elasticsearch"]["hosts"],
        auth=cfg["elasticsearch"]["auth"],
        timeout=cfg["elasticsearch"]["timeout"],
        retry_on_timeout=cfg["elasticsearch"]["retry_on_timeout"],
        max_retries=cfg["elasticsearch"]["max_retries"],
    )

    # Establish connection
    try:
        client.connect()
    except Exception as e:
        if verbose:
            click.echo(f"Failed to connect to Elasticsearch: {e}", err=True)
        # We don't exit here because some commands might not need connection (e.g. config),
        # but most do. For now, let's let individual commands fail if they need connection,
        # or better, just Log it. client.connect() raises ConnectionError.
        # Actually, if we fail to connect, most commands will fail.
        # Let's print a warning but continue, as 'config' commands shouldn't fail.
        pass

    # Store in context
    ctx.obj = client


@cli.group()
def index() -> None:
    """
    Manage Elasticsearch indices.
    """
    pass


# Register index commands
index.add_command(create_index)
index.add_command(get_index)
index.add_command(index_exists)
index.add_command(update_index)
index.add_command(delete_index)
index.add_command(open_index)
index.add_command(close_index)
index.add_command(list_indices)
index.add_command(find_indices)
index.add_command(index_wizard)
index.add_command(fix_indices)


@cli.group()
def doc() -> None:
    """
    Manage Elasticsearch documents.
    """
    pass


# Register document commands
doc.add_command(index_document)
doc.add_command(bulk_index)
doc.add_command(get_document)
doc.add_command(search_documents)
doc.add_command(update_document)
doc.add_command(delete_document)
doc.add_command(bulk_delete)


@cli.group()
def datastream() -> None:
    """
    Manage Elasticsearch datastreams.
    """
    pass


# Register datastream commands
datastream.add_command(create_datastream)
datastream.add_command(list_datastreams)
datastream.add_command(get_datastream)
datastream.add_command(delete_datastream)
datastream.add_command(rollover_datastream)


@cli.group()
def config() -> None:
    """
    Manage configuration.
    """
    pass


# Register config commands
config.add_command(get_config_value)
config.add_command(set_config_value)
config.add_command(list_config)
config.add_command(init_config)


@cli.group()
def utils() -> None:
    """
    Utility commands.
    """
    pass


# Register utility commands
utils.add_command(health)
utils.add_command(utils_templates)
utils.add_command(aliases)

from elastro.cli.commands.daemon import daemon_group
from elastro.cli.commands.gui import gui
from elastro.cli.commands.rag import rag_group

# Register Top-Level Groups
cli.add_command(template_group)
cli.add_command(ilm_group)
cli.add_command(snapshot_group)
cli.add_command(cluster_group)
cli.add_command(security_group)
cli.add_command(tasks_group)
cli.add_command(ingest_group)
cli.add_command(ml_group)
cli.add_command(script_group)
cli.add_command(painless_group)
cli.add_command(telemetry_group)
cli.add_command(memory_group)
cli.add_command(tools_group)
cli.add_command(gui)
cli.add_command(rag_group)
cli.add_command(daemon_group)
cli.add_command(esql_group)
cli.add_command(health_group)


def main() -> None:
    from elastro.core.logger import configure_logging

    configure_logging()
    """Entry point for CLI."""
    cli()


if __name__ == "__main__":
    main()
