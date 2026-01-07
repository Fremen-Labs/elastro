"""
Index management commands for the CLI.
"""

import click
import json
from elastro.core.client import ElasticsearchClient
from elastro.core.index import IndexManager
from elastro.core.errors import OperationError
from elastro.cli.completion import complete_indices

@click.command("create")
@click.argument("name", type=str)
@click.option("--shards", type=int, default=1, help="Number of shards")
@click.option("--replicas", type=int, default=1, help="Number of replicas")
@click.option("--mapping", type=click.Path(exists=True, readable=True), help="Path to mapping file")
@click.option("--settings", type=click.Path(exists=True, readable=True), help="Path to settings file")
@click.pass_obj
def create_index(client, name, shards, replicas, mapping, settings):
    """Create an index with the specified configuration."""
    index_manager = IndexManager(client)

    # Prepare settings dictionary
    index_settings = {
        "settings": {
            "number_of_shards": shards,
            "number_of_replicas": replicas
        },
        "mappings": {}
    }

    # Load mappings from file if provided
    if mapping:
        with open(mapping, 'r') as f:
            mapping_data = json.load(f)
            index_settings["mappings"] = mapping_data

    # Load settings from file if provided (overriding defaults)
    if settings:
        with open(settings, 'r') as f:
            settings_data = json.load(f)
            index_settings["settings"].update(settings_data)

    try:
        result = index_manager.create(name, index_settings)
        click.echo(json.dumps(result, indent=2))
        click.echo(f"Index '{name}' created successfully.")
    except OperationError as e:
        click.echo(f"Error creating index: {str(e)}", err=True)
        exit(1)

@click.command("get")
@click.argument("name", type=str, shell_complete=complete_indices)
@click.pass_obj
def get_index(client, name):
    """Get information about an index."""
    index_manager = IndexManager(client)

    try:
        result = index_manager.get(name)
        click.echo(json.dumps(result, indent=2))
    except OperationError as e:
        click.echo(f"Error retrieving index: {str(e)}", err=True)
        exit(1)

@click.command("exists")
@click.argument("name", type=str, shell_complete=complete_indices)
@click.pass_obj
def index_exists(client, name):
    """Check if an index exists."""
    index_manager = IndexManager(client)

    try:
        exists = index_manager.exists(name)
        click.echo(json.dumps({"exists": exists}, indent=2))
    except OperationError as e:
        click.echo(f"Error checking index: {str(e)}", err=True)
        exit(1)

@click.command("update")
@click.argument("name", type=str, shell_complete=complete_indices)
@click.option("--settings", type=click.Path(exists=True, readable=True), required=True, help="Path to settings file")
@click.pass_obj
def update_index(client, name, settings):
    """Update index settings."""
    index_manager = IndexManager(client)

    # Load settings from file
    with open(settings, 'r') as f:
        settings_data = json.load(f)

    try:
        result = index_manager.update(name, settings_data)
        click.echo(json.dumps(result, indent=2))
        click.echo(f"Index '{name}' updated successfully.")
    except OperationError as e:
        click.echo(f"Error updating index: {str(e)}", err=True)
        exit(1)

@click.command("delete")
@click.argument("name", type=str, shell_complete=complete_indices)
@click.option("--force", is_flag=True, help="Force deletion without confirmation")
@click.pass_obj
def delete_index(client, name, force):
    """Delete an index."""
    index_manager = IndexManager(client)

    # Confirm deletion unless --force is provided
    if not force:
        confirm = click.confirm(f"Are you sure you want to delete index '{name}'?")
        if not confirm:
            click.echo("Operation cancelled.")
            return

    try:
        result = index_manager.delete(name)
        click.echo(json.dumps(result, indent=2))
        click.echo(f"Index '{name}' deleted successfully.")
    except OperationError as e:
        click.echo(f"Error deleting index: {str(e)}", err=True)
        exit(1)

@click.command("open")
@click.argument("name", type=str, shell_complete=complete_indices)
@click.pass_obj
def open_index(client, name):
    """Open an index."""
    index_manager = IndexManager(client)

    try:
        result = index_manager.open(name)
        click.echo(json.dumps(result, indent=2))
        click.echo(f"Index '{name}' opened successfully.")
    except OperationError as e:
        click.echo(f"Error opening index: {str(e)}", err=True)
        exit(1)

@click.command("close")
@click.argument("name", type=str, shell_complete=complete_indices)
@click.pass_obj
def close_index(client, name):
    """Close an index."""
    index_manager = IndexManager(client)

    try:
        result = index_manager.close(name)
        click.echo(json.dumps(result, indent=2))
        click.echo(f"Index '{name}' closed successfully.")
    except OperationError as e:
        click.echo(f"Error closing index: {str(e)}", err=True)
        exit(1)
