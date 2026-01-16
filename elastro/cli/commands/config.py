"""
Configuration management commands for the CLI.
"""

import click
import json
import os
import yaml
from typing import Dict, Any
from elastro.config import get_config, save_config, default_config

CONFIG_PATH = os.path.expanduser("~/.elastic/config.yaml")

@click.command("get")
@click.argument("key", type=str)
@click.option("--profile", "-p", default="default", help="Configuration profile")
def get_config_value(key, profile):
    """Get a configuration value."""
    config = get_config(profile=profile)

    # Handle nested keys (e.g., "elasticsearch.hosts")
    parts = key.split(".")
    value = config
    try:
        for part in parts:
            value = value[part]

        if isinstance(value, (dict, list)):
            click.echo(json.dumps(value, indent=2))
        else:
            click.echo(value)
    except (KeyError, TypeError):
        click.echo(f"Configuration key '{key}' not found.", err=True)
        exit(1)

@click.command("set")
@click.argument("key", type=str)
@click.argument("value", type=str)
@click.option("--profile", "-p", default="default", help="Configuration profile")
def set_config_value(key, value, profile):
    """Set a configuration value."""
    config = get_config(profile=profile)

    # Parse the value if it looks like JSON
    if value.startswith("{") or value.startswith("["):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            pass

    # Handle nested keys
    parts = key.split(".")
    target = config
    for part in parts[:-1]:
        if part not in target:
            target[part] = {}
        target = target[part]

    target[parts[-1]] = value

    # Save the updated config
    save_config(config, profile=profile)
    click.echo(f"Configuration key '{key}' set successfully.")

@click.command("list")
@click.option("--profile", "-p", default="default", help="Configuration profile")
def list_config(profile):
    """List all configuration values."""
    config = get_config(profile=profile)
    click.echo(yaml.dump(config, default_flow_style=False))

@click.command("init")
@click.option("--force", is_flag=True, help="Force initialization (overwrite existing)")
@click.option("--profile", "-p", default="default", help="Configuration profile")
def init_config(force, profile):
    """
    Initialize the configuration file.
    
    Launches an interactive wizard to help you configure Elastro.
    """
    config_dir = os.path.dirname(CONFIG_PATH)

    # Create config directory if it does not exist
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)

    # Check if config file exists
    config_exists = os.path.exists(CONFIG_PATH)

    if config_exists and not force:
        click.echo("Configuration file already exists. Use --force to overwrite or launch the wizard.")
        if not click.confirm("Do you want to overwrite it and run the wizard?"):
            return

    # Run the interactive wizard
    config = run_config_wizard()

    if not config:
        click.echo("Configuration cancelled.")
        return

    # Add profile if specified
    if profile != "default":
        # Check if we are merging into existing config
        if config_exists:
             existing = get_config(profile=profile) # Takes care of loading base config
             # Load raw current config to be safe
             if os.path.exists(CONFIG_PATH):
                 with open(CONFIG_PATH, 'r') as f:
                     full_config = yaml.safe_load(f) or {}
             else:
                 full_config = {}
                 
             if "profiles" not in full_config:
                 full_config["profiles"] = {}
             full_config["profiles"][profile] = config
             config = full_config
        else:
            config = {"profiles": {profile: config}}

    # Save config
    # Use direct yaml dump for full structure control during init
    with open(CONFIG_PATH, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)

    from rich.console import Console
    console = Console()
    console.print(f"[green]Configuration initialized at {CONFIG_PATH}[/]")

def run_config_wizard() -> Dict[str, Any]:
    """Run interactive wizard to build configuration."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from elastro.core.client import ElasticsearchClient
    from elastro.core.errors import ConnectionError, AuthenticationError

    console = Console()
    console.print(Panel("🧙 [bold blue]Elastro Configuration Wizard[/]\nLet's get you connected to Elasticsearch.", border_style="blue"))
    
    # 1. Hosts
    default_host = "http://localhost:9200"
    hosts_input = Prompt.ask("🔌 [bold]Elasticsearch Host[/]", default=default_host)
    hosts = [h.strip() for h in hosts_input.split(",")]

    # 2. Authentication
    console.print("\n🔑 [bold]Authentication[/]")
    auth_type = Prompt.ask("   Method", choices=["basic", "api_key", "none"], default="none")
    
    auth = {}
    if auth_type == "basic":
        username = Prompt.ask("   Username", default="elastic")
        password = Prompt.ask("   Password", password=True)
        auth = {"type": "basic", "username": username, "password": password}
    elif auth_type == "api_key":
        api_key = Prompt.ask("   API Key", password=True)
        auth = {"type": "api_key", "api_key": api_key}
    
    # 3. Connection Test
    console.print("\n📡 [bold]Testing Connection...[/]")
    try:
        # Create a temporary client to test connection
        client = ElasticsearchClient(
            hosts=hosts,
            auth=auth,
            verify_certs=False,
            use_config=False
        )
        client.connect()
        info = client.get_client().info()
        version = info.get("version", {}).get("number", "Unknown")
        cluster_name = info.get("cluster_name", "Unknown")
        
        console.print(f"[bold green]✅ Success! Connected to '{cluster_name}' (v{version})[/]")
        client.disconnect()
        
    except (ConnectionError, AuthenticationError) as e:
        console.print(f"[bold red]❌ Connection Failed:[/]\n   {str(e)}")
        if not Confirm.ask("   Save configuration anyway?", default=False):
            return {}

    # 4. Build Config Object
    config = default_config()
    config["elasticsearch"]["hosts"] = hosts
    config["elasticsearch"]["auth"] = auth
    
    return config
