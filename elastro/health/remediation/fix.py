"""Unified health fix orchestration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, List, Optional
from uuid import uuid4

from elastro.core.client import ElasticsearchClient
from elastro.core.logger import get_logger

if TYPE_CHECKING:
    from elastro.health.audit import HealthAuditLogger
from elastro.health.remediation.diagnosis import diagnose_unhealthy_indices
from elastro.health.remediation.executor import RemediationExecutor
from elastro.health.remediation.models import FixRunResult, PlannedAction, RemediationResult
from elastro.health.remediation.planner import RemediationPlanner
from elastro.health.remediation.dry_run import is_preview_mode
from elastro.health.remediation.safety import ConfirmFn, PromptFn, RemediationSafetyGate

logger = get_logger(__name__)


def run_health_fix(
    client: ElasticsearchClient,
    *,
    dry_run: bool = False,
    plan_only: bool = False,
    auto_yes: bool = False,
    force: bool = False,
    index_pattern: Optional[str] = None,
    action_filter: Optional[str] = None,
    target_replicas: Optional[int] = None,
    interactive: bool = True,
    api_mode: bool = False,
    session_id: Optional[str] = None,
    cluster_name: Optional[str] = None,
    audit_logger: Optional["HealthAuditLogger"] = None,
    confirm: Optional[ConfirmFn] = None,
    prompt: Optional[PromptFn] = None,
) -> FixRunResult:
    """Diagnose unhealthy indices, plan remediations, and execute or preview them."""
    resolved_session = session_id or str(uuid4())
    preview = is_preview_mode(dry_run=dry_run, plan_only=plan_only)
    executor = RemediationExecutor(
        client,
        dry_run=dry_run or plan_only,
        interactive=interactive and not preview,
        auto_yes=auto_yes,
        force=force,
        api_mode=api_mode and not preview,
        confirm=confirm,
        session_id=resolved_session,
        audit_logger=None if preview else audit_logger,
        cluster_name=cluster_name,
    )

    diagnoses = diagnose_unhealthy_indices(executor.index_manager)
    if index_pattern:
        import fnmatch

        diagnoses = [
            diagnosis
            for diagnosis in diagnoses
            if fnmatch.fnmatchcase(diagnosis.index_name, index_pattern)
        ]

    planned = RemediationPlanner.plan_from_diagnoses(
        executor.index_manager,
        diagnoses,
        index_pattern=index_pattern,
        action_filter=action_filter,
        target_replicas=target_replicas,
        api_mode=api_mode,
    )

    if plan_only:
        return FixRunResult(
            diagnoses=diagnoses,
            planned_actions=planned,
            results=[],
            blocked=[],
            dry_run=True,
            plan_only=True,
            session_id=resolved_session,
        )

    gate = RemediationSafetyGate(
        dry_run=dry_run,
        interactive=interactive,
        auto_yes=auto_yes,
        force=force,
        api_mode=api_mode,
        confirm=confirm,
        prompt=prompt,
    )

    results: List[RemediationResult] = []
    blocked: List[str] = []
    executed_cluster: set[str] = set()

    for planned_action in planned:
        if (
            planned_action.dedupe_key
            and planned_action.dedupe_key in executed_cluster
        ):
            logger.info(
                "Skipping duplicate cluster action %s",
                planned_action.action_id,
            )
            results.append(
                RemediationResult(
                    action_id=planned_action.action_id,
                    index_name=planned_action.index_name,
                    success=True,
                    executed=False,
                    dry_run=dry_run,
                    message="Skipped duplicate cluster action",
                )
            )
            continue

        decision = gate.decide(planned_action)
        if decision.message and not decision.execute:
            blocked.append(decision.message)

        result = executor.execute_planned(
            planned_action,
            confirmed=decision.execute,
            skip_reason=decision.message,
        )
        results.append(result)

        if result.executed and planned_action.dedupe_key:
            executed_cluster.add(planned_action.dedupe_key)

    logger.info(
        "Health fix pass complete: planned=%s executed=%s blocked=%s dry_run=%s",
        len(planned),
        sum(1 for item in results if item.executed),
        len(blocked),
        dry_run,
    )
    return FixRunResult(
        diagnoses=diagnoses,
        planned_actions=planned,
        results=results,
        blocked=blocked,
        dry_run=dry_run,
        plan_only=False,
        session_id=resolved_session,
    )