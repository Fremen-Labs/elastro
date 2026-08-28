"""
Daemon management commands.
"""

# fmt: off

import sys

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
    "--host",
    type=str,
    default="127.0.0.1",
    help="Host to bind the daemon to (loopback only)",
)
def start(port: int, host: str) -> None:
    """
    Start the Fast-Path CLI Daemon.

    Keeps the Elasticsearch connection hot in memory so subsequent agents querying via
    'elastro doc search' will bypass the slow Python startup sequence.

    The daemon binds to loopback (127.0.0.1 by default) and requires a shared secret.
    Non-localhost binds are refused.
    """
    try:
        from elastro.core.daemon import (
            DaemonBindError,
            start_daemon,
            validate_daemon_bind,
        )
    except ImportError as e:
        click.echo(f"Failed to load daemon dependencies: {e}", err=True)
        sys.exit(1)

    try:
        validate_daemon_bind(host)
        click.echo(f"Starting Elastro Daemon on {host}:{port}...")
        start_daemon(host=host, port=port)
    except DaemonBindError as e:
        click.echo(str(e), err=True)
        sys.exit(1)


@daemon_group.command("status")
@click.option("--port", type=int, default=9201, help="Port the daemon is running on")
@click.option(
    "--host",
    type=str,
    default="127.0.0.1",
    help="Host the daemon is bound to",
)
def status(port: int, host: str) -> None:
    """Check if the Daemon is active via XML-RPC (not HTTP /health)."""
    from elastro.core.daemon import probe_daemon

    online, detail = probe_daemon(host=host, port=port)
    if online:
        click.echo("Daemon is ONLINE and responding.")
    else:
        click.echo(f"Daemon is OFFLINE. ({detail})")
