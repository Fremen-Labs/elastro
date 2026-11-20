"""Unit tests for APM/Beats health rules."""

import unittest

from elastro.health.models import FindingStatus
from elastro.health.rules.apm_beats import (
    apm_beats_shard_imbalance_findings,
    apm_data_stream_findings,
    apm_ilm_phase_lag_findings,
    apm_rejection_findings,
    beats_ilm_findings,
)
from elastro.health.rules.engine import RuleContext


class TestApmBeatsRules(unittest.TestCase):
    def test_apm_missing_stream_is_skipped_by_default(self) -> None:
        ctx = RuleContext(
            collector_data={"apm_beats": {"indices": [], "data_streams": []}}
        )
        findings = apm_data_stream_findings(ctx)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].id, "apm.datastream.missing")
        self.assertEqual(findings[0].status, FindingStatus.SKIPPED)
        self.assertEqual(findings[0].score_impact, 0)

    def test_apm_missing_stream_fails_when_strict(self) -> None:
        ctx = RuleContext(
            collector_data={"apm_beats": {"indices": [], "data_streams": []}},
            coverage_strict=True,
        )
        findings = apm_data_stream_findings(ctx)
        self.assertEqual(findings[0].status, FindingStatus.FAIL)
        self.assertEqual(findings[0].score_impact, 15)

    def test_apm_missing_stream_fails_for_feature_apm(self) -> None:
        ctx = RuleContext(
            collector_data={"apm_beats": {"indices": [], "data_streams": []}},
            feature="apm",
        )
        findings = apm_data_stream_findings(ctx)
        self.assertEqual(findings[0].status, FindingStatus.FAIL)

    def test_apm_stale_stream(self) -> None:
        ctx = RuleContext(
            collector_data={
                "apm_beats": {
                    "indices": [{"index": "traces-apm-default"}],
                    "data_streams": [{"name": "traces-apm-default"}],
                    "freshness": {"apm": {"doc_count": 0}},
                }
            }
        )
        findings = apm_data_stream_findings(ctx)
        self.assertEqual(findings[0].id, "apm.datastream.stale")

    def test_apm_fresh_no_finding(self) -> None:
        ctx = RuleContext(
            collector_data={
                "apm_beats": {
                    "indices": [{"index": "traces-apm-default"}],
                    "data_streams": [],
                    "freshness": {"apm": {"doc_count": 12}},
                }
            }
        )
        self.assertEqual(apm_data_stream_findings(ctx), [])

    def test_beats_without_ilm(self) -> None:
        ctx = RuleContext(
            collector_data={
                "apm_beats": {
                    "indices": [{"index": "filebeat-8.15.0"}],
                    "ilm": {"filebeat-8.15.0": {"managed": False, "phase": None}},
                }
            }
        )
        findings = beats_ilm_findings(ctx)
        self.assertEqual(findings[0].id, "beats.ilm.missing")

    def test_beats_truncated_explain_is_not_unmanaged(self) -> None:
        ctx = RuleContext(
            collector_data={
                "apm_beats": {
                    "indices": [{"index": "filebeat-8.15.0"}],
                    "ilm": {},
                    "ilm_truncated": True,
                    "ilm_skipped": ["filebeat-8.15.0"],
                    "ilm_explain_failed": [],
                }
            }
        )
        self.assertEqual(beats_ilm_findings(ctx), [])

    def test_beats_explain_failed_is_unknown(self) -> None:
        ctx = RuleContext(
            collector_data={
                "apm_beats": {
                    "indices": [{"index": "filebeat-8.15.0"}],
                    "ilm": {},
                    "ilm_explain_failed": ["filebeat-8.15.0"],
                    "ilm_skipped": [],
                }
            }
        )
        findings = beats_ilm_findings(ctx)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].id, "beats.ilm.explain_unknown")
        self.assertEqual(findings[0].status, FindingStatus.WARN)

    def test_beats_managed_no_finding(self) -> None:
        ctx = RuleContext(
            collector_data={
                "apm_beats": {
                    "indices": [{"index": "filebeat-8.15.0"}],
                    "ilm": {"filebeat-8.15.0": {"managed": True, "phase": "hot"}},
                }
            }
        )
        self.assertEqual(beats_ilm_findings(ctx), [])

    def test_high_rejection_rate(self) -> None:
        ctx = RuleContext(
            collector_data={
                "apm_beats": {
                    "stats": {
                        "traces-apm-default": {
                            "primaries": {
                                "indexing": {"index_total": 1000, "index_failed": 50}
                            }
                        }
                    }
                }
            }
        )
        findings = apm_rejection_findings(ctx)
        self.assertEqual(findings[0].id, "apm.index.rejections")

    def test_low_rejection_rate_no_finding(self) -> None:
        ctx = RuleContext(
            collector_data={
                "apm_beats": {
                    "stats": {
                        "traces-apm-default": {
                            "primaries": {
                                "indexing": {"index_total": 1000, "index_failed": 1}
                            }
                        }
                    }
                }
            }
        )
        self.assertEqual(apm_rejection_findings(ctx), [])

    def test_shard_imbalance(self) -> None:
        shards = []
        for i in range(4):
            shards.append(
                {
                    "index": "traces-apm-default",
                    "shard": str(i),
                    "prirep": "p",
                    "state": "STARTED",
                    "store": "1000000000" if i else "4000000000",
                    "node": f"n{i}",
                }
            )
        ctx = RuleContext(collector_data={"shards": {"shards": shards}})
        findings = apm_beats_shard_imbalance_findings(ctx)
        self.assertEqual(findings[0].id, "apm.shards.imbalance")

    def test_ilm_hot_lag(self) -> None:
        ctx = RuleContext(
            collector_data={
                "apm_beats": {
                    "ilm": {
                        "traces-apm-default": {
                            "managed": True,
                            "phase": "hot",
                            "age": "3.5d",
                        }
                    }
                }
            }
        )
        findings = apm_ilm_phase_lag_findings(ctx)
        self.assertEqual(findings[0].id, "apm.ilm.hot_lag")
        self.assertIn("ilm explain", findings[0].remediation.command)

    def test_ilm_numeric_age_is_ignored(self) -> None:
        ctx = RuleContext(
            collector_data={
                "apm_beats": {
                    "ilm": {
                        "traces-apm-default": {
                            "managed": True,
                            "phase": "hot",
                            "age": 200000,
                        }
                    }
                }
            }
        )
        self.assertEqual(apm_ilm_phase_lag_findings(ctx), [])

    def test_empty_collector_data_no_findings(self) -> None:
        ctx = RuleContext(collector_data={})
        self.assertEqual(apm_data_stream_findings(ctx), [])
        self.assertEqual(beats_ilm_findings(ctx), [])
        self.assertEqual(apm_rejection_findings(ctx), [])
        self.assertEqual(apm_ilm_phase_lag_findings(ctx), [])
