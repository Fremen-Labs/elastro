from elastro.utils.async_cli import coro
"""
Configuration management commands for the CLI.
"""

import rich_click as click
import json
import os
import yaml
import copy
from typing import Dict, Any, Union
from elastro.config import get_config, save_config, default_config

CONFIG_PATH = os.path.expanduser("~/.elastic/config.yaml")

SENSITIVE_KEYS = {"api_key", "password"}


def mask_credentials(data: Any) -> Any:
    """Recursively mask sensitive credentials in a configuration object."""
    if isinstance(data, dict):
        masked_data = copy.deepcopy(data)
        for key, value in masked_data.items():
            if key in SENSITIVE_KEYS and value is not None:
                masked_data[key] = "********"
            elif isinstance(value, (dict, list)):
                masked_data[key] = mask_credentials(value)
        return masked_data
    elif isinstance(data, list):
        return [mask_credentials(item) for item in data]
    return data


@click.command("get", no_args_is_help=True)
@click.argument("key", type=str)
@click.option("--profile", "-p", default="default", help="Configuration profile")
@coro
async def get_config_value(key: str, profile: str) -> None:
    """
    Get a configuration value.

    Retrieves a specific setting from the configuration file.

    Examples:

    Get a specific config value:
    ```bash
    elastro config get elasticsearch.hosts
    ```
    """
    config = get_config(profile=profile)

    # Handle nested keys (e.g., "elasticsearch.hosts")
    parts = key.split(".")
    value = config
    try:
        for part in parts:
            value = value[part]

        if isinstance(value, (dict, list)):
            masked_value = mask_credentials(value)
            click.echo(json.dumps(masked_value, indent=2))
        else:
            if parts[-1] in SENSITIVE_KEYS and value is not None:
                click.echo("********")
            else:
                click.echo(value)
    except (KeyError, TypeError):
        click.echo(f"Configuration key '{key}' not found.", err=True)
        exit(1)


@click.command("set", no_args_is_help=True)
@click.argument("key", type=str)
@click.argument("value", type=str)
@click.option("--profile", "-p", default="default", help="Configuration profile")
@coro
async def set_config_value(key: str, value: str, profile: str) -> None:
    """
    Set a configuration value.

    Updates a setting in the configuration file. Supports nested keys and JSON values.

    Examples:

    Set a simple value:
    ```bash
    elastro config set elasticsearch.timeout 60s
    ```

    Set a complex value (JSON array):
    ```bash
    elastro config set elasticsearch.hosts '["http://localhost:9200"]'
    ```
    """
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
@coro
async def list_config(profile: str) -> None:
    """
    List all configuration values.

    Displays the full configuration for the selected profile in YAML format.

    Examples:

    List all configuration values:
    ```bash
    elastro config list
    ```
    """
    config = get_config(profile=profile)
    masked_config = mask_credentials(config)
    click.echo(yaml.dump(masked_config, default_flow_style=False))


@click.command("init")
@click.option("--force", is_flag=True, help="Force initialization (overwrite existing)")
@click.option("--profile", "-p", default="default", help="Configuration profile")
@coro
async def init_config(force: bool, profile: str) -> None:
    """
    Initialize the configuration file.

    Launches an interactive wizard to help you configure Elastro.

    Examples:

    Initialize configuration (interactive wizard):
    ```bash
    elastro config init
    ```
    """
    config_dir = os.path.dirname(CONFIG_PATH)

    # Create config directory if it does not exist
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)

    # Check if config file exists
    config_exists = os.path.exists(CONFIG_PATH)

    if config_exists and not force:
        click.echo(
            "Configuration file already exists. Use --force to overwrite or launch the wizard."
        )
        if not click.confirm("Do you want to overwrite it and run the wizard?"):
            return

    # Run the interactive wizard
    config = await run_config_wizard()

    if not config:
        click.echo("Configuration cancelled.")
        return

    # Add profile if specified
    if profile != "default":
        # Check if we are merging into existing config
        if config_exists:
            existing = get_config(profile=profile)  # Takes care of loading base config
            # Load raw current config to be safe
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, "r") as f:
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
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(config, f, default_flow_style=False)

    from rich.console import Console

    console = Console()
    console.print(f"[green]Configuration initialized at {CONFIG_PATH}[/]")


async def run_config_wizard() -> Dict[str, Any]:
    """Run interactive wizard to build configuration."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from elastro.core.client import ElasticsearchClient
    from elastro.core.errors import ConnectionError, AuthenticationError

    console = Console()
    console.print(
        Panel(
            "🧙 [bold blue]Elastro Configuration Wizard[/]\nLet's get you connected to Elasticsearch.",
            border_style="blue",
        )
    )

    # 1. Hosts
    console.print("\n[bold]1. Cluster Connection:[/bold]")
    console.print(
        "Provide the HTTP(S) address of your Elasticsearch cluster. Multiple coordinates can be provided (comma-separated) for round-robin load balancing."
    )
    default_host = "http://localhost:9200"
    hosts_input = Prompt.ask("🔌 [bold]Elasticsearch Host[/]", default=default_host)
    hosts = [h.strip() for h in hosts_input.split(",")]

    # 2. Authentication
    console.print("\n🔑 [bold]2. Authentication[/]")
    console.print(
        "Select how Elastro should authenticate with the cluster. API Keys are recommended for production environments."
    )
    auth_type = Prompt.ask(
        "   Method", choices=["basic", "api_key", "none"], default="none"
    )

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
            hosts=hosts, auth=auth, verify_certs=False, use_config=False
        )
        await client.connect()
        info = await client.get_client().info()
        version = info.get("version", {}).get("number", "Unknown")
        cluster_name = info.get("cluster_name", "Unknown")

        console.print(
            f"[bold green]✅ Success! Connected to '{cluster_name}' (v{version})[/]"
        )
        await client.disconnect()

    except (ConnectionError, AuthenticationError) as e:
        console.print(f"[bold red]❌ Connection Failed:[/]\n   {str(e)}")
        if not Confirm.ask("   Save configuration anyway?", default=False):
            return {}

    # 4. Build Config Object
    config = default_config()
    config["elasticsearch"]["hosts"] = hosts
    config["elasticsearch"]["auth"] = auth

    return config
