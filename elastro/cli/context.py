"""CLI session helpers for the Elasticsearch client."""

from __future__ import annotations

from typing import Optional

import rich_click as click

from elastro.cli.errors import render_error
from elastro.core.client import ElasticsearchClient
from elastro.core.errors import ElasticModuleError, OperationError


def require_client(ctx: Optional[click.Context] = None) -> ElasticsearchClient:
    """Return the session client, or exit 1 if connect already failed.

    An omitted ``ctx`` uses ``click.get_current_context()`` so
    ``@click.pass_obj`` callbacks need no extra parameter. ``ctx.obj`` stays
    the ``ElasticsearchClient``; this helper does not replace it.
    """
    if ctx is None:
        ctx = click.get_current_context()
    error = ctx.meta.get("connection_error")
    if error is not None:
        domain_error: ElasticModuleError
        if isinstance(error, ElasticModuleError):
            domain_error = error
        else:
            domain_error = OperationError(str(error))
        raise SystemExit(render_error(domain_error)) from error
    return ctx.obj
