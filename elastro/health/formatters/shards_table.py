"""Rich formatters for shard analysis output."""

from __future__ import annotations

from io import StringIO
from typing import Any, Dict

from rich import box
from rich.console import Console
from rich.table import Table

from elastro.health.shards import format_bytes


def format_shard_analyze_summary(analysis: Dict[str, Any]) -> str:
    """Render the PR-3b shard analyze summary block."""
    total = analysis.get("total_shards", 0)
    avg_bytes = float(analysis.get("avg_bytes", 0))
    oversharded = analysis.get("oversharded_count", 0)
    undersharded = analysis.get("undersharded_count", 0)
    unassigned = analysis.get("unassigned_count", 0)
    overshard_threshold = int(analysis.get("overshard_threshold_bytes", 0))
    undershard_threshold = int(analysis.get("undershard_threshold_bytes", 0))

    lines = [
        f"Total shards: {total:,}",
        f"Avg size: {format_bytes(avg_bytes)}",
        (
            f"< {format_bytes(overshard_threshold)}: {oversharded:,} shards "
            f"(OVERSHARDED)"
        ),
        (
            f"> {format_bytes(undershard_threshold)}: {undersharded:,} shards "
            f"(UNDERSHARDED)"
        ),
    ]
    if unassigned:
        lines.append(f"Unassigned: {unassigned:,}")
    return "\n".join(lines)


def format_shard_analyze_table(analysis: Dict[str, Any]) -> str:
    """Render shard analyze summary plus top offenders as Rich tables."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=100)
    console.print(format_shard_analyze_summary(analysis))
    console.print()

    for label, key in (
        ("Oversharded Shards", "oversharded"),
        ("Undersharded Shards", "undersharded"),
    ):
        rows = analysis.get(key) or []
        if not rows:
            continue
        table = Table(title=label, box=box.ROUNDED, expand=True)
        table.add_column("Index", style="cyan")
        table.add_column("Shard", justify="right")
        table.add_column("Type", justify="center")
        table.add_column("Size", justify="right")
        table.add_column("Node")
        for row in rows[:20]:
            table.add_row(
                str(row.get("index", "")),
                str(row.get("shard", "")),
                str(row.get("prirep", "")),
                format_bytes(float(row.get("store_bytes", 0))),
                str(row.get("node", "")),
            )
        console.print(table)
        console.print()

    return buf.getvalue()