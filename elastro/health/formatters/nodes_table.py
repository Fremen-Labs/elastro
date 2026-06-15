"""Rich table formatter for node health stats."""

from __future__ import annotations

from io import StringIO
from typing import Any, Dict, Iterable, List

from rich import box
from rich.console import Console
from rich.table import Table


def _human_bytes(value: Any) -> str:
    if value is None:
        return "—"
    try:
        size = float(value)
    except (TypeError, ValueError):
        return "—"
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def format_nodes_table(
    nodes: Dict[str, Dict[str, Any]],
    metrics: Iterable[str],
) -> str:
    """Render node stats as a Rich table for the requested metrics."""
    metric_list = [metric.strip().lower() for metric in metrics]
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=110)

    table = Table(
        title="Node Health",
        box=box.ROUNDED,
        show_lines=False,
        expand=True,
    )
    table.add_column("Node", style="bold cyan", min_width=16)
    table.add_column("Roles", min_width=12)

    if "jvm" in metric_list:
        table.add_column("Heap %", justify="right", width=8)
        table.add_column("Heap Used", justify="right", width=12)
    if "fs" in metric_list:
        table.add_column("Disk %", justify="right", width=8)
        table.add_column("Available", justify="right", width=12)
    if "os" in metric_list:
        table.add_column("CPU %", justify="right", width=8)
        table.add_column("Load 1m", justify="right", width=8)
    if "breaker" in metric_list:
        table.add_column("Tripped", justify="center", width=8)

    for node in sorted(nodes.values(), key=lambda item: item.get("name", "")):
        roles = ",".join(node.get("roles") or []) or "—"
        row: List[str] = [node.get("name", node.get("id", "unknown")), roles]

        if "jvm" in metric_list:
            jvm = node.get("jvm") or {}
            mem = jvm.get("mem") or {}
            heap_pct = mem.get("heap_used_percent")
            row.append(str(heap_pct) if heap_pct is not None else "—")
            row.append(_human_bytes(mem.get("heap_used_in_bytes")))

        if "fs" in metric_list:
            fs = node.get("fs") or {}
            total = fs.get("total") or {}
            total_bytes = total.get("total_in_bytes")
            available = total.get("available_in_bytes")
            if total_bytes and available is not None and total_bytes > 0:
                used_pct = round(
                    ((total_bytes - available) / total_bytes) * 100,
                    1,
                )
                row.append(str(used_pct))
            else:
                row.append("—")
            row.append(_human_bytes(available))

        if "os" in metric_list:
            os_data = node.get("os") or {}
            cpu = os_data.get("cpu") or {}
            row.append(
                str(cpu.get("percent")) if cpu.get("percent") is not None else "—"
            )
            row.append(
                str(cpu.get("load_average", {}).get("1m"))
                if cpu.get("load_average")
                else "—"
            )

        if "breaker" in metric_list:
            breakers = node.get("breakers") or {}
            tripped = any(
                isinstance(body, dict) and body.get("tripped")
                for body in breakers.values()
            )
            row.append("yes" if tripped else "no")

        table.add_row(*row)

    console.print(table)
    console.print()
    return buf.getvalue()