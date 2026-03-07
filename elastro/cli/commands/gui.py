import os
import sys
import rich_click as click
from rich.console import Console
from rich.panel import Panel
from elastro.config.loader import default_config, save_config

console = Console()


@click.command()
def gui() -> None:
    """
    Launch the Elastro Local Web GUI.

    Starts a local web server in the background and prints the secure
    access URL for managing Elasticsearch clusters structurally via the Browser.
    """
    try:
        from elastro.server import launch_gui_process
    except ImportError:
        console.print(
            "[red]Error: GUI dependencies not installed. Please reinstall with `pipx install elastro-client\\[gui]`[/red]"
        )
        sys.exit(1)

    try:
        # Safety measure: ensure base CLI config exists so first-run GUI users
        # get the default localhost cluster seeded into their workspace.
        config_path = os.path.expanduser("~/.elastic/config.yaml")
        if not os.path.exists(config_path):
            try:
                os.makedirs(os.path.dirname(config_path), exist_ok=True)
                save_config(default_config(), path=config_path)
                console.print(
                    f"[dim]Initialized default CLI configuration at {config_path}[/dim]"
                )
            except Exception:
                pass

        url = launch_gui_process()

        banner = """[bold cyan]Elastro Local GUI Launched![/bold cyan]

The server is running securely in the background.
Access your dashboard below:"""

        panel = Panel(
            f"{banner}\n\n[bold green]{url}[/bold green]",
            title="Elastro Settings",
            border_style="cyan",
            expand=False,
        )

        console.print(panel)
        console.print(
            "\n[dim]You can now continue using the terminal or close it.[/dim]\n"
        )

    except Exception as e:
        console.print(f"[bold red]Failed to launch GUI:[/bold red] {str(e)}")
