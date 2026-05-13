"""
Fluent ES|QL query builder.

Constructs syntactically valid ES|QL query strings using a chainable
Python API.  Each method appends a processing command to an internal
pipeline that is rendered into ES|QL text via :meth:`build`.

Usage::

    from elastro.core.esql import ESQLQuery

    q = (
        ESQLQuery("logs-*")
        .where("status_code >= 400")
        .where("@timestamp > now() - 1h")
        .stats("avg_response = AVG(response_time)", by="service.name")
        .sort("avg_response", desc=True)
        .limit(25)
        .build()
    )

    # q == 'FROM logs-* | WHERE status_code >= 400 | WHERE @timestamp > now() - 1h | ...'

The builder enforces structural correctness:

- Exactly one source command (``FROM`` or ``ROW``) is required.
- ``LIMIT`` must have a positive integer value.
- ``build()`` produces the final query string.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Union


class ESQLQuery:
    """Fluent builder for ES|QL queries.

    Args:
        source: Index pattern, data stream, or alias for the ``FROM``
            command.  Pass ``None`` to use :meth:`row` instead.
    """

    def __init__(self, source: Optional[str] = None) -> None:
        self._commands: List[str] = []
        if source is not None:
            self._commands.append(f"FROM {source}")

    # ------------------------------------------------------------------
    # Source commands
    # ------------------------------------------------------------------

    @classmethod
    def from_(cls, source: str, *, metadata: Optional[List[str]] = None) -> "ESQLQuery":
        """Create a query starting with ``FROM``.

        Args:
            source: Index pattern (supports wildcards).
            metadata: Optional metadata fields to include
                (e.g. ``["_index", "_id"]``).
        """
        q = cls(source)
        if metadata:
            q._commands[-1] += f" METADATA {', '.join(metadata)}"
        return q

    @classmethod
    def row(cls, **fields: Any) -> "ESQLQuery":
        """Create a query starting with ``ROW``.

        Each keyword argument becomes a ``field = value`` assignment.
        String values are automatically quoted.
        """
        q = cls()
        assignments = []
        for k, v in fields.items():
            assignments.append(f"{k} = {_format_value(v)}")
        q._commands.append(f"ROW {', '.join(assignments)}")
        return q

    # ------------------------------------------------------------------
    # Processing commands
    # ------------------------------------------------------------------

    def where(self, condition: str) -> "ESQLQuery":
        """Append a ``WHERE`` filter condition.

        Multiple calls are chained as separate ``WHERE`` commands
        (equivalent to AND logic in ES|QL).
        """
        self._commands.append(f"WHERE {condition}")
        return self

    def eval(self, *expressions: str) -> "ESQLQuery":
        """Append an ``EVAL`` command to create or transform columns.

        Args:
            expressions: One or more column expressions
                (e.g. ``"rate = bytes / duration"``).
        """
        self._commands.append(f"EVAL {', '.join(expressions)}")
        return self

    def stats(
        self,
        *aggregations: str,
        by: Optional[Union[str, List[str]]] = None,
    ) -> "ESQLQuery":
        """Append a ``STATS ... BY`` aggregation command.

        Args:
            aggregations: Aggregation expressions
                (e.g. ``"avg_bytes = AVG(bytes)"``).
            by: Group-by field(s).
        """
        cmd = f"STATS {', '.join(aggregations)}"
        if by is not None:
            if isinstance(by, str):
                by = [by]
            cmd += f" BY {', '.join(by)}"
        self._commands.append(cmd)
        return self

    def sort(
        self,
        *fields: str,
        desc: bool = False,
        order: Optional[str] = None,
    ) -> "ESQLQuery":
        """Append a ``SORT`` command.

        Args:
            fields: Field names to sort by.
            desc: Shorthand to sort descending (applied to all fields).
            order: Explicit order string (``ASC`` or ``DESC``).
                Overrides ``desc``.
        """
        direction = order or ("DESC" if desc else "ASC")
        sorted_fields = [f"{f} {direction}" for f in fields]
        self._commands.append(f"SORT {', '.join(sorted_fields)}")
        return self

    def limit(self, n: int) -> "ESQLQuery":
        """Append a ``LIMIT`` command.

        Args:
            n: Maximum number of rows to return.

        Raises:
            ValueError: If *n* is not a positive integer.
        """
        if not isinstance(n, int) or n <= 0:
            raise ValueError(f"LIMIT must be a positive integer, got {n!r}")
        self._commands.append(f"LIMIT {n}")
        return self

    def keep(self, *fields: str) -> "ESQLQuery":
        """Append a ``KEEP`` command to retain only specified columns."""
        self._commands.append(f"KEEP {', '.join(fields)}")
        return self

    def drop(self, *fields: str) -> "ESQLQuery":
        """Append a ``DROP`` command to remove specified columns."""
        self._commands.append(f"DROP {', '.join(fields)}")
        return self

    def rename(self, **mappings: str) -> "ESQLQuery":
        """Append a ``RENAME`` command.

        Args:
            mappings: ``old_name=new_name`` keyword arguments.
        """
        parts = [f"{old} AS {new}" for old, new in mappings.items()]
        self._commands.append(f"RENAME {', '.join(parts)}")
        return self

    def dissect(
        self, field: str, pattern: str, *, append_separator: Optional[str] = None
    ) -> "ESQLQuery":
        """Append a ``DISSECT`` command for text parsing.

        Args:
            field: Source field to parse.
            pattern: Dissect pattern string.
            append_separator: Optional append separator.
        """
        cmd = f'DISSECT {field} "{pattern}"'
        if append_separator is not None:
            cmd += f' APPEND_SEPARATOR="{append_separator}"'
        self._commands.append(cmd)
        return self

    def grok(self, field: str, pattern: str) -> "ESQLQuery":
        """Append a ``GROK`` command for pattern-based text extraction.

        Args:
            field: Source field to parse.
            pattern: Grok pattern string.
        """
        self._commands.append(f'GROK {field} "{pattern}"')
        return self

    def enrich(
        self,
        policy: str,
        *,
        on: Optional[str] = None,
        with_fields: Optional[List[str]] = None,
    ) -> "ESQLQuery":
        """Append an ``ENRICH`` command for data enrichment.

        Args:
            policy: Name of the enrich policy.
            on: Match field.
            with_fields: Fields to add from the enrich index.
        """
        cmd = f"ENRICH {policy}"
        if on:
            cmd += f" ON {on}"
        if with_fields:
            cmd += f" WITH {', '.join(with_fields)}"
        self._commands.append(cmd)
        return self

    def mv_expand(self, field: str) -> "ESQLQuery":
        """Append an ``MV_EXPAND`` command to expand multi-valued fields."""
        self._commands.append(f"MV_EXPAND {field}")
        return self

    def pipe(self, raw_command: str) -> "ESQLQuery":
        """Append a raw ES|QL command string.

        Escape hatch for commands not yet covered by the fluent API.
        """
        self._commands.append(raw_command)
        return self

    # ------------------------------------------------------------------
    # Build & render
    # ------------------------------------------------------------------

    def build(self) -> str:
        """Render the query as an ES|QL string.

        Returns:
            The full ES|QL query string with pipe delimiters.

        Raises:
            ValueError: If no source command (FROM/ROW) was specified.
        """
        if not self._commands:
            raise ValueError(
                "Cannot build an empty ES|QL query. "
                "Start with ESQLQuery('index') or ESQLQuery.row(...)."
            )
        first = self._commands[0].strip()
        if not (first.startswith("FROM") or first.startswith("ROW")):
            raise ValueError(
                f"ES|QL query must start with FROM or ROW, got: {first[:30]!r}"
            )
        return "\n| ".join(self._commands)

    def to_request_body(
        self,
        *,
        params: Optional[List[Any]] = None,
        filter: Optional[Dict[str, Any]] = None,
        columnar: bool = False,
    ) -> Dict[str, Any]:
        """Render the query as a ``_query`` API request body.

        Args:
            params: Positional parameter values for ``?`` placeholders.
            filter: Optional Query DSL pre-filter.
            columnar: Return results in columnar format.
        """
        body: Dict[str, Any] = {"query": self.build()}
        if params:
            body["params"] = params
        if filter:
            body["filter"] = filter
        if columnar:
            body["columnar"] = True
        return body

    def __str__(self) -> str:
        """Return the rendered ES|QL query string."""
        return self.build()

    def __repr__(self) -> str:
        return f"ESQLQuery(commands={len(self._commands)})"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_value(v: Any) -> str:
    """Format a Python value for ES|QL literal syntax."""
    if isinstance(v, str):
        # Escape internal double quotes
        escaped = v.replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return "null"
    return str(v)
