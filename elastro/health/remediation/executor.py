"""Execute remediation actions with dry-run and interactive confirmation."""

from __future__ import annotations

from typing import Callable, List, Optional

from elastro.core.client import ElasticsearchClient
from elastro.core.index import IndexManager
from elastro.health.remediation.catalog import RemediationCatalog
from elastro.health.remediation.diagnosis import diagnose_unhealthy_indices
from elastro.health.remediation.models import IndexDiagnosis, RemediationResult


ConfirmFn = Callable[[str, bool], bool]
PromptFn = Callable[[str], str]


class RemediationExecutor:
    """Run catalog remediations against unhealthy indices."""

    def __init__(
        self,
        client: ElasticsearchClient,
        *,
        dry_run: bool = False,
        interactive: bool = True,
        confirm: Optional[ConfirmFn] = None,
        api_mode: bool = False,
    ) -> None:
        self._index_manager = IndexManager(client)
        self.dry_run = dry_run
        self.interactive = interactive
        self._confirm = confirm
        self.api_mode = api_mode

    @property
    def index_manager(self) -> IndexManager:
        return self._index_manager

    def _should_execute(self, prompt: str, *, default: bool = True) -> bool:
        if self.dry_run:
            return False
        if not self.interactive:
            return True
        if self._confirm is not None:
            return self._confirm(prompt, default)
        return default

    def execute_action(
        self,
        action_id: str,
        index_name: Optional[str] = None,
        *,
        prompt: Optional[str] = None,
        default_confirm: bool = True,
    ) -> RemediationResult:
        """Execute or preview a single catalog action."""
        entry = RemediationCatalog.get(action_id)
        if entry is None:
            return RemediationResult(
                action_id=action_id,
                index_name=index_name,
                success=False,
                executed=False,
                dry_run=self.dry_run,
                message=f"Unknown remediation action: {action_id}",
            )

        planned = RemediationCatalog.planned_call(
            action_id,
            index_name,
            api_mode=self.api_mode,
        )

        if self.dry_run:
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
        if not self._should_execute(confirm_prompt, default=default_confirm):
            return RemediationResult(
                action_id=action_id,
                index_name=index_name,
                success=True,
                executed=False,
                dry_run=False,
                message="Skipped by user",
                planned_api_call=planned,
            )

        try:
            message = RemediationCatalog.execute(
                action_id,
                self._index_manager,
                index_name,
                api_mode=self.api_mode,
            )
            return RemediationResult(
                action_id=action_id,
                index_name=index_name,
                success=True,
                executed=True,
                dry_run=False,
                message=message,
                planned_api_call=planned,
            )
        except Exception as exc:
            return RemediationResult(
                action_id=action_id,
                index_name=index_name,
                success=False,
                executed=False,
                dry_run=False,
                message=str(exc),
                planned_api_call=planned,
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
            prompt = (
                f"Reduce replicas for '{diagnosis.index_name}' to 0 "
                f"to fix {diagnosis.health} state?"
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
        results: List[RemediationResult] = []
        for diagnosis in diagnose_unhealthy_indices(self._index_manager):
            result = self.remediate_diagnosis(
                diagnosis,
                prompt_builder=prompt_builder,
            )
            if result is not None:
                results.append(result)
        return results