"""Combined coverage readiness report."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field

from elastro.core.client import ElasticsearchClient
from elastro.core.logger import get_logger
from elastro.coverage.templates import TemplateInfo, TemplateManager
from elastro.coverage.validators import (
    DEFAULT_MIN_DOCS,
    DEFAULT_WINDOW,
    CoverageReport,
    CoverageValidator,
)
from elastro.health.models import Finding, FindingStatus
from elastro.health.rules.apm_beats import is_apm_beats_finding

logger = get_logger(__name__)


class ReadinessReport(BaseModel):
    """Templates + coverage checks + APM/Beats health findings."""

    passed: bool
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    templates: List[TemplateInfo] = Field(default_factory=list)
    coverage: CoverageReport
    health_findings: List[Finding] = Field(default_factory=list)


class ReadinessReporter:
    """Build a single readiness report from templates, checks, and health."""

    def __init__(self, client: ElasticsearchClient) -> None:
        self._client = client
        self._templates = TemplateManager(client)
        self._validator = CoverageValidator(client)

    def report(
        self,
        *,
        service: Optional[str] = None,
        pattern: Optional[str] = None,
        window: str = DEFAULT_WINDOW,
        min_docs: int = DEFAULT_MIN_DOCS,
        max_age: Optional[str] = None,
        max_cardinality: Optional[int] = None,
    ) -> ReadinessReport:
        """Run template status, coverage checks, and APM/Beats health rules."""
        templates = self._templates.list(include_applied=True)
        if service:
            coverage = self._validator.check_service(
                service,
                window=window,
                min_docs=min_docs,
                max_age=max_age,
                max_cardinality=max_cardinality,
            )
        elif pattern:
            coverage = self._validator.check_pattern(
                pattern,
                window=window,
                min_docs=min_docs,
                max_age=max_age,
                max_cardinality=max_cardinality,
            )
        else:
            coverage = self._validator.check_all(
                window=window,
                min_docs=min_docs,
                max_age=max_age,
                max_cardinality=max_cardinality,
            )

        from elastro.health.assessor import HealthAssessor

        assessment = HealthAssessor(self._client).run(
            audit=False,
            coverage_strict=True,
        )
        findings = [
            finding for finding in assessment.findings if is_apm_beats_finding(finding)
        ]
        logger.info(
            "Readiness report templates=%s coverage_passed=%s health_findings=%s",
            len(templates),
            coverage.passed,
            len(findings),
        )
        failed_health = any(
            finding.status == FindingStatus.FAIL for finding in findings
        )
        return ReadinessReport(
            passed=coverage.passed and not failed_health,
            templates=templates,
            coverage=coverage,
            health_findings=findings,
        )
