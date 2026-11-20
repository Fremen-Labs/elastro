"""
Command-line interface main module.

This module defines the main CLI structure using Click.
"""

import sys


def _try_doc_search_fast_path(argv: list[str]) -> bool:
    """Attempt daemon XML-RPC search. True if a result was printed.

    Restores the previous socket default timeout before returning so a
    50 ms process-wide timeout cannot leak into the Click CLI.
    """
    if len(argv) < 3 or argv[1] != "doc" or argv[2] != "search":
        return False
    if "--help" in argv or "-h" in argv:
        return False

    import os
    import socket
    import xmlrpc.client

    token = os.environ.get("ELASTRO_DAEMON_TOKEN")
    token_path = os.path.expanduser("~/.elastic/daemon.token")
    if not token:
        try:
            with open(token_path, encoding="utf-8") as token_file:
                token = token_file.read().strip()
        except OSError:
            token = None
    if not token:
        from elastro.core.logger import get_logger

        get_logger("elastro.cli").debug("daemon token missing at %s", token_path)
        return False

    previous_timeout = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(0.05)
        proxy = xmlrpc.client.ServerProxy("http://127.0.0.1:9201")
        result = proxy.fast_path_search(token, argv[3:])
        if result:
            print(result, end="")
            return True
        return False
    except (OSError, TimeoutError, socket.timeout, xmlrpc.client.Error):
        return False
    finally:
        socket.setdefaulttimeout(previous_timeout)


# --- FAST PATH INTERCEPTOR ---
# Must run before any other heavy imports to avoid the ~214ms startup penalty
if len(sys.argv) >= 3 and sys.argv[1] == "doc" and sys.argv[2] == "search":
    if "--help" not in sys.argv and "-h" not in sys.argv:
        if _try_doc_search_fast_path(sys.argv):
            sys.exit(0)
# --- END FAST PATH INTERCEPTOR ---

from typing import Optional

import rich_click as click

from elastro.cli.art import ELASTRO_ART, banner_enabled

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


def _apply_header_text() -> None:
    if banner_enabled():
        click.rich_click.HEADER_TEXT = ELASTRO_ART
    else:
        click.rich_click.HEADER_TEXT = None


_apply_header_text()

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
from elastro.cli.commands.coverage import coverage_group
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
    _apply_header_text()
    # Load configuration
    cfg = load_config(config, profile)

    # Override with command-line options
    if host:
        cfg["elasticsearch"]["hosts"] = list(host)

    if output:
        cfg["cli"]["output_format"] = output

    if verbose:
        cfg["cli"]["verbose"] = verbose

    # Construct only. Client-using callbacks call require_client, which connects.
    ctx.obj = ElasticsearchClient(
        hosts=cfg["elasticsearch"]["hosts"],
        auth=cfg["elasticsearch"]["auth"],
        timeout=cfg["elasticsearch"]["timeout"],
        retry_on_timeout=cfg["elasticsearch"]["retry_on_timeout"],
        max_retries=cfg["elasticsearch"]["max_retries"],
    )


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
cli.add_command(coverage_group)


def main() -> None:
    from elastro.core.logger import configure_logging

    configure_logging()
    """Entry point for CLI."""
    cli()


if __name__ == "__main__":
    main()
