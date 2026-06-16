"""Elasticsearch health assessment and diagnostics."""

from elastro.health.models import (
    AssessmentReport,
    Finding,
    FindingStatus,
    RemediationAction,
    RemediationSafety,
    Severity,
)
from elastro.health.assessor import HealthAssessor
from elastro.health.collectors.health_report import (
    HealthReportCollector,
    map_indicators,
)
from elastro.health.manager import HealthManager
from elastro.health.remediation import RemediationCatalog, RemediationExecutor

__all__ = [
    "AssessmentReport",
    "Finding",
    "FindingStatus",
    "HealthAssessor",
    "HealthManager",
    "HealthReportCollector",
    "map_indicators",
    "RemediationAction",
    "RemediationCatalog",
    "RemediationExecutor",
    "RemediationSafety",
    "Severity",
]
