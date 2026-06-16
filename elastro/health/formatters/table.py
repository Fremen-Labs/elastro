"""Rich table formatter for health assessment reports."""

from __future__ import annotations

from io import StringIO
from typing import Dict, List, Optional

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from elastro.health.models import AssessmentReport, Finding, Severity

_SEVERITY_ORDER = {
    Severity.CRITICAL: 0,
    Severity.HIGH: 1,
    Severity.MEDIUM: 2,
    Severity.LOW: 3,
    Severity.INFO: 4,
}

_SEVERITY_STYLE = {
    Severity.CRITICAL: "bold red",
    Severity.HIGH: "yellow",
    Severity.MEDIUM: "orange3",
    Severity.LOW: "dim",
    Severity.INFO: "green",
}

_STATUS_STYLE = {
    "pass": "green",
    "warn": "yellow",
    "fail": "bold red",
    "unknown": "dim",
    "skipped": "dim",
}


def score_label(score: int) -> str:
    if score >= 90:
        return "HEALTHY"
    if score >= 70:
        return "DEGRADED"
    if score >= 50:
        return "DEGRADED"
    return "CRITICAL"


def _sort_findings(findings: List[Finding]) -> List[Finding]:
    return sorted(
        findings,
        key=lambda f: (_SEVERITY_ORDER.get(f.severity, 99), f.id),
    )


def format_finding_details(
    findings: List[Finding],
    *,
    finding_id: Optional[str] = None,
) -> str:
    """Render expanded remediation detail for actionable findings."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=110)

    targets = _sort_findings(findings)
    if finding_id:
        targets = [item for item in targets if item.id == finding_id]
    targets = [
        item
        for item in targets
        if item.detail and item.status.value not in {"pass", "skipped"}
    ]
    if not targets:
        return ""

    console.print("\n[bold]Finding details[/]\n")
    for finding in targets:
        console.print(
            Panel(
                finding.detail or "",
                title=f"[bold]{finding.title}[/] [dim]({finding.id})[/]",
                border_style="yellow" if finding.severity == Severity.MEDIUM else "red",
            )
        )
    console.print()
    return buf.getvalue()


def format_assessment_table(
    report: AssessmentReport,
    *,
    show_detail: bool = False,
    detail_finding: Optional[str] = None,
) -> str:
    """Render an assessment report as a Rich table."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=100)

    label = score_label(report.overall_score)
    status_style = _STATUS_STYLE.get(report.overall_status.value, "white")
    banner = (
        f"[bold]{report.cluster_name}[/]  │  "
        f"Score: [{status_style}]{report.overall_score}/100 ({label})[/]  │  "
        f"ES {report.elasticsearch_version}  │  "
        f"{report.duration_ms}ms"
    )
    console.print(Panel(banner, border_style="cyan"))

    findings = _sort_findings(report.findings)
    if not findings:
        console.print("\n[green]No actionable findings. Cluster looks healthy.[/]\n")
        return buf.getvalue()

    table = Table(
        title="Health Findings",
        box=box.ROUNDED,
        show_lines=False,
        expand=True,
    )
    table.add_column("Severity", style="bold", width=10)
    table.add_column("Finding", min_width=24)
    table.add_column("Status", width=8)
    table.add_column("Action", min_width=20)

    for finding in findings:
        action = "—"
        if finding.remediation:
            action = finding.remediation.command
        elif finding.detail:
            action = "elastro health assess --detail"

        finding_text = finding.title
        if finding.summary and finding.summary != finding.title:
            finding_text = f"{finding.title}\n[dim]{finding.summary}[/]"

        table.add_row(
            f"[{_SEVERITY_STYLE.get(finding.severity, 'white')}]{finding.severity.value}[/]",
            finding_text,
            f"[{_STATUS_STYLE.get(finding.status.value, 'white')}]{finding.status.value}[/]",
            action,
        )

    console.print()
    console.print(table)

    if report.collectors_failed:
        console.print(
            f"\n[dim]Collectors failed: {', '.join(report.collectors_failed)}[/]"
        )

    output = buf.getvalue()
    if show_detail:
        output += format_finding_details(
            report.findings,
            finding_id=detail_finding,
        )
    else:
        detail_findings = [
            item
            for item in findings
            if item.detail and item.status.value not in {"pass", "skipped"}
        ]
        if detail_findings:
            output += (
                "\n[dim]Tip: run with --detail (or --detail shards.oversharded) "
                "for remediation guidance.[/]\n"
            )
    return output