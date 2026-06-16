"""Unit tests for health assessment formatters."""

import json
import unittest

from elastro.health.formatters.json_fmt import format_assessment_json
from elastro.health.formatters.render import render_assessment
from elastro.health.formatters.table import format_assessment_table, score_label
from elastro.health.formatters.yaml_fmt import format_assessment_yaml
from elastro.health.models import (
    AssessmentReport,
    Finding,
    FindingStatus,
    RemediationAction,
    RemediationSafety,
    Severity,
)


class TestFormatters(unittest.TestCase):
    def _sample_report(self) -> AssessmentReport:
        return AssessmentReport(
            cluster_name="docker-cluster",
            elasticsearch_version="8.15.2",
            overall_score=88,
            overall_status=FindingStatus.WARN,
            duration_ms=120,
            findings=[
                Finding(
                    id="indicator.shards_availability",
                    category="shards",
                    title="Shards Availability yellow",
                    status=FindingStatus.WARN,
                    severity=Severity.HIGH,
                    summary="15 unavailable replica shards",
                    indicator="shards_availability",
                    remediation=RemediationAction(
                        id="shards.diagnosis",
                        label="Reduce replicas",
                        command="elastro cluster allocation",
                        safety=RemediationSafety.SUGGEST,
                    ),
                )
            ],
            collectors_run=["health_report", "cluster_health"],
            raw_health_report={"status": "yellow"},
        )

    def test_score_label(self):
        self.assertEqual(score_label(95), "HEALTHY")
        self.assertEqual(score_label(88), "DEGRADED")
        self.assertEqual(score_label(40), "CRITICAL")

    def test_format_assessment_table(self):
        output = format_assessment_table(self._sample_report())
        self.assertIn("docker-cluster", output)
        self.assertIn("88/100", output)
        self.assertIn("Shards Availability", output)
        self.assertIn("15 unavailable replica shards", output)
        self.assertIn("elastro cluster allocation", output)

    def test_format_assessment_json(self):
        payload = json.loads(format_assessment_json(self._sample_report()))
        self.assertEqual(payload["cluster_name"], "docker-cluster")
        self.assertEqual(payload["overall_score"], 88)
        self.assertNotIn("raw_health_report", payload)
        self.assertEqual(len(payload["findings"]), 1)

    def test_format_assessment_json_include_raw(self):
        payload = json.loads(
            format_assessment_json(self._sample_report(), include_raw=True)
        )
        self.assertIn("raw_health_report", payload)

    def test_format_assessment_yaml(self):
        output = format_assessment_yaml(self._sample_report())
        self.assertIn("cluster_name: docker-cluster", output)
        self.assertIn("overall_score: 88", output)

    def test_render_assessment_dispatch(self):
        report = self._sample_report()
        self.assertIn("88/100", render_assessment(report, "table"))
        self.assertIn('"overall_score": 88', render_assessment(report, "json"))

    def test_render_assessment_detail_flag(self):
        from elastro.health.models import Finding, FindingStatus, Severity

        report = self._sample_report()
        report.findings.append(
            Finding(
                id="shards.oversharded",
                category="shards",
                title="Oversharded indices detected",
                status=FindingStatus.WARN,
                severity=Severity.MEDIUM,
                summary="29 shard(s) are smaller than 1.0 MB (OVERSHARDED).",
                detail="Performance implications:\n  • Each shard runs on one thread.",
            )
        )
        table = render_assessment(report, "table", show_detail=True)
        self.assertIn("Finding details", table)
        self.assertIn("Each shard runs on one thread", table)


if __name__ == "__main__":
    unittest.main()