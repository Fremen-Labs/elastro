"""Pydantic models for health assessment reports and findings."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class FindingStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    UNKNOWN = "unknown"
    SKIPPED = "skipped"


class RemediationSafety(str, Enum):
    OBSERVE = "observe"
    SUGGEST = "suggest"
    CONFIRM = "confirm"
    DESTRUCTIVE = "destructive"


class RemediationAction(BaseModel):
    id: str
    label: str
    command: str
    safety: RemediationSafety
    preconditions: List[str] = Field(default_factory=list)
    rollback_command: Optional[str] = None


class Finding(BaseModel):
    id: str
    category: str
    title: str
    status: FindingStatus
    severity: Severity
    score_impact: int = 0
    summary: str
    detail: Optional[str] = None
    affected_resources: List[str] = Field(default_factory=list)
    source: str = "collector"
    indicator: Optional[str] = None
    remediation: Optional[RemediationAction] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AssessmentReport(BaseModel):
    schema_version: str = "1.0"
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    cluster_name: str = "unknown"
    elasticsearch_version: str = "unknown"
    assessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: int = 0
    overall_score: int = 0
    overall_status: FindingStatus = FindingStatus.UNKNOWN
    findings: List[Finding] = Field(default_factory=list)
    collectors_run: List[str] = Field(default_factory=list)
    collectors_failed: List[str] = Field(default_factory=list)
    raw_health_report: Optional[Dict[str, Any]] = None


def score_to_status(score: int) -> FindingStatus:
    """Map a numeric health score to a status band."""
    if score >= 90:
        return FindingStatus.PASS
    if score >= 70:
        return FindingStatus.WARN
    if score >= 50:
        return FindingStatus.WARN
    return FindingStatus.FAIL


def cluster_status_to_score(status: str) -> int:
    """Map Elasticsearch cluster health color to a baseline score."""
    return {"green": 100, "yellow": 70, "red": 30}.get(status, 0)
