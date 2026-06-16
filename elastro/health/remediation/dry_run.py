"""Dry-run contract helpers for scriptable, mutation-free previews."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from elastro.health.remediation.models import FixRunResult, RemediationResult


def is_preview_mode(*, dry_run: bool = False, plan_only: bool = False) -> bool:
    """Return True when the workflow must not mutate Elasticsearch or local rollback state."""
    return dry_run or plan_only


def planned_rollback_call(index_name: str, settings: Dict[str, Any]) -> str:
    """Describe the API call that would restore rollback settings."""
    return f"PUT /{index_name}/_settings body={settings}"


def summarize_fix_run(result: FixRunResult) -> Dict[str, Any]:
    """Build a stable scripting summary for fix / plan / dry-run passes."""
    executed = sum(1 for item in result.results if item.executed)
    previewed = sum(
        1 for item in result.results if item.dry_run and item.planned_api_call
    )
    return {
        "preview_only": is_preview_mode(
            dry_run=result.dry_run,
            plan_only=result.plan_only,
        ),
        "dry_run": result.dry_run,
        "plan_only": result.plan_only,
        "diagnosis_count": len(result.diagnoses),
        "planned_action_count": len(result.planned_actions),
        "result_count": len(result.results),
        "executed_count": executed,
        "previewed_count": previewed if result.dry_run else len(result.planned_actions),
        "blocked_count": len(result.blocked),
        "session_id": result.session_id,
    }


def fix_run_payload(result: FixRunResult) -> Dict[str, Any]:
    """Serialize a fix run for JSON/YAML CLI output."""
    payload = result.model_dump(mode="json")
    payload["summary"] = summarize_fix_run(result)
    return payload


def remediation_result_payload(result: RemediationResult) -> Dict[str, Any]:
    """Serialize a single remediation result for JSON/YAML CLI output."""
    return result.model_dump(mode="json")


def assert_no_executions(results: Iterable[RemediationResult]) -> None:
    """Raise when any result executed despite preview mode (test helper)."""
    executed = [item for item in results if item.executed]
    if executed:
        actions = ", ".join(
            f"{item.action_id}:{item.index_name or 'cluster'}" for item in executed
        )
        raise RuntimeError(f"Dry-run executed mutations: {actions}")
