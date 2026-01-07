"""
Command-line interface main module.

This module defines the main CLI structure using Click.
"""

import rich_click as click
import json
import yaml
from typing import Dict, Any, Optional, List, Union
from rich.console import Console
from rich.table import Table
from rich import box

from elastro.cli.art import ELASTRO_ART

# Configure rich-click
click.rich_click.USE_RICH_MARKUP = True
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
click.rich_click.STYLE_ERRORS_SUGGESTION = "magenta italic"
click.rich_click.ERRORS_SUGGESTION = "Try running the command again with --help for more information."
click.rich_click.ERRORS_EPILOGUE = "To find out more, visit [link=https://github.com/Fremen-Labs/elastro]https://github.com/Fremen-Labs/elastro[/link]"
click.rich_click.HEADER_TEXT = ELASTRO_ART

from elastro import __version__
from elastro.config import load_config, get_config
from elastro.core.client import ElasticsearchClient

# Import command groups
from elastro.cli.commands.index import (
    create_index, get_index, index_exists, update_index,
    delete_index, open_index, close_index
)
from elastro.cli.commands.document import (
    index_document, bulk_index, get_document, search_documents,
    update_document, delete_document, bulk_delete
)
from elastro.cli.commands.datastream import (
    create_datastream, list_datastreams, get_datastream,
    delete_datastream, rollover_datastream
)
from elastro.cli.commands.config import (
    get_config_value, set_config_value, list_config, init_config
)
from elastro.cli.commands.utils import (
    health, templates as utils_templates, aliases
)
from elastro.cli.commands.template import template_group
from elastro.cli.commands.ilm import ilm_group
from elastro.cli.commands.snapshot import snapshot_group

# ... (omitted) ...

# Register Top-Level Groups

@click.group()
@click.option(
    "--config", "-c",
    help="Path to configuration file",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True)
)
@click.option(
    "--profile", "-p",
    help="Configuration profile to use",
    default="default"
)
@click.option(
    "--host", "-h",
    help="Elasticsearch host(s)",
    multiple=True
)
@click.option(
    "--output", "-o",
    help="Output format (json, yaml, table)",
    type=click.Choice(["json", "yaml", "table"]),
    default="json"
)
@click.option(
    "--verbose", "-v",
    help="Enable verbose output",
    is_flag=True,
    default=False
)
@click.version_option(version=__version__)
@click.pass_context
def cli(
    ctx: click.Context,
    config: Optional[str],
    profile: str,
    host: tuple,
    output: str,
    verbose: bool
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
        max_retries=cfg["elasticsearch"]["max_retries"]
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

# Register Top-Level Groups
cli.add_command(template_group)
cli.add_command(ilm_group)
cli.add_command(snapshot_group)

def main():
    """Entry point for CLI."""
    cli()


if __name__ == "__main__":
    main()
