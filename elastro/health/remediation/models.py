"""Remediation execution models."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from elastro.health.models import RemediationSafety


class IndexDiagnosis(BaseModel):
    """Diagnosis for a single unhealthy index."""

    index_name: str
    health: str
    status: str = "unknown"
    allocate_explanation: str = ""
    reason: str = "UNKNOWN_REASON"
    routing_filter_fault: bool = False
    suggested_action_id: Optional[str] = None
    suggestion_text: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RemediationResult(BaseModel):
    """Outcome of a remediation attempt."""

    action_id: str
    index_name: Optional[str] = None
    success: bool
    executed: bool = False
    dry_run: bool = False
    message: str
    planned_api_call: Optional[str] = None
    rollback_id: Optional[str] = None


class PlannedAction(BaseModel):
    """Single step in an ordered remediation runbook."""

    action_id: str
    label: str
    safety: RemediationSafety
    impact: str
    index_name: Optional[str] = None
    planned_api_call: Optional[str] = None
    target_replicas: Optional[int] = None
    diagnosis: Optional[IndexDiagnosis] = None
    dedupe_key: Optional[str] = None


class FixRunResult(BaseModel):
    """Outcome of a full health fix pass."""

    diagnoses: List[IndexDiagnosis] = Field(default_factory=list)
    planned_actions: List[PlannedAction] = Field(default_factory=list)
    results: List[RemediationResult] = Field(default_factory=list)
    blocked: List[str] = Field(default_factory=list)
    dry_run: bool = False
    plan_only: bool = False
    session_id: Optional[str] = None
