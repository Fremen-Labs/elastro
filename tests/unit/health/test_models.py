"""Unit tests for health assessment models."""

import unittest

from elastro.health.models import (
    AssessmentReport,
    Finding,
    FindingStatus,
    Severity,
    cluster_status_to_score,
    score_to_status,
)


class TestHealthModels(unittest.TestCase):
    def test_cluster_status_to_score(self):
        self.assertEqual(cluster_status_to_score("green"), 100)
        self.assertEqual(cluster_status_to_score("yellow"), 70)
        self.assertEqual(cluster_status_to_score("red"), 30)
        self.assertEqual(cluster_status_to_score("unknown"), 0)

    def test_score_to_status_bands(self):
        self.assertEqual(score_to_status(100), FindingStatus.PASS)
        self.assertEqual(score_to_status(90), FindingStatus.PASS)
        self.assertEqual(score_to_status(89), FindingStatus.WARN)
        self.assertEqual(score_to_status(70), FindingStatus.WARN)
        self.assertEqual(score_to_status(49), FindingStatus.FAIL)
        self.assertEqual(score_to_status(0), FindingStatus.FAIL)

    def test_assessment_report_defaults(self):
        report = AssessmentReport(cluster_name="test-cluster", overall_score=100)
        self.assertEqual(report.schema_version, "1.0")
        self.assertTrue(report.session_id)
        self.assertEqual(report.cluster_name, "test-cluster")
        self.assertEqual(report.findings, [])

    def test_finding_serialization(self):
        finding = Finding(
            id="cluster.status.yellow",
            category="cluster",
            title="Cluster status is yellow",
            status=FindingStatus.WARN,
            severity=Severity.HIGH,
            score_impact=30,
            summary="Cluster reports yellow.",
        )
        data = finding.model_dump()
        self.assertEqual(data["severity"], "high")
        self.assertEqual(data["status"], "warn")


if __name__ == "__main__":
    unittest.main()
