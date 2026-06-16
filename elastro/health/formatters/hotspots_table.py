"""Rich formatter for node hotspot variance output."""

from __future__ import annotations

from io import StringIO
from typing import Any, Dict, List

from rich import box
from rich.console import Console
from rich.table import Table


def format_hotspots_table(hotspots: List[Dict[str, Any]]) -> str:
    """Render hotspot variance rows as a Rich table."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=100)

    if not hotspots:
        console.print("No node hotspots detected across JVM, disk, or CPU metrics.")
        return buf.getvalue()

    table = Table(title="Node Hotspots", box=box.ROUNDED, expand=True)
    table.add_column("Metric", style="bold cyan")
    table.add_column("Spread", justify="right")
    table.add_column("Low Node")
    table.add_column("Low Value", justify="right")
    table.add_column("High Node")
    table.add_column("High Value", justify="right")

    for hotspot in hotspots:
        table.add_row(
            str(hotspot.get("label", hotspot.get("metric", ""))),
            f"{float(hotspot.get('spread', 0)):.1f}",
            str(hotspot.get("min_node", "")),
            f"{float(hotspot.get('min_value', 0)):.1f}",
            str(hotspot.get("max_node", "")),
            f"{float(hotspot.get('max_value', 0)):.1f}",
        )

    console.print(table)
    console.print()
    return buf.getvalue()