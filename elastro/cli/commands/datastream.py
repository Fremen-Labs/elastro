"""
Datastream management commands for the CLI.
"""

import click
import json
from elastro.core.client import ElasticsearchClient
from elastro.core.datastream import DatastreamManager
from elastro.core.errors import OperationError
from elastro.cli.completion import complete_datastreams

@click.command("create")
@click.argument("name", type=str)
@click.option("--settings", type=click.Path(exists=True, readable=True), help="Path to settings file")
@click.pass_obj
def create_datastream(client, name, settings):
    """Create a datastream."""
    datastream_manager = DatastreamManager(client)

    # Load settings if provided
    if settings:
        with open(settings, 'r') as f:
            settings_data = json.load(f)
    else:
        settings_data = {}

    try:
        result = datastream_manager.create(name, settings_data)
        click.echo(json.dumps(result, indent=2))
        click.echo(f"Datastream '{name}' created successfully.")
    except OperationError as e:
        click.echo(f"Error creating datastream: {str(e)}", err=True)
        exit(1)

@click.command("list")
@click.pass_obj
def list_datastreams(client):
    """List all datastreams."""
    datastream_manager = DatastreamManager(client)

    try:
        result = datastream_manager.list()
        click.echo(json.dumps(result, indent=2))
    except OperationError as e:
        click.echo(f"Error listing datastreams: {str(e)}", err=True)
        exit(1)

@click.command("get")
@click.argument("name", type=str, shell_complete=complete_datastreams)
@click.pass_obj
def get_datastream(client, name):
    """Get information about a datastream."""
    datastream_manager = DatastreamManager(client)

    try:
        result = datastream_manager.get(name)
        click.echo(json.dumps(result, indent=2))
    except OperationError as e:
        click.echo(f"Error retrieving datastream: {str(e)}", err=True)
        exit(1)

@click.command("delete")
@click.argument("name", type=str, shell_complete=complete_datastreams)
@click.option("--force", is_flag=True, help="Force deletion without confirmation")
@click.pass_obj
def delete_datastream(client, name, force):
    """Delete a datastream."""
    datastream_manager = DatastreamManager(client)

    # Confirm deletion unless --force is provided
    if not force:
        confirm = click.confirm(f"Are you sure you want to delete datastream '{name}'?")
        if not confirm:
            click.echo("Operation cancelled.")
            return

    try:
        result = datastream_manager.delete(name)
        click.echo(json.dumps(result, indent=2))
        click.echo(f"Datastream '{name}' deleted successfully.")
    except OperationError as e:
        click.echo(f"Error deleting datastream: {str(e)}", err=True)
        exit(1)

@click.command("rollover")
@click.argument("name", type=str, shell_complete=complete_datastreams)
@click.option("--max-age", type=str, help="Maximum age (e.g., '7d')")
@click.option("--max-docs", type=int, help="Maximum number of documents")
@click.option("--max-size", type=str, help="Maximum size (e.g., '5gb')")
@click.pass_obj
def rollover_datastream(client, name, max_age, max_docs, max_size):
    """Rollover a datastream."""
    datastream_manager = DatastreamManager(client)

    # Prepare conditions
    conditions = {}
    if max_age:
        conditions["max_age"] = max_age
    if max_docs:
        conditions["max_docs"] = max_docs
    if max_size:
        conditions["max_size"] = max_size

    try:
        result = datastream_manager.rollover(name, conditions)
        click.echo(json.dumps(result, indent=2))
        if result.get("rolled_over", False):
            click.echo(f"Datastream '{name}' rolled over successfully.")
        else:
            click.echo(f"Datastream '{name}' was not rolled over. Conditions not met.")
    except OperationError as e:
        click.echo(f"Error rolling over datastream: {str(e)}", err=True)
        exit(1)
