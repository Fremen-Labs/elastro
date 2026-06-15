"""Diagnose unhealthy indices and map them to remediation actions."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from elastro.core.index import IndexManager
from elastro.core.logger import get_logger
from elastro.health.remediation.models import IndexDiagnosis

logger = get_logger(__name__)


def detect_routing_filter_fault(explain_result: Dict[str, Any]) -> bool:
    """Return True when allocation is blocked by index routing filters."""
    for node_decision in explain_result.get("node_allocation_decisions", []):
        for decider in node_decision.get("deciders", []):
            explanation = decider.get("explanation", "")
            if decider.get("decider") == "filter" and "index.routing.allocation" in explanation:
                return True
    return False


def suggest_action_id(
    *,
    health: str,
    reason: str,
    allocate_explanation: str,
    routing_filter_fault: bool,
) -> tuple[Optional[str], Optional[str]]:
    """Map allocation explain output to a catalog action id."""
    explanation_lower = allocate_explanation.lower()

    if health == "yellow" and (
        reason in {"CLUSTER_RECOVERED", "REPLICA_ADDED"}
        or (
            "replica" in explanation_lower
            and (
                "permitted" in explanation_lower
                or "too many copies" in explanation_lower
                or "same node" in explanation_lower
            )
        )
    ):
        return (
            "reduce_replicas",
            "The replica count is likely higher than the number of available physical nodes.",
        )

    if reason == "ALLOCATION_FAILED":
        return (
            "reroute_failed",
            "Allocation failed multiple times and hit max retries.",
        )

    if routing_filter_fault:
        return (
            "clear_routing_filters",
            "Explicit node routing filters are preventing shard allocation.",
        )

    return None, None


def diagnose_index(
    index_manager: IndexManager,
    *,
    index_name: str,
    health: str,
    status: str = "unknown",
) -> IndexDiagnosis:
    """Explain allocation for an index and suggest a remediation action."""
    explain_result = index_manager.allocation_explain(index_name)
    allocate_explanation = explain_result.get(
        "allocate_explanation", "No explanation available"
    )
    unassigned_info = explain_result.get("unassigned_info", {})
    reason = unassigned_info.get("reason", "UNKNOWN_REASON")
    routing_filter_fault = detect_routing_filter_fault(explain_result)
    action_id, suggestion = suggest_action_id(
        health=health,
        reason=reason,
        allocate_explanation=str(allocate_explanation),
        routing_filter_fault=routing_filter_fault,
    )
    logger.debug(
        "Diagnosed index %s: health=%s reason=%s action=%s",
        index_name,
        health,
        reason,
        action_id or "none",
    )

    return IndexDiagnosis(
        index_name=index_name,
        health=health,
        status=status,
        allocate_explanation=str(allocate_explanation),
        reason=str(reason),
        routing_filter_fault=routing_filter_fault,
        suggested_action_id=action_id,
        suggestion_text=suggestion,
        metadata={"explain": explain_result},
    )


def list_unhealthy_indices(index_manager: IndexManager) -> List[Dict[str, Any]]:
    """Return cat indices entries that are yellow or red."""
    indices = index_manager.list()
    unhealthy = [
        idx
        for idx in indices
        if idx.get("health", "green") in {"yellow", "red"}
    ]
    logger.info("Found %s unhealthy index(es)", len(unhealthy))
    return unhealthy


def diagnose_unhealthy_indices(index_manager: IndexManager) -> List[IndexDiagnosis]:
    """Scan and diagnose every yellow/red index in the cluster."""
    diagnoses: List[IndexDiagnosis] = []
    for idx in list_unhealthy_indices(index_manager):
        name = str(idx.get("index", "")).strip()
        if not name:
            continue
        health = str(idx.get("health", "unknown"))
        status = str(idx.get("status", "unknown"))
        try:
            diagnoses.append(
                diagnose_index(
                    index_manager,
                    index_name=name,
                    health=health,
                    status=status,
                )
            )
        except Exception as exc:
            logger.warning(
                "Failed to diagnose index %s: %s",
                name,
                exc,
                exc_info=True,
            )
            diagnoses.append(
                IndexDiagnosis(
                    index_name=name,
                    health=health,
                    status=status,
                    allocate_explanation=f"Failed to explain allocation: {exc}",
                    reason="ERROR",
                    metadata={"error": str(exc)},
                )
            )
    logger.info(
        "Diagnosis complete: %s index(es), %s actionable",
        len(diagnoses),
        sum(1 for d in diagnoses if d.suggested_action_id),
    )
    return diagnoses