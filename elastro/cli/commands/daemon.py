"""
Daemon management commands.
"""

import sys
import urllib.request

import rich_click as click


@click.group("daemon")
def daemon_group() -> None:
    """
    Manage the Fast-Path Agentic Daemon.
    """
    pass


@daemon_group.command("start")
@click.option("--port", type=int, default=9201, help="Port to run the daemon on")
@click.option(
    "--host", type=str, default="127.0.0.1", help="Host to bind the daemon to"
)
def start(port: int, host: str) -> None:
    """
    Start the Fast-Path CLI Daemon.

    Keeps the Elasticsearch connection hot in memory so subsequent agents querying via
    'elastro doc search' will bypass the slow Python startup sequence.
    """
    try:
        from elastro.core.daemon import start_daemon

        click.echo(f"Starting Elastro Daemon on {host}:{port}...")
        start_daemon(host=host, port=port)
    except ImportError as e:
        click.echo(f"Failed to load daemon dependencies: {e}", err=True)
        sys.exit(1)


@daemon_group.command("status")
@click.option("--port", type=int, default=9201, help="Port the daemon is running on")
def status(port: int) -> None:
    """Check if the Daemon is active."""
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/health")
        with urllib.request.urlopen(req, timeout=1.0) as response:
            if response.status == 200:
                click.echo("Daemon is ONLINE and responding.")
            else:
                click.echo(f"Daemon returned status: {response.status}")
    except Exception as e:
        click.echo(f"Daemon is OFFLINE. ({e})")
