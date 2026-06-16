"""CLI output helpers for remediation flows."""

from __future__ import annotations

from typing import Iterable, List

import rich_click as click

from elastro.health.remediation.models import IndexDiagnosis, RemediationResult


def render_remediation_summary(
    diagnoses: Iterable[IndexDiagnosis],
    results: List[RemediationResult],
    *,
    dry_run: bool,
) -> None:
    """Print remediation dry-run or execution results."""
    diagnoses = list(diagnoses)
    if not diagnoses:
        click.echo(
            click.style(
                "\nNo yellow or red indices found; no automated fixes to apply.",
                fg="green",
            )
        )
        return

    heading = (
        "Planned remediations (dry-run)"
        if dry_run
        else "Remediation results"
    )
    click.echo(f"\n{heading}:")
    for diagnosis in diagnoses:
        if not diagnosis.suggested_action_id:
            click.echo(
                f"  - {diagnosis.index_name}: no automated quick fix available"
            )
            continue

        matching = [
            r
            for r in results
            if r.index_name == diagnosis.index_name
            and r.action_id == diagnosis.suggested_action_id
        ]
        result = matching[0] if matching else None
        if result is None:
            continue

        if dry_run:
            click.echo(
                f"  - {diagnosis.index_name} [{diagnosis.suggested_action_id}]: "
                f"{result.planned_api_call}"
            )
            continue

        if result.executed and result.success:
            line = f"  ✓ {diagnosis.index_name}: {result.message}"
            if result.rollback_id:
                line += (
                    f"\n    Rollback id: {result.rollback_id} "
                    f"(undo: elastro health rollback --id {result.rollback_id})"
                )
            click.echo(click.style(line, fg="green"))
        elif not result.executed and result.success:
            click.echo(f"  - {diagnosis.index_name}: skipped")
        else:
            click.echo(
                click.style(
                    f"  ✗ {diagnosis.index_name}: {result.message}",
                    fg="red",
                )
            )

