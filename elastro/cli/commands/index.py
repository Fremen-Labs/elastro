"""
Index management commands for the CLI.
"""

import rich_click as click
import json
from elastro.core.client import ElasticsearchClient
from elastro.core.index import IndexManager
from elastro.core.errors import OperationError
from elastro.cli.completion import complete_indices

@click.command("create", no_args_is_help=True)
@click.argument("name", type=str)
@click.option("--shards", type=int, default=1, help="Number of shards", show_default=True)
@click.option("--replicas", type=int, default=1, help="Number of replicas", show_default=True)
@click.option("--mapping", type=click.Path(exists=True, readable=True), help="Path to mapping file")
@click.option("--settings", type=click.Path(exists=True, readable=True), help="Path to settings file")
@click.pass_obj
def create_index(client, name, shards, replicas, mapping, settings):
    """
    Create an index with the specified configuration.

    Create a new Elasticsearch index with explicit settings for shards and replicas.
    You can also provide a JSON file for mappings or full settings.

    Examples:
    
    Create a simple index with custom shards and replicas:
    ```bash
    elastro index create my-logs --shards 3 --replicas 2
    ```

    Create using a mapping file:
    ```bash
    elastro index create users --mapping ./user_mapping.json
    ```

    Create using full settings:
    ```bash
    elastro index create products --settings ./index_settings.json
    ```
    """
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
    """
    Get information about an index.

    Retrieves the full settings, mappings, and metadata for a specific index.

    Examples:
    
    Get details for a specific index:
    ```bash
    elastro index get my-logs
    ```
    """
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
    """
    Check if an index exists.

    Returns a simple JSON boolean indicating presence.

    Examples:
    
    Check if an index exists:
    ```bash
    elastro index exists my-logs
    ```
    """
    index_manager = IndexManager(client)

    try:
        exists = index_manager.exists(name)
        click.echo(json.dumps({"exists": exists}, indent=2))
    except OperationError as e:
        click.echo(f"Error checking index: {str(e)}", err=True)
        exit(1)

@click.command("update", no_args_is_help=True)
@click.argument("name", type=str, shell_complete=complete_indices)
@click.option("--settings", type=click.Path(exists=True, readable=True), required=True, help="Path to settings file")
@click.pass_obj
def update_index(client, name, settings):
    """
    Update index settings.

    Dynamically updates the settings of an existing index.
    Note: Some settings (like analysis) require closing the index first.

    Examples:
    
    Update index settings from a file:
    ```bash
    elastro index update my-logs --settings ./new_settings.json
    ```
    """
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

@click.command("delete", no_args_is_help=True)
@click.argument("name", type=str, shell_complete=complete_indices)
@click.option("--force", is_flag=True, help="Force deletion without confirmation")
@click.pass_obj
def delete_index(client, name, force):
    """
    Delete an index.

    Permanently removes an index and all its data.
    Requires confirmation unless --force is used.

    Examples:
    
    Delete an index (prompts for confirmation):
    ```bash
    elastro index delete my-logs
    ```

    Force delete without confirmation:
    ```bash
    elastro index delete my-logs --force
    ```
    """
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
    """
    Open an index.

    Opens a closed index, making it available for search and indexing again.

    Examples:
    
    Open a closed index:
    ```bash
    elastro index open my-logs
    ```
    """
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
    """
    Close an index.

    Closes an index to perform maintenance or save resources.
    Closed indices consume disk space but no memory.

    Examples:
    
    Close an index to save resources:
    ```bash
    elastro index close my-logs
    ```
    """
    index_manager = IndexManager(client)

    try:
        result = index_manager.close(name)
        click.echo(json.dumps(result, indent=2))
        click.echo(f"Index '{name}' closed successfully.")
    except OperationError as e:
        click.echo(f"Error closing index: {str(e)}", err=True)
        exit(1)

@click.command("list")
@click.argument("pattern", type=str, default="*", required=False)
@click.pass_obj
def list_indices(client, pattern):
    """
    List indices.
    
    Optionally provide a PATTERN to filter matching indices.
    Displays a formatted table of index statuses.

    Examples:
    
    List all indices:
    ```bash
    elastro index list
    ```

    List indices matching a pattern:
    ```bash
    elastro index list "logs-*"
    ```
    """
    from rich.console import Console
    from rich.table import Table
    from rich import box
    
    index_manager = IndexManager(client)
    console = Console()

    try:
        indices = index_manager.list(pattern=pattern)
        
        if not indices:
             console.print(f"[yellow]No indices found matching pattern '{pattern}'[/]")
             return

        table = Table(title=f"Indices ({len(indices)})", box=box.ROUNDED)
        table.add_column("Health", justify="center")
        table.add_column("Status", justify="center")
        table.add_column("Name", style="bold cyan")
        table.add_column("Docs", justify="right")
        table.add_column("Size", justify="right")
        table.add_column("Pri/Rep", justify="center")

        for idx in indices:
            health = idx.get("health", "unknown")
            color = "green" if health == "green" else "yellow" if health == "yellow" else "red"
            
            table.add_row(
                f"[{color}]{health}[/]",
                idx.get("status", ""),
                idx.get("index", ""),
                idx.get("docs.count", "0"),
                idx.get("store.size", "0b"),
                f"{idx.get('pri', '0')}/{idx.get('rep', '0')}"
            )
            
        console.print(table)
        
    except OperationError as e:
        click.echo(f"Error listing indices: {str(e)}", err=True)
        exit(1)

