"""Unit tests for the health report collector and mapper."""

import json
import unittest
from pathlib import Path
from unittest.mock import Mock

from elastro.core.client import ElasticsearchClient
from elastro.health.collectors.base import CollectContext
from elastro.health.collectors.health_report import (
    HealthReportCollector,
    map_indicator,
    map_indicators,
    non_passing_findings,
)
from elastro.health.models import FindingStatus
from elastro.health.scoring import compute_weighted_score
from elastro.health.version import parse_version, supports_health_report

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "health"


def _load_fixture(name: str) -> dict:
    with open(FIXTURES / name, encoding="utf-8") as handle:
        return json.load(handle)


class TestVersionGating(unittest.TestCase):
    def test_parse_version(self):
        self.assertEqual(parse_version("8.15.2"), (8, 15, 2))
        self.assertEqual(parse_version("8.7.0"), (8, 7, 0))
        self.assertEqual(parse_version("7.17.18"), (7, 17, 18))

    def test_supports_health_report(self):
        self.assertTrue(supports_health_report("8.7.0"))
        self.assertTrue(supports_health_report("8.15.2"))
        self.assertFalse(supports_health_report("8.6.2"))
        self.assertFalse(supports_health_report("7.17.18"))


class TestHealthReportMapper(unittest.TestCase):
    def test_map_all_nine_indicators_from_green_fixture(self):
        report = _load_fixture("health_report_green.json")
        findings = map_indicators(report)
        self.assertEqual(len(findings), 9)
        indicators = {f.indicator for f in findings}
        self.assertIn("file_settings", indicators)
        self.assertTrue(all(f.status == FindingStatus.PASS for f in findings))

    def test_map_shards_yellow_extracts_diagnosis_action(self):
        report = _load_fixture("health_report_shards_yellow.json")
        findings = map_indicators(report)
        self.assertEqual(len(findings), 9)
        shards = next(f for f in findings if f.indicator == "shards_availability")
        self.assertEqual(shards.status, FindingStatus.WARN)
        self.assertIsNotNone(shards.remediation)
        self.assertIn("nodes", shards.remediation.label.lower())
        self.assertEqual(shards.remediation.command, "elastro cluster allocation")
        missing = next(f for f in findings if f.id == "indicator.file_settings.missing")
        self.assertEqual(missing.status, FindingStatus.SKIPPED)

    def test_map_disk_red_extracts_cause_and_action(self):
        report = _load_fixture("health_report_disk_red.json")
        finding = map_indicator("disk", report["indicators"]["disk"])
        self.assertEqual(finding.status, FindingStatus.FAIL)
        self.assertIn("flood-stage", finding.detail)
        self.assertIn("Free up disk space", finding.detail)
        self.assertEqual(finding.affected_resources, ["node-1"])

    def test_non_passing_findings_filters_green(self):
        report = _load_fixture("health_report_shards_yellow.json")
        findings = map_indicators(report)
        non_pass = non_passing_findings(findings)
        self.assertEqual(len(non_pass), 1)
        self.assertEqual(non_pass[0].indicator, "shards_availability")

    def test_weighted_score_shards_yellow(self):
        report = _load_fixture("health_report_shards_yellow.json")
        score = compute_weighted_score(report["indicators"])
        self.assertGreater(score, 50)
        self.assertLess(score, 100)

    def test_weighted_score_disk_red(self):
        report = _load_fixture("health_report_disk_red.json")
        score = compute_weighted_score(report["indicators"])
        self.assertLess(score, 90)


class TestHealthReportCollector(unittest.TestCase):
    def setUp(self):
        self.mock_es = Mock()
        self.mock_client = Mock(spec=ElasticsearchClient)
        self.mock_client.client = self.mock_es
        self.collector = HealthReportCollector()

    def test_skips_when_es_version_below_8_7(self):
        ctx = CollectContext(client=self.mock_client, es_version="8.6.0")
        result = self.collector.collect(ctx)
        self.assertEqual(result.status, "skipped")
        self.mock_es.health_report.assert_not_called()

    def test_collects_report_on_supported_version(self):
        report = _load_fixture("health_report_green.json")
        self.mock_es.health_report.return_value = report
        ctx = CollectContext(client=self.mock_client, es_version="8.15.2")
        result = self.collector.collect(ctx)

        self.assertEqual(result.status, "ok")
        self.mock_es.health_report.assert_called_once_with(verbose=True)
        self.assertEqual(len(result.data["findings"]), 9)
        self.assertEqual(result.data["cluster_name"], "test-cluster")

    def test_skips_on_404(self):
        exc = Exception("not found")
        exc.status_code = 404  # type: ignore[attr-defined]
        self.mock_es.health_report.side_effect = exc
        ctx = CollectContext(client=self.mock_client, es_version="8.15.2")
        result = self.collector.collect(ctx)
        self.assertEqual(result.status, "skipped")

    def test_returns_error_on_non_404_failure(self):
        exc = Exception("connection refused")
        self.mock_es.health_report.side_effect = exc
        ctx = CollectContext(client=self.mock_client, es_version="8.15.2")
        result = self.collector.collect(ctx)
        self.assertEqual(result.status, "error")

    def test_passes_verbose_false_to_api(self):
        report = _load_fixture("health_report_green.json")
        self.mock_es.health_report.return_value = report
        ctx = CollectContext(client=self.mock_client, es_version="8.15.2")
        ctx.options["verbose_report"] = False
        result = self.collector.collect(ctx)
        self.assertEqual(result.status, "ok")
        self.mock_es.health_report.assert_called_once_with(verbose=False)

    def test_feature_filter_passed_to_api(self):
        report = _load_fixture("health_report_green.json")
        self.mock_es.health_report.return_value = report
        ctx = CollectContext(client=self.mock_client, es_version="8.15.2")
        ctx.options["feature"] = "disk"
        result = self.collector.collect(ctx)
        self.assertEqual(result.status, "ok")
        self.mock_es.health_report.assert_called_once_with(
            feature="disk", verbose=True
        )


if __name__ == "__main__":
    unittest.main()