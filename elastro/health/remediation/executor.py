"""Execute remediation actions with dry-run and interactive confirmation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, List, Optional
from uuid import uuid4

from elastro.core.client import ElasticsearchClient
from elastro.core.index import IndexManager
from elastro.core.logger import get_logger

if TYPE_CHECKING:
    from elastro.health.audit import HealthAuditLogger
from elastro.health.remediation.actions.reduce_replicas import resolve_replica_target
from elastro.health.remediation.catalog import RemediationCatalog
from elastro.health.remediation.diagnosis import diagnose_unhealthy_indices
from elastro.health.remediation.models import (
    IndexDiagnosis,
    PlannedAction,
    RemediationResult,
)
from elastro.health.models import RemediationSafety
from elastro.health.remediation.safety import build_confirm_prompt
from elastro.health.remediation.rollback import (
    RollbackStore,
    apply_rollback,
    capture_index_settings,
    create_rollback_record,
    describe_rollback_restore,
)


ConfirmFn = Callable[[str, bool], bool]
PromptFn = Callable[[str], str]

logger = get_logger(__name__)


def build_prompt_from_planned(planned: PlannedAction) -> str:
    """Build a remediation prompt from a planned action."""
    if (
        planned.action_id == "reduce_replicas"
        and planned.index_name
        and planned.target_replicas is not None
        and planned.diagnosis is not None
    ):
        return (
            f"Reduce replicas for '{planned.index_name}' to "
            f"{planned.target_replicas} to fix "
            f"{planned.diagnosis.health} state?"
        )
    if planned.action_id == "reroute_failed":
        return "Force retry allocation via cluster reroute?"
    if planned.action_id == "clear_routing_filters" and planned.index_name:
        return (
            f"Clear all custom node routing allocation filters "
            f"for '{planned.index_name}'?"
        )
    if planned.action_id == "ilm_retry" and planned.index_name:
        return f"Retry ILM lifecycle step for '{planned.index_name}'?"
    if planned.action_id == "clear_read_only" and planned.index_name:
        return (
            f"Clear read_only_allow_delete block for '{planned.index_name}'? "
            f"Ensure disk pressure is resolved first."
        )
    return build_confirm_prompt(planned)


class RemediationExecutor:
    """Run catalog remediations against unhealthy indices."""

    def __init__(
        self,
        client: ElasticsearchClient,
        *,
        dry_run: bool = False,
        interactive: bool = True,
        auto_yes: bool = False,
        force: bool = False,
        confirm: Optional[ConfirmFn] = None,
        api_mode: bool = False,
        session_id: Optional[str] = None,
        rollback_store: Optional[RollbackStore] = None,
        audit_logger: Optional["HealthAuditLogger"] = None,
        cluster_name: Optional[str] = None,
    ) -> None:
        self._index_manager = IndexManager(client)
        self.dry_run = dry_run
        self.interactive = interactive
        self.auto_yes = auto_yes
        self.force = force
        self._confirm = confirm
        self.api_mode = api_mode
        self._session_id = session_id or str(uuid4())
        self._rollback_store = rollback_store or RollbackStore()
        self._audit = audit_logger
        self._cluster_name = cluster_name

    @property
    def index_manager(self) -> IndexManager:
        return self._index_manager

    def _should_execute(
        self,
        prompt: str,
        *,
        default: bool = True,
        safety: Optional[RemediationSafety] = None,
        confirmed: Optional[bool] = None,
    ) -> bool:
        if self.dry_run:
            return False
        if confirmed is not None:
            return confirmed
        if self.api_mode:
            return True
        if not self.interactive:
            if safety == RemediationSafety.DESTRUCTIVE:
                return self.auto_yes and self.force
            if safety in {RemediationSafety.CONFIRM, RemediationSafety.SUGGEST}:
                return self.auto_yes
            return self.auto_yes
        if self._confirm is not None:
            return self._confirm(prompt, default)
        return default

    def execute_action(
        self,
        action_id: str,
        index_name: Optional[str] = None,
        *,
        prompt: Optional[str] = None,
        default_confirm: Optional[bool] = None,
        target_replicas: Optional[int] = None,
        confirmed: Optional[bool] = None,
    ) -> RemediationResult:
        """Execute or preview a single catalog action."""
        entry = RemediationCatalog.get(action_id)
        if entry is None:
            logger.warning("Unknown remediation action requested: %s", action_id)
            return RemediationResult(
                action_id=action_id,
                index_name=index_name,
                success=False,
                executed=False,
                dry_run=self.dry_run,
                message=f"Unknown remediation action: {action_id}",
            )

        resolved_target = target_replicas
        if action_id == "reduce_replicas" and index_name and resolved_target is None:
            resolved_target = resolve_replica_target(
                self._index_manager,
                index_name,
            )

        planned = RemediationCatalog.planned_call(
            action_id,
            index_name,
            api_mode=self.api_mode,
            target_replicas=resolved_target,
        )

        if self.dry_run:
            logger.info(
                "Dry-run remediation %s for index=%s: %s",
                action_id,
                index_name,
                planned,
            )
            return RemediationResult(
                action_id=action_id,
                index_name=index_name,
                success=True,
                executed=False,
                dry_run=True,
                message=entry.label,
                planned_api_call=planned,
            )

        confirm_prompt = prompt or f"Apply {entry.label}?"
        confirm_default = (
            default_confirm
            if default_confirm is not None
            else RemediationCatalog.default_confirm(action_id)
        )
        if not self._should_execute(
            confirm_prompt,
            default=confirm_default,
            safety=entry.safety,
            confirmed=confirmed,
        ):
            logger.info(
                "Remediation skipped: action=%s index=%s",
                action_id,
                index_name,
            )
            return RemediationResult(
                action_id=action_id,
                index_name=index_name,
                success=True,
                executed=False,
                dry_run=False,
                message="Skipped by user",
                planned_api_call=planned,
            )

        rollback_id: Optional[str] = None
        if entry.requires_index and index_name:
            before = capture_index_settings(self._index_manager, index_name)
            if before:
                record = create_rollback_record(
                    session_id=self._session_id,
                    action_id=action_id,
                    index_name=index_name,
                    before=before,
                    cluster_name=self._cluster_name,
                )
                rollback_id = self._rollback_store.save(record)

        try:
            logger.info(
                "Executing remediation %s for index=%s rollback_id=%s",
                action_id,
                index_name,
                rollback_id,
            )
            message = RemediationCatalog.execute(
                action_id,
                self._index_manager,
                index_name,
                api_mode=self.api_mode,
                target_replicas=resolved_target,
            )
            result = RemediationResult(
                action_id=action_id,
                index_name=index_name,
                success=True,
                executed=True,
                dry_run=False,
                message=message,
                planned_api_call=planned,
                rollback_id=rollback_id,
            )
            if self._audit is not None:
                self._audit.log_fix(result, session_id=self._session_id)
            return result
        except Exception as exc:
            logger.error(
                "Remediation failed: action=%s index=%s error=%s",
                action_id,
                index_name,
                exc,
                exc_info=True,
            )
            result = RemediationResult(
                action_id=action_id,
                index_name=index_name,
                success=False,
                executed=False,
                dry_run=False,
                message=str(exc),
                planned_api_call=planned,
                rollback_id=rollback_id,
            )
            if self._audit is not None:
                self._audit.log_fix(result, session_id=self._session_id)
            return result

    def rollback(
        self,
        rollback_id: str,
        *,
        dry_run: bool = False,
    ) -> RemediationResult:
        """Restore settings from a saved rollback snapshot."""
        record = self._rollback_store.get(rollback_id)
        if record is None:
            logger.warning("Rollback not found: rollback_id=%s", rollback_id)
            return RemediationResult(
                action_id="rollback",
                index_name=None,
                success=False,
                executed=False,
                dry_run=dry_run,
                message=f"Rollback '{rollback_id}' not found",
            )

        if (
            record.cluster_name
            and self._cluster_name
            and record.cluster_name != self._cluster_name
        ):
            message = (
                f"Rollback cluster mismatch: snapshot={record.cluster_name} "
                f"connected={self._cluster_name}"
            )
            logger.warning(message)
            return RemediationResult(
                action_id="rollback",
                index_name=record.index_name,
                success=False,
                executed=False,
                dry_run=dry_run,
                message=message,
                rollback_id=rollback_id,
            )

        if not dry_run and self.interactive:
            prompt = (
                f"Restore settings for '{record.index_name}' from "
                f"rollback {rollback_id}?"
            )
            if not self._should_execute(prompt, default=False):
                return RemediationResult(
                    action_id="rollback",
                    index_name=record.index_name,
                    success=True,
                    executed=False,
                    dry_run=False,
                    message="Rollback skipped by user",
                    rollback_id=rollback_id,
                )

        planned_call = describe_rollback_restore(record) if dry_run else None
        try:
            message = apply_rollback(
                self._index_manager,
                record,
                dry_run=dry_run,
            )
            result = RemediationResult(
                action_id="rollback",
                index_name=record.index_name,
                success=True,
                executed=not dry_run,
                dry_run=dry_run,
                message=message,
                planned_api_call=planned_call,
                rollback_id=rollback_id,
            )
            if self._audit is not None:
                self._audit.log_rollback(
                    record,
                    dry_run=dry_run,
                    success=True,
                    message=message,
                )
            return result
        except Exception as exc:
            logger.error(
                "Rollback failed rollback_id=%s: %s",
                rollback_id,
                exc,
                exc_info=True,
            )
            if self._audit is not None:
                self._audit.log_rollback(
                    record,
                    dry_run=dry_run,
                    success=False,
                    message=str(exc),
                )
            return RemediationResult(
                action_id="rollback",
                index_name=record.index_name,
                success=False,
                executed=False,
                dry_run=dry_run,
                message=str(exc),
                rollback_id=rollback_id,
            )

    def execute_planned(
        self,
        planned: PlannedAction,
        *,
        confirmed: Optional[bool] = None,
        skip_reason: Optional[str] = None,
    ) -> RemediationResult:
        """Execute or preview a planned remediation step."""
        entry = RemediationCatalog.get(planned.action_id)
        if entry is None:
            return RemediationResult(
                action_id=planned.action_id,
                index_name=planned.index_name,
                success=False,
                executed=False,
                dry_run=self.dry_run,
                message=f"Unknown remediation action: {planned.action_id}",
            )

        if self.dry_run:
            return RemediationResult(
                action_id=planned.action_id,
                index_name=planned.index_name,
                success=True,
                executed=False,
                dry_run=True,
                message=planned.label,
                planned_api_call=planned.planned_api_call,
            )

        prompt = build_prompt_from_planned(planned)
        confirm_default = RemediationCatalog.default_confirm(planned.action_id)
        should_run = self._should_execute(
            prompt,
            default=confirm_default,
            safety=entry.safety,
            confirmed=confirmed,
        )
        if not should_run:
            message = skip_reason or "Skipped by user"
            return RemediationResult(
                action_id=planned.action_id,
                index_name=planned.index_name,
                success=True,
                executed=False,
                dry_run=False,
                message=message,
                planned_api_call=planned.planned_api_call,
            )

        return self.execute_action(
            planned.action_id,
            planned.index_name,
            prompt=prompt,
            default_confirm=confirm_default,
            target_replicas=planned.target_replicas,
            confirmed=True,
        )

    def remediate_diagnosis(
        self,
        diagnosis: IndexDiagnosis,
        *,
        prompt_builder: Optional[Callable[[IndexDiagnosis, str], str]] = None,
    ) -> Optional[RemediationResult]:
        """Execute the suggested action for a single diagnosis, if any."""
        action_id = diagnosis.suggested_action_id
        if not action_id:
            return None

        entry = RemediationCatalog.get(action_id)
        if entry is None:
            return None

        if prompt_builder is not None:
            prompt = prompt_builder(diagnosis, entry.label)
        elif action_id == "reduce_replicas":
            target = resolve_replica_target(
                self._index_manager,
                diagnosis.index_name,
            )
            prompt = (
                f"Reduce replicas for '{diagnosis.index_name}' to {target} "
                f"to fix {diagnosis.health} state?"
            )
            return self.execute_action(
                action_id,
                diagnosis.index_name,
                prompt=prompt,
                target_replicas=target,
            )
        elif action_id == "reroute_failed":
            prompt = "Force retry allocation via cluster reroute?"
        elif action_id == "clear_routing_filters":
            prompt = (
                f"Clear all custom node routing allocation filters "
                f"for '{diagnosis.index_name}'?"
            )
        else:
            prompt = f"Apply {entry.label} to '{diagnosis.index_name}'?"

        return self.execute_action(
            action_id,
            diagnosis.index_name,
            prompt=prompt,
        )

    def remediate_unhealthy_indices(
        self,
        *,
        prompt_builder: Optional[Callable[[IndexDiagnosis, str], str]] = None,
    ) -> List[RemediationResult]:
        """Scan yellow/red indices and apply or preview suggested fixes."""
        logger.info(
            "Starting unhealthy index remediation (dry_run=%s interactive=%s)",
            self.dry_run,
            self.interactive,
        )
        results: List[RemediationResult] = []
        for diagnosis in diagnose_unhealthy_indices(self._index_manager):
            result = self.remediate_diagnosis(
                diagnosis,
                prompt_builder=prompt_builder,
            )
            if result is not None:
                results.append(result)
        logger.info(
            "Remediation pass complete: planned_or_executed=%s",
            len(results),
        )
        return results