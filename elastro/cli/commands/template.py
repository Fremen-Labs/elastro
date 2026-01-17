import click
import json
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.console import Console
from rich.panel import Panel
from elastro.core.client import ElasticsearchClient
from elastro.utils.templates import TemplateManager
from elastro.core.errors import OperationError
from elastro.cli.completion import complete_templates

console = Console()

@click.group("template")
def template_group():
    """Manage index and component templates."""
    pass

@template_group.command("list")
@click.option("--type", type=click.Choice(["index", "component"]), default="index", help="Template type")
@click.option("--name", type=str, help="Template name pattern")
@click.pass_obj
def list_templates(client, type, name):
    """
    List templates.

    Lists all index or component templates, optionally filtering by name.

    Examples:
        # List all index templates
        $ elastro template list

        # List component templates
        $ elastro template list --type component
    """
    manager = TemplateManager(client)
    try:
        result = manager.list(template_type=type, name=name)
        click.echo(json.dumps(result, indent=2))
    except OperationError as e:
        click.echo(f"Error listing templates: {str(e)}", err=True)
        exit(1)

@template_group.command("get", no_args_is_help=True)
@click.argument("name", type=str, shell_complete=complete_templates)
@click.option("--type", type=click.Choice(["index", "component"]), default="index", help="Template type")
@click.pass_obj
def get_template(client, name, type):
    """
    Get a template.

    Retrieves the definition of a specific template.

    Examples:
        $ elastro template get my-template
    """
    manager = TemplateManager(client)
    try:
        result = manager.get(name, template_type=type)
        click.echo(json.dumps(result, indent=2))
    except OperationError as e:
        click.echo(f"Error getting template: {str(e)}", err=True)
        exit(1)

@template_group.command("delete", no_args_is_help=True)
@click.argument("name", type=str, shell_complete=complete_templates)
@click.option("--type", type=click.Choice(["index", "component"]), default="index", help="Template type")
@click.option("--force", is_flag=True, help="Force deletion")
@click.pass_obj
def delete_template(client, name, type, force):
    """
    Delete a template.

    Permanently removes a template.

    Examples:
        $ elastro template delete my-template
    """
    manager = TemplateManager(client)
    if not force and not click.confirm(f"Delete {type} template '{name}'?"):
        return
        
    try:
        if manager.delete(name, template_type=type):
            click.echo(f"Template '{name}' deleted.")
        else:
            click.echo("Deletion not acknowledged.")
    except OperationError as e:
        click.echo(f"Error deleting template: {str(e)}", err=True)
        exit(1)

@template_group.command("create", no_args_is_help=True)
@click.argument("name", type=str)
@click.option("--file", type=click.Path(exists=True, readable=True), required=True, help="Template definition file")
@click.option("--type", type=click.Choice(["index", "component"]), default="index", help="Template type")
@click.pass_obj
def create_template(client, name, file, type):
    """
    Create a template from file.

    Creates or updates a template using a JSON definition file.

    Examples:
        $ elastro template create my-template --file ./template.json
    """
    manager = TemplateManager(client)
    
    with open(file, 'r') as f:
        body = json.load(f)
        
    try:
        if manager.create(name, body, template_type=type):
            click.echo(f"Template '{name}' created.")
        else:
            click.echo("Creation not acknowledged.")
    except OperationError as e:
        click.echo(f"Error creating template: {str(e)}", err=True)
        exit(1)

@template_group.command("wizard")
@click.pass_obj
def wizard(client):
    """
    Interactive template builder wizard.

    Guides you through creating a new component or index template.

    Examples:
        $ elastro template wizard
    """

    manager = TemplateManager(client)
    
    console.print(Panel.fit("🧙‍♂️ Index Architect Wizard", style="bold blue"))
    
    # 1. Choose Type
    template_type = Prompt.ask("What do you want to build?", choices=["component", "index"], default="component")
    
    name = Prompt.ask("Name of the template")
    
    settings = {}
    mappings = {"properties": {}}
    aliases = {}
    
    # 2. Settings Wizard
    if Confirm.ask("Configure Settings? (shards, replicas, codec)"):
        shards = IntPrompt.ask("Number of shards", default=1)
        replicas = IntPrompt.ask("Number of replicas", default=1)
        settings["number_of_shards"] = shards
        settings["number_of_replicas"] = replicas
        
        if Confirm.ask("Add Codec (compression)?"):
            codec = Prompt.ask("Codec", choices=["default", "best_compression"], default="best_compression")
            settings["codec"] = codec
            
    # 3. Mappings Wizard
    if Confirm.ask("Configure Mappings?"):
        while True:
            if not Confirm.ask("Add a field?"):
                break
            field_name = Prompt.ask("Field Name")
            field_type = Prompt.ask("Field Type", choices=["text", "keyword", "long", "integer", "date", "boolean", "ip"], default="keyword")
            mappings["properties"][field_name] = {"type": field_type}
            
    # 4. Final Assembly
    body = {}
    if template_type == "component":
        body["template"] = {}
        if settings:
            body["template"]["settings"] = settings
        if mappings["properties"]:
            body["template"]["mappings"] = mappings
    else:
        # Index Template
        patterns = Prompt.ask("Index Patterns (comma separated)").split(",")
        body["index_patterns"] = [p.strip() for p in patterns]
        body["template"] = {}
        if settings:
            body["template"]["settings"] = settings
        if mappings["properties"]:
            body["template"]["mappings"] = mappings
            
        # Composed Of
        if Confirm.ask("Compose of existing components?"):
            comps = Prompt.ask("Component names (comma separated)").split(",")
            body["composed_of"] = [c.strip() for c in comps]

    # Preview
    console.print(Panel(json.dumps(body, indent=2), title="Preview", border_style="green"))
    
    if Confirm.ask("Deploy to Cluster?"):
        try:
            if manager.create(name, body, template_type=template_type):
                console.print(f"[bold green]Success![/] {template_type} template '{name}' created.")
            else:
                console.print("[bold red]Failed.[/] Not acknowledged.")
        except Exception as e:
            console.print(f"[bold red]Error:[/]{str(e)}")
