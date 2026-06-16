"""Rich table formatter for health lint findings."""

from __future__ import annotations

from io import StringIO
from typing import List

from rich import box
from rich.console import Console
from rich.table import Table

from elastro.health.formatters.table import (
    _SEVERITY_ORDER,
    _SEVERITY_STYLE,
    _STATUS_STYLE,
)
from elastro.health.models import Finding


def format_lint_table(findings: List[Finding]) -> str:
    """Render lint findings as a Rich table."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=100)

    if not findings:
        console.print("\n[green]No lint issues found.[/]\n")
        return buf.getvalue()

    sorted_findings = sorted(
        findings,
        key=lambda item: (
            _SEVERITY_ORDER.get(item.severity, 99),
            item.category,
            item.id,
        ),
    )

    table = Table(
        title="Health Lint",
        box=box.ROUNDED,
        show_lines=False,
        expand=True,
    )
    table.add_column("Category", width=10)
    table.add_column("Severity", width=10)
    table.add_column("Finding", min_width=28)
    table.add_column("Status", width=8)
    table.add_column("Action", min_width=20)

    for finding in sorted_findings:
        action = "—"
        if finding.remediation:
            action = finding.remediation.command

        finding_text = finding.title
        if finding.summary and finding.summary != finding.title:
            finding_text = f"{finding.title}\n[dim]{finding.summary}[/]"

        table.add_row(
            finding.category,
            f"[{_SEVERITY_STYLE.get(finding.severity, 'white')}]{finding.severity.value}[/]",
            finding_text,
            f"[{_STATUS_STYLE.get(finding.status.value, 'white')}]{finding.status.value}[/]",
            action,
        )

    console.print()
    console.print(table)
    console.print()
    return buf.getvalue()