@click.command("find", no_args_is_help=True)
@click.argument("pattern", type=str)
@click.pass_obj
def find_indices(client, pattern):
    """
    Find indices matching a pattern.
    
    Wrapper for 'list' that requires a pattern argument.

    Examples:
    
    Find indices starting with 'users-':
    ```bash
    elastro index find "users-*"
    ```

    Find all Kibana system indices:
    ```bash
    elastro index find "*.kibana"
    ```
    """
    # Simply delegate to the list implementation
    # We invoke it manually passing the context object 'client' and the pattern
    # But since Click commands are wrapped, it's easier to just call the logic directly or duplicating minimal logic.
    # Duplicating minimal logic for clarity and specific 'Find' header if we wanted, 
    # but re-using the exact same function body is DRY. 
    # Let's just call the same logic.
    ctx = click.get_current_context()
    ctx.invoke(list_indices, pattern=pattern)

@click.command("wizard", no_args_is_help=False)
@click.pass_obj
def index_wizard(client):
    """
    Interactive index creation wizard.

    Guides you through creating an index using "Certified Engineer" best practices.
    Select from a list of optimized recipes for common use cases.

    Examples:
    
    Launch the wizard:
    ```bash
    elastro index wizard
    ```
    """
    from rich.prompt import Prompt, Confirm, IntPrompt
    from rich.console import Console
    from rich.panel import Panel
    from rich.syntax import Syntax
    from .index_recipes import RECIPES

    console = Console()
    index_manager = IndexManager(client)

    console.print(Panel.fit(
        "[bold cyan]Elastro Index Wizard[/]\n"
        "Select a recipe to generate an optimized index configuration.",
        border_style="cyan"
    ))

    # 1. Display Recipes
    for key, recipe in RECIPES.items():
        console.print(f"[bold green]{key}[/]. [bold white]{recipe.name}[/]")
        console.print(f"   [dim]{recipe.description}[/]\n")

    # 2. Select Recipe
    choice = Prompt.ask(
        "Select a recipe number", 
        choices=list(RECIPES.keys()), 
        default="1"
    )
    recipe = RECIPES[choice]

    console.print(f"\n[bold]Selected:[/]: [cyan]{recipe.name}[/]")
    console.print(f"[italic]{recipe.description}[/]\n")

    # 3. Prompt for Basic Info
    index_name = Prompt.ask("Enter index name", default="my-new-index")
    
    # 4. Prepare Configuration
    settings = recipe.get_settings()
    mappings = recipe.get_mappings()

    # Allow simple overrides for shards/replicas
    if Confirm.ask("Customize shards/replicas?", default=False):
        settings["number_of_shards"] = IntPrompt.ask("Primary Shards", default=settings.get("number_of_shards", 1))
        settings["number_of_replicas"] = IntPrompt.ask("Replica Copies", default=settings.get("number_of_replicas", 1))

    # --- Feature: Dynamic Field Customization ---
    
    # A. Rename Default Fields
    if recipe.customizable_fields:
        console.print("\n[bold]Customize Default Fields:[/]")
        for field in recipe.customizable_fields:
            if field in mappings["properties"]:
                new_name = Prompt.ask(f"Rename field '{field}'?", default=field)
                if new_name != field:
                    mappings["properties"][new_name] = mappings["properties"].pop(field)

    # B. Add New Fields
    console.print("\n[bold]Add Custom Fields:[/]")
    valid_types = [
        "text", "keyword", "date", "long", "integer", "boolean", 
        "ip", "geo_point", "nested", "object"
    ]
    
    while True:
        if not Confirm.ask("Add a new field?", default=False):
            break
            
        field_name = Prompt.ask("Field Name")
        field_type = Prompt.ask("Field Type", choices=valid_types, default="keyword")
        
        mappings["properties"][field_name] = {"type": field_type}
        console.print(f"[green]Added field '{field_name}' ({field_type})[/]")

    # Construct Final Config
    final_config = {
        "settings": settings,
        "mappings": mappings
    }

    # 5. Preview JSON
    json_str = json.dumps(final_config, indent=2)
    console.print("\n[bold]Configuration Preview:[/]")
    console.print(Syntax(json_str, "json", theme="monokai", line_numbers=False))

    # 6. Confirmation and Creation
    if Confirm.ask(f"\nCreate index [bold cyan]{index_name}[/]?", default=True):
        try:
            result = index_manager.create(index_name, final_config)
            console.print(Panel(
                f"[bold green]Success![/]\nIndex [cyan]{index_name}[/] created.\n"
                f"Response: {json.dumps(result)}",
                title="Operation Complete",
                border_style="green"
            ))
        except OperationError as e:
            console.print(f"[bold red]Error:[/] {str(e)}")
            exit(1)
    else:
        console.print("[yellow]Operation cancelled.[/]")
