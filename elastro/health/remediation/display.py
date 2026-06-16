"""CLI output helpers for remediation flows."""

from __future__ import annotations

from typing import Iterable, List, Optional

import rich_click as click

from elastro.health.models import RemediationSafety
from elastro.health.remediation.dry_run import fix_run_payload, remediation_result_payload
from elastro.health.remediation.models import (
    FixRunResult,
    IndexDiagnosis,
    PlannedAction,
    RemediationResult,
)

_SAFETY_COLORS = {
    RemediationSafety.OBSERVE: "blue",
    RemediationSafety.SUGGEST: "cyan",
    RemediationSafety.CONFIRM: "yellow",
    RemediationSafety.DESTRUCTIVE: "red",
}


def render_diagnosis_panel(diagnoses: Iterable[IndexDiagnosis]) -> None:
    """Print diagnosis details for unhealthy indices."""
    diagnoses = list(diagnoses)
    if not diagnoses:
        click.echo(
            click.style(
                "\nNo yellow or red indices found; no automated fixes to apply.",
                fg="green",
            )
        )
        return

    click.echo("\nDiagnoses:")
    for diagnosis in diagnoses:
        health_color = "yellow" if diagnosis.health == "yellow" else "red"
        click.echo(
            f"  - {diagnosis.index_name} "
            f"[{click.style(diagnosis.health, fg=health_color)}] "
            f"reason={diagnosis.reason}"
        )
        if diagnosis.allocate_explanation:
            click.echo(f"      {diagnosis.allocate_explanation}")
        if diagnosis.suggestion_text:
            click.echo(
                click.style(
                    f"      Suggestion: {diagnosis.suggestion_text}",
                    fg="cyan",
                )
            )
        elif not diagnosis.suggested_action_id:
            click.echo("      No automated quick fix available.")


def render_remediation_plan(
    planned: Iterable[PlannedAction],
    *,
    dry_run: bool,
    plan_only: bool = False,
) -> None:
    """Print the ordered remediation runbook."""
    planned = list(planned)
    if not planned:
        click.echo(
            click.style(
                "\nNo actionable remediations in the current plan.",
                fg="yellow",
            )
        )
        return

    if plan_only:
        heading = "Remediation runbook (plan only)"
    elif dry_run:
        heading = "Remediation runbook (dry-run)"
    else:
        heading = "Remediation runbook"

    click.echo(f"\n{heading}:")
    for index, action in enumerate(planned, start=1):
        scope = action.index_name or "cluster"
        safety_color = _SAFETY_COLORS.get(action.safety, "white")
        click.echo(
            f"  {index}. [{click.style(action.safety.value, fg=safety_color)}] "
            f"{action.label} — {scope}"
        )
        click.echo(f"      Impact: {action.impact}")
        if action.planned_api_call:
            click.echo(f"      API: {action.planned_api_call}")


def render_fix_run_result(
    result: FixRunResult,
    *,
    output_format: str = "table",
) -> None:
    """Render a complete health fix pass."""
    if output_format != "table":
        from elastro.cli.output import format_output

        click.echo(format_output(fix_run_payload(result), output_format=output_format))
        return

    render_diagnosis_panel(result.diagnoses)
    render_remediation_plan(
        result.planned_actions,
        dry_run=result.dry_run,
        plan_only=result.plan_only,
    )

    if result.blocked:
        click.echo("\nBlocked actions:")
        for message in result.blocked:
            click.echo(click.style(f"  - {message}", fg="yellow"))

    if result.plan_only:
        return

    if result.results:
        click.echo(
            "\nPlanned remediations (dry-run)"
            if result.dry_run
            else "\nRemediation results:"
        )
        for planned, remediation in _zip_planned_results(
            result.planned_actions,
            result.results,
        ):
            _render_single_result(planned, remediation, dry_run=result.dry_run)


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

        _render_legacy_result(diagnosis, result, dry_run=dry_run)


def _zip_planned_results(
    planned: List[PlannedAction],
    results: List[RemediationResult],
) -> List[tuple[Optional[PlannedAction], RemediationResult]]:
    if len(planned) == len(results):
        return list(zip(planned, results))
    return [(None, item) for item in results]


def _render_single_result(
    planned: Optional[PlannedAction],
    result: RemediationResult,
    *,
    dry_run: bool,
) -> None:
    label = planned.label if planned else result.action_id
    scope = result.index_name or "cluster"
    if dry_run:
        click.echo(
            f"  - {scope} [{result.action_id}]: {result.planned_api_call}"
        )
        return

    if result.executed and result.success:
        line = f"  ✓ {scope} ({label}): {result.message}"
        if result.rollback_id:
            line += (
                f"\n    Rollback id: {result.rollback_id} "
                f"(undo: elastro health rollback apply --id {result.rollback_id})"
            )
        click.echo(click.style(line, fg="green"))
    elif not result.executed and result.success:
        click.echo(f"  - {scope}: {result.message}")
    else:
        click.echo(
            click.style(
                f"  ✗ {scope}: {result.message}",
                fg="red",
            )
        )


def _render_legacy_result(
    diagnosis: IndexDiagnosis,
    result: RemediationResult,
    *,
    dry_run: bool,
) -> None:
    if dry_run:
        click.echo(
            f"  - {diagnosis.index_name} [{diagnosis.suggested_action_id}]: "
            f"{result.planned_api_call}"
        )
        return

    if result.executed and result.success:
        line = f"  ✓ {diagnosis.index_name}: {result.message}"
        if result.rollback_id:
            line += (
                f"\n    Rollback id: {result.rollback_id} "
                f"(undo: elastro health rollback apply --id {result.rollback_id})"
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