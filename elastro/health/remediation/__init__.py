"""Safe remediation execution for health findings and unhealthy indices."""

from elastro.health.remediation.catalog import RemediationCatalog
from elastro.health.remediation.dry_run import fix_run_payload, is_preview_mode
from elastro.health.remediation.executor import RemediationExecutor
from elastro.health.remediation.fix import run_health_fix
from elastro.health.remediation.models import (
    FixRunResult,
    IndexDiagnosis,
    PlannedAction,
    RemediationResult,
)
from elastro.health.remediation.planner import RemediationPlanner

__all__ = [
    "fix_run_payload",
    "FixRunResult",
    "is_preview_mode",
    "IndexDiagnosis",
    "PlannedAction",
    "RemediationCatalog",
    "RemediationExecutor",
    "RemediationPlanner",
    "RemediationResult",
    "run_health_fix",
]