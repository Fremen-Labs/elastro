import rich_click as click
from rich.console import Console
from rich.panel import Panel
from elastro.server import launch_gui_process

console = Console()

@click.command()
def gui() -> None:
    """
    Launch the Elastro Local Web GUI.
    
    Starts a local web server in the background and prints the secure
    access URL for managing Elasticsearch clusters structurally via the Browser.
    """
    try:
        url = launch_gui_process()
        
        banner = """[bold cyan]Elastro Local GUI Launched![/bold cyan]

The server is running securely in the background.
Access your dashboard below:"""

        panel = Panel(
            f"{banner}\n\n[bold green]{url}[/bold green]",
            title="Elastro Settings",
            border_style="cyan",
            expand=False
        )
        
        console.print(panel)
        console.print("\n[dim]You can now continue using the terminal or close it.[/dim]\n")
        
    except Exception as e:
        console.print(f"[bold red]Failed to launch GUI:[/bold red] {str(e)}")
