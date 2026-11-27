"""CLI session helpers for the Elasticsearch client."""

from __future__ import annotations

from typing import Optional

import rich_click as click

from elastro.cli.errors import render_error
from elastro.core.client import ElasticsearchClient
from elastro.core.errors import ElasticModuleError, OperationError


def require_client(ctx: Optional[click.Context] = None) -> ElasticsearchClient:
    """Return the session client, connecting on first use.

    An omitted ``ctx`` uses ``click.get_current_context()`` so
    ``@click.pass_obj`` callbacks need no extra parameter. ``ctx.obj`` stays
    the ``ElasticsearchClient``; this helper does not replace it.
    Connect errors are stored on ``ctx.meta["connection_error"]`` and exit 1.
    """
    if ctx is None:
        ctx = click.get_current_context()
    if ctx is None:
        raise RuntimeError("no active Click context")
    error = ctx.meta.get("connection_error")
    if error is not None:
        raise SystemExit(render_error(_as_domain_error(error))) from error

    client = ctx.obj
    if isinstance(client, ElasticsearchClient) and not client._connected:
        try:
            client.connect()
        except Exception as exc:
            ctx.meta["connection_error"] = exc
            raise SystemExit(render_error(_as_domain_error(exc))) from exc
    return client


def _as_domain_error(error: BaseException) -> ElasticModuleError:
    if isinstance(error, ElasticModuleError):
        return error
    return OperationError(str(error))
