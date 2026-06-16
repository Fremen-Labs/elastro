"""Build ordered remediation runbooks from index diagnoses."""

from __future__ import annotations

import fnmatch
from typing import Iterable, List, Optional

from elastro.core.index import IndexManager
from elastro.core.logger import get_logger
from elastro.health.remediation.actions.reduce_replicas import resolve_replica_target
from elastro.health.remediation.catalog import RemediationCatalog
from elastro.health.remediation.models import IndexDiagnosis, PlannedAction
from elastro.health.remediation.safety import describe_impact

logger = get_logger(__name__)

_CLUSTER_ACTIONS = frozenset({"reroute_failed"})
_GLOB_CHARS = frozenset("*?[")


def _matches_pattern(index_name: str, pattern: Optional[str]) -> bool:
    if not pattern:
        return True
    return fnmatch.fnmatchcase(index_name, pattern)


class RemediationPlanner:
    """Produce a deduplicated, ordered remediation plan from diagnoses."""

    @staticmethod
    def plan_from_diagnoses(
        index_manager: IndexManager,
        diagnoses: Iterable[IndexDiagnosis],
        *,
        index_pattern: Optional[str] = None,
        action_filter: Optional[str] = None,
        target_replicas: Optional[int] = None,
        api_mode: bool = False,
    ) -> List[PlannedAction]:
        """Map diagnoses to catalog actions with impact text and API previews."""
        planned: List[PlannedAction] = []
        seen_cluster: set[str] = set()

        for diagnosis in diagnoses:
            action_id = diagnosis.suggested_action_id
            if not action_id:
                continue
            if action_filter and action_id != action_filter:
                continue
            if (
                diagnosis.index_name
                and index_pattern
                and not _matches_pattern(diagnosis.index_name, index_pattern)
            ):
                continue

            entry = RemediationCatalog.get(action_id)
            if entry is None:
                logger.warning("Skipping unknown action in plan: %s", action_id)
                continue

            if action_id in _CLUSTER_ACTIONS:
                if action_id in seen_cluster:
                    logger.debug(
                        "Skipping duplicate cluster action %s in plan",
                        action_id,
                    )
                    continue
                seen_cluster.add(action_id)

            resolved_target: Optional[int] = None
            index_name = diagnosis.index_name if entry.requires_index else None

            if action_id == "reduce_replicas" and index_name:
                resolved_target = resolve_replica_target(
                    index_manager,
                    index_name,
                    explicit_target=target_replicas,
                )

            try:
                planned_call = RemediationCatalog.planned_call(
                    action_id,
                    index_name,
                    api_mode=api_mode,
                    target_replicas=resolved_target,
                )
            except ValueError as exc:
                logger.warning(
                    "Cannot plan action %s for %s: %s",
                    action_id,
                    index_name,
                    exc,
                )
                continue

            impact = describe_impact(
                action_id,
                index_name=index_name,
                target_replicas=resolved_target,
            )
            dedupe_key = action_id if action_id in _CLUSTER_ACTIONS else None

            planned.append(
                PlannedAction(
                    action_id=action_id,
                    label=entry.label,
                    safety=entry.safety,
                    impact=impact,
                    index_name=index_name,
                    planned_api_call=planned_call,
                    target_replicas=resolved_target,
                    diagnosis=diagnosis,
                    dedupe_key=dedupe_key,
                )
            )

        logger.info(
            "Remediation plan built: %s action(s) from %s diagnosis(es)",
            len(planned),
            sum(1 for _ in diagnoses),
        )
        return planned

    @staticmethod
    def _resolve_explicit_targets(
        index_manager: IndexManager,
        action_id: str,
        index_pattern: Optional[str],
    ) -> List[str]:
        if action_id in _CLUSTER_ACTIONS:
            return [""]

        if index_pattern and not any(char in index_pattern for char in _GLOB_CHARS):
            return [index_pattern]

        if action_id == "ilm_retry":
            from elastro.health.ilm_status import list_stuck_ilm_indices

            stuck = list_stuck_ilm_indices(
                index_manager._client,
                index_pattern=index_pattern,
            )
            return [item.index_name for item in stuck]

        if action_id == "clear_read_only":
            from elastro.health.disk_blocks import (
                discover_read_only_blocked_indices,
                filter_indices,
            )

            blocked = discover_read_only_blocked_indices(
                index_manager,
                pattern=index_pattern or "*",
            )
            return filter_indices(blocked, index_pattern)

        return []

    @staticmethod
    def plan_explicit(
        index_manager: IndexManager,
        action_id: str,
        *,
        index_pattern: Optional[str] = None,
        target_replicas: Optional[int] = None,
        api_mode: bool = False,
    ) -> List[PlannedAction]:
        """Build a remediation plan for an explicit catalog action."""
        entry = RemediationCatalog.get(action_id)
        if entry is None:
            logger.warning("Cannot plan unknown explicit action: %s", action_id)
            return []

        targets = RemediationPlanner._resolve_explicit_targets(
            index_manager,
            action_id,
            index_pattern,
        )
        if not targets and action_id not in _CLUSTER_ACTIONS:
            logger.info(
                "No targets found for explicit action %s pattern=%s",
                action_id,
                index_pattern,
            )
            return []

        planned: List[PlannedAction] = []
        seen_cluster: set[str] = set()

        for raw_target in targets:
            index_name = raw_target or None
            if action_id in _CLUSTER_ACTIONS:
                if action_id in seen_cluster:
                    continue
                seen_cluster.add(action_id)
                index_name = None

            resolved_target: Optional[int] = None
            if action_id == "reduce_replicas" and index_name:
                resolved_target = resolve_replica_target(
                    index_manager,
                    index_name,
                    explicit_target=target_replicas,
                )

            try:
                planned_call = RemediationCatalog.planned_call(
                    action_id,
                    index_name,
                    api_mode=api_mode,
                    target_replicas=resolved_target,
                )
            except ValueError as exc:
                logger.warning(
                    "Cannot plan explicit action %s for %s: %s",
                    action_id,
                    index_name,
                    exc,
                )
                continue

            planned.append(
                PlannedAction(
                    action_id=action_id,
                    label=entry.label,
                    safety=entry.safety,
                    impact=describe_impact(
                        action_id,
                        index_name=index_name,
                        target_replicas=resolved_target,
                    ),
                    index_name=index_name,
                    planned_api_call=planned_call,
                    target_replicas=resolved_target,
                    dedupe_key=action_id if action_id in _CLUSTER_ACTIONS else None,
                )
            )

        logger.info(
            "Explicit remediation plan built: action=%s targets=%s",
            action_id,
            len(planned),
        )
        return planned
