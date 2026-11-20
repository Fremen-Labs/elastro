"""CLI error rendering and shared exit-code helpers."""

from __future__ import annotations

import logging
import sys
from typing import NoReturn

import rich_click as click

from elastro.core.errors import ElasticModuleError, OperationError


def render_error(exc: ElasticModuleError) -> int:
    """Write one error line to stderr and return operational-failure exit code 1.

    Does not log. Callers (or domain managers) log once with ``exc_info=True``
    before raising the domain error.
    """
    click.echo(str(exc), err=True)
    return 1


def stdin_is_tty() -> bool:
    """Return True when stdin is an interactive terminal."""
    try:
        return sys.stdin.isatty()
    except (ValueError, OSError):
        return False


def usage_error(message: str) -> NoReturn:
    """Write a usage message to stderr and exit 2."""
    click.echo(message, err=True)
    raise SystemExit(2)


def confirm_or_exit(prompt: str, *, yes: bool) -> None:
    """Require ``--yes`` or an interactive confirm before a mutation.

    Non-interactive callers without ``--yes`` exit 2 with no further work.
    An interactive decline exits 0.
    """
    if yes:
        return
    if not stdin_is_tty():
        usage_error("Error: --yes is required in non-interactive mode")
    if not click.confirm(prompt):
        click.echo("Aborted", err=True)
        raise SystemExit(0)


def exit_from_exception(
    exc: Exception,
    *,
    logger: logging.Logger,
    action: str,
) -> NoReturn:
    """Raise ``SystemExit(1)`` for an operational failure.

    Raw transport exceptions are logged once here. Domain errors are rendered
    without a second log line.
    """
    if isinstance(exc, ElasticModuleError):
        raise SystemExit(render_error(exc)) from exc
    logger.error("%s failed: %s", action, exc, exc_info=True)
    raise SystemExit(render_error(OperationError(f"{action} failed: {exc}"))) from exc
