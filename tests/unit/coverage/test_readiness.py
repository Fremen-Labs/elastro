"""Unit tests for ReadinessReporter."""

from unittest.mock import patch

from elastro.coverage.readiness import ReadinessReporter
from elastro.coverage.templates import TemplateInfo
from elastro.coverage.validators import CoverageCheck, CoverageReport
from elastro.health.models import AssessmentReport, Finding, FindingStatus, Severity


def _coverage_report(*, passed: bool) -> CoverageReport:
    return CoverageReport(
        passed=passed,
        target="all",
        window="15m",
        checks=[
            CoverageCheck(
                name="doc_count",
                passed=passed,
                summary="ok" if passed else "too few docs",
                doc_count=10 if passed else 0,
            )
        ],
        doc_count=10 if passed else 0,
    )


def test_report_happy_path(es_client) -> None:
    templates = [TemplateInfo(name="apm-traces", description="traces", applied=True)]
    assessment = AssessmentReport(
        findings=[
            Finding(
                id="apm.datastream.stale",
                category="apm",
                title="stale",
                status=FindingStatus.WARN,
                severity=Severity.HIGH,
                summary="stale",
                source="rule",
                indicator="apm",
            ),
            Finding(
                id="jvm.heap_pressure.n1",
                category="jvm",
                title="heap",
                status=FindingStatus.FAIL,
                severity=Severity.HIGH,
                summary="heap",
                source="rule",
            ),
        ]
    )
    with patch("elastro.coverage.readiness.TemplateManager") as tmpl_cls:
        with patch("elastro.coverage.readiness.CoverageValidator") as val_cls:
            with patch("elastro.health.assessor.HealthAssessor") as assessor_cls:
                tmpl_cls.return_value.list.return_value = templates
                val_cls.return_value.check_all.return_value = _coverage_report(
                    passed=True
                )
                assessor_cls.return_value.run.return_value = assessment
                report = ReadinessReporter(es_client).report()
    assert report.passed is True
    assert [item.id for item in report.health_findings] == ["apm.datastream.stale"]


def test_report_fails_when_coverage_fails(es_client) -> None:
    with patch("elastro.coverage.readiness.TemplateManager") as tmpl_cls:
        with patch("elastro.coverage.readiness.CoverageValidator") as val_cls:
            with patch("elastro.health.assessor.HealthAssessor") as assessor_cls:
                tmpl_cls.return_value.list.return_value = []
                val_cls.return_value.check_service.return_value = _coverage_report(
                    passed=False
                )
                assessor_cls.return_value.run.return_value = AssessmentReport()
                report = ReadinessReporter(es_client).report(service="checkout")
    assert report.passed is False
    val_cls.return_value.check_service.assert_called_once()
