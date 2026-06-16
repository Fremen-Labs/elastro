"""Safety prompts and impact descriptions for remediation actions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from elastro.health.models import RemediationSafety
from elastro.health.remediation.catalog import RemediationCatalog
from elastro.health.remediation.models import PlannedAction

ConfirmFn = Callable[[str, bool], bool]
PromptFn = Callable[[str], str]

_IMPACTS: dict[str, str] = {
    "reduce_replicas": (
        "Reduces replica copies and high-availability resilience. "
        "Surviving node loss may cause data unavailability until topology "
        "recovers. A rollback snapshot is captured before applying."
    ),
    "reroute_failed": (
        "Retries failed shard allocations cluster-wide. May increase "
        "master and data-node load and temporarily affect indexing or "
        "search latency while shards relocate."
    ),
    "clear_routing_filters": (
        "Removes custom index routing allocation filters. Shards may move "
        "to nodes that were intentionally excluded, changing performance "
        "characteristics and cluster topology."
    ),
    "ilm_retry": (
        "Retries the current ILM lifecycle step. May trigger rollover, "
        "forcemerge, shrink, or snapshot operations depending on policy phase."
    ),
    "clear_read_only": (
        "Removes the flood-stage read_only_allow_delete block so writes and "
        "deletes are allowed again. Only use after disk pressure is resolved; "
        "otherwise Elasticsearch may re-block the index."
    ),
}


def describe_impact(
    action_id: str,
    *,
    index_name: Optional[str] = None,
    target_replicas: Optional[int] = None,
) -> str:
    """Return human-readable consequences for a catalog action."""
    base = _IMPACTS.get(
        action_id,
        "May change cluster or index state. Review the planned API call.",
    )
    if action_id == "reduce_replicas" and index_name and target_replicas is not None:
        return (
            f"Set '{index_name}' replicas to {target_replicas}. {base}"
        )
    if index_name:
        return f"Apply to index '{index_name}'. {base}"
    return base


def build_confirm_prompt(planned: PlannedAction) -> str:
    """Build the primary yes/no confirmation prompt."""
    scope = (
        f" for '{planned.index_name}'"
        if planned.index_name
        else " (cluster-wide)"
    )
    return f"Apply {planned.label}{scope}?"


def requires_force(safety: RemediationSafety, *, auto_yes: bool) -> bool:
    """Return True when --force is required alongside --yes."""
    return safety == RemediationSafety.DESTRUCTIVE and auto_yes


def can_auto_confirm(
    safety: RemediationSafety,
    *,
    auto_yes: bool,
    force: bool,
    api_mode: bool = False,
) -> bool:
    """Return True when confirmation can be skipped safely."""
    if api_mode:
        return True
    if safety in {RemediationSafety.OBSERVE, RemediationSafety.SUGGEST}:
        return True
    if safety == RemediationSafety.CONFIRM:
        return auto_yes
    if safety == RemediationSafety.DESTRUCTIVE:
        return auto_yes and force
    return False


def refusal_message(
    planned: PlannedAction,
    *,
    auto_yes: bool,
    force: bool,
    interactive: bool,
) -> Optional[str]:
    """Explain why an action was blocked in non-interactive mode."""
    if interactive:
        return None
    if can_auto_confirm(planned.safety, auto_yes=auto_yes, force=force):
        return None
    if planned.safety == RemediationSafety.DESTRUCTIVE:
        if auto_yes and not force:
            return (
                f"Blocked {planned.action_id}: destructive actions require "
                f"--force with --yes in non-interactive mode"
            )
        return (
            f"Blocked {planned.action_id}: destructive action requires "
            f"interactive confirmation or --yes --force"
        )
    if planned.safety == RemediationSafety.CONFIRM:
        return (
            f"Blocked {planned.action_id}: confirmation required; "
            f"use --yes to auto-confirm or run interactively"
        )
    return f"Blocked {planned.action_id}: confirmation required"


@dataclass
class ConfirmDecision:
    """Result of evaluating whether to execute a planned action."""

    execute: bool
    message: Optional[str] = None


class RemediationSafetyGate:
    """Interactive and non-interactive confirmation for planned actions."""

    def __init__(
        self,
        *,
        dry_run: bool,
        interactive: bool,
        auto_yes: bool = False,
        force: bool = False,
        api_mode: bool = False,
        confirm: Optional[ConfirmFn] = None,
        prompt: Optional[PromptFn] = None,
    ) -> None:
        self.dry_run = dry_run
        self.interactive = interactive
        self.auto_yes = auto_yes
        self.force = force
        self.api_mode = api_mode
        self._confirm = confirm
        self._prompt = prompt

    def decide(self, planned: PlannedAction) -> ConfirmDecision:
        """Determine whether a planned action should execute."""
        if self.dry_run:
            return ConfirmDecision(execute=False)

        refusal = refusal_message(
            planned,
            auto_yes=self.auto_yes,
            force=self.force,
            interactive=self.interactive,
        )
        if refusal:
            return ConfirmDecision(execute=False, message=refusal)

        if can_auto_confirm(
            planned.safety,
            auto_yes=self.auto_yes,
            force=self.force,
            api_mode=self.api_mode,
        ):
            return ConfirmDecision(execute=True)

        if not self.interactive:
            return ConfirmDecision(
                execute=False,
                message=refusal_message(
                    planned,
                    auto_yes=self.auto_yes,
                    force=self.force,
                    interactive=False,
                ),
            )

        return self._interactive_confirm(planned)

    def _interactive_confirm(self, planned: PlannedAction) -> ConfirmDecision:
        entry = RemediationCatalog.get(planned.action_id)
        default = RemediationCatalog.default_confirm(planned.action_id)
        prompt = build_confirm_prompt(planned)

        if (
            planned.safety == RemediationSafety.DESTRUCTIVE
            and planned.index_name
            and self._prompt is not None
        ):
            if self._confirm is not None and not self._confirm(
                f"{prompt}\n\nImpact: {planned.impact}",
                False,
            ):
                return ConfirmDecision(execute=False, message="Skipped by user")
            typed = self._prompt(
                f"Type index name '{planned.index_name}' to confirm "
                f"{entry.label if entry else planned.action_id}:"
            )
            if typed.strip() != planned.index_name:
                return ConfirmDecision(
                    execute=False,
                    message="Confirmation failed: index name did not match",
                )
            return ConfirmDecision(execute=True)

        if self._confirm is None:
            return ConfirmDecision(execute=default)

        impact_line = f"\n\nImpact: {planned.impact}" if planned.impact else ""
        if self._confirm(f"{prompt}{impact_line}", default):
            return ConfirmDecision(execute=True)
        return ConfirmDecision(execute=False, message="Skipped by user")