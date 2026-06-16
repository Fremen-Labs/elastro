"""Table formatters for assessment history and trends."""

from __future__ import annotations

from io import StringIO
from typing import Any, Dict, List, Optional

from rich import box
from rich.console import Console
from rich.table import Table

from elastro.health.formatters.table import score_label
from elastro.health.trends import TrendReport


def _sparkline(scores: List[int], *, width: int = 24) -> str:
    if not scores:
        return ""
    if len(scores) == 1:
        return "▁"

    blocks = "▁▂▃▄▅▆▇█"
    sampled = scores
    if len(scores) > width:
        step = len(scores) / width
        sampled = [scores[int(index * step)] for index in range(width)]

    low = min(sampled)
    high = max(sampled)
    if low == high:
        return blocks[4] * len(sampled)

    chars: List[str] = []
    span = high - low
    for score in sampled:
        normalized = (score - low) / span
        index = min(len(blocks) - 1, int(round(normalized * (len(blocks) - 1))))
        chars.append(blocks[index])
    return "".join(chars)


def format_score_history_table(records: List[Dict[str, Any]]) -> str:
    """Render historical scores with a sparkline-friendly layout."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=110)

    if not records:
        console.print("[dim]No assessment history found.[/]")
        return buf.getvalue()

    chronological = list(reversed(records))
    scores = [int(record.get("overall_score") or 0) for record in chronological]
    spark = _sparkline(scores)

    table = Table(
        title="Assessment History",
        box=box.ROUNDED,
        show_lines=False,
    )
    table.add_column("Assessed At", style="dim")
    table.add_column("Cluster")
    table.add_column("Score", justify="right")
    table.add_column("Status")
    table.add_column("Findings", justify="right")

    for record in records:
        score = int(record.get("overall_score") or 0)
        findings = record.get("findings", [])
        finding_count = len(findings) if isinstance(findings, list) else 0
        table.add_row(
            str(record.get("assessed_at", "")),
            str(record.get("cluster_name", "unknown")),
            f"{score}/100 ({score_label(score)})",
            str(record.get("overall_status", "unknown")),
            str(finding_count),
        )

    console.print(table)
    if spark:
        console.print(f"\nTrend: [cyan]{spark}[/]  ({len(chronological)} samples)")
    return buf.getvalue()


def format_trends_table(report: TrendReport) -> str:
    """Render a trend report for CLI table output."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=110)

    if report.message and report.sample_count == 0:
        console.print(f"[yellow]{report.message}[/]")
        return buf.getvalue()

    delta = report.score_delta_7d
    delta_text = "n/a" if delta is None else f"{delta:+d}"
    console.print(
        f"[bold]{report.cluster_name}[/]  window={report.window}  "
        f"samples={report.sample_count}  delta_7d={delta_text}"
    )

    if report.points:
        scores = [point.overall_score for point in report.points]
        console.print(f"Sparkline: [cyan]{_sparkline(scores)}[/]")

    if report.recurring_findings:
        console.print("\n[bold]Recurring findings[/]")
        for finding_id in report.recurring_findings:
            console.print(f"  • {finding_id}")

    if report.persistent_yellow_count:
        console.print(
            f"\nPersistent yellow samples: [yellow]{report.persistent_yellow_count}[/]"
        )

    return buf.getvalue()


def format_fleet_summary_table(rows: List[Dict[str, Any]], *, window: str) -> str:
    """Render a fleet-wide cluster summary table."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=110)

    if not rows:
        console.print(
            "[yellow]No fleet history found. Run assess --history on each cluster first.[/]"
        )
        return buf.getvalue()

    table = Table(
        title=f"Fleet Health ({window})",
        box=box.ROUNDED,
        show_lines=False,
    )
    table.add_column("Cluster")
    table.add_column("Latest Score", justify="right")
    table.add_column("Status")
    table.add_column("Avg Score", justify="right")
    table.add_column("Samples", justify="right")
    table.add_column("Latest Assessed", style="dim")

    for row in rows:
        latest_score = row.get("latest_score")
        score_text = f"{int(latest_score)}/100" if latest_score is not None else "—"
        table.add_row(
            str(row.get("cluster_name", "unknown")),
            score_text,
            str(row.get("latest_status", "unknown")),
            str(row.get("avg_score", "—")),
            str(row.get("sample_count", 0)),
            str(row.get("latest_assessed_at", "")),
        )

    console.print(table)
    return buf.getvalue()
