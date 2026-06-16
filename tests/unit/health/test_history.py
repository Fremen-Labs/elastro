"""Unit tests for assessment history indexing."""

from unittest.mock import MagicMock

from elastro.health.history import (
    assessment_document,
    ensure_index,
    filter_records_by_window,
    history_cluster_summary,
    index_assessment,
    parse_window,
    query_assessment_history,
    sanitize_host,
)
from elastro.health.models import AssessmentReport, FindingStatus


class TestAssessmentHistory:
    def test_assessment_document_strips_raw_report(self):
        report = AssessmentReport(
            cluster_name="docker-cluster",
            overall_score=90,
            overall_status=FindingStatus.PASS,
            raw_health_report={"status": "green"},
        )
        document = assessment_document(
            report,
            profile="prod",
            host="http://localhost:9205",
        )
        assert document["cluster_name"] == "docker-cluster"
        assert document["profile"] == "prod"
        assert "raw_health_report" not in document

    def test_index_assessment_creates_index_when_missing(self):
        client = MagicMock()
        client.client.indices.exists.return_value = False
        report = AssessmentReport(cluster_name="docker-cluster")
        index_assessment(client, report, history_index="elastro-health-assessments")
        client.client.indices.create.assert_called_once()
        client.client.index.assert_called_once()

    def test_query_assessment_history_returns_sources(self):
        client = MagicMock()
        client.client.search.return_value = {
            "hits": {
                "hits": [
                    {"_source": {"cluster_name": "c1", "overall_score": 88}},
                ]
            }
        }
        records = query_assessment_history(
            client,
            history_index="elastro-health-assessments",
            limit=5,
        )
        assert len(records) == 1
        assert records[0]["overall_score"] == 88

    def test_assessment_document_sanitizes_host(self):
        report = AssessmentReport(cluster_name="docker-cluster")
        document = assessment_document(
            report,
            host="https://user:pass@localhost:9200",
        )
        assert document["host"] == "https://localhost:9200"

    def test_query_assessment_history_applies_window_filter(self):
        client = MagicMock()
        client.client.search.return_value = {"hits": {"hits": []}}
        query_assessment_history(
            client,
            cluster_name="c1",
            profile="prod",
            window="7d",
            finding_id="disk.watermark.high",
            limit=3,
        )
        body = client.client.search.call_args.kwargs.get("body")
        filters = body["query"]["bool"]["filter"]
        assert {"term": {"cluster_name": "c1"}} in filters
        assert {"term": {"profile": "prod"}} in filters
        assert any("range" in item for item in filters)
        assert any("nested" in item for item in filters)

    def test_history_cluster_summary_parses_aggregations(self):
        client = MagicMock()
        client.client.search.return_value = {
            "aggregations": {
                "by_cluster": {
                    "buckets": [
                        {
                            "key": "c1",
                            "sample_count": {"value": 3},
                            "avg_score": {"value": 81.5},
                            "latest": {
                                "hits": {
                                    "hits": [
                                        {
                                            "_source": {
                                                "cluster_name": "c1",
                                                "overall_score": 82,
                                                "overall_status": "warn",
                                                "assessed_at": "2026-06-15T10:00:00+00:00",
                                            }
                                        }
                                    ]
                                }
                            },
                        }
                    ]
                }
            }
        }
        rows = history_cluster_summary(client, window="7d")
        assert rows[0]["cluster_name"] == "c1"
        assert rows[0]["latest_score"] == 82
        assert rows[0]["sample_count"] == 3

    def test_parse_window_hours(self):
        assert parse_window("24h").total_seconds() == 24 * 3600

    def test_query_assessment_history_missing_index_returns_empty(self):
        client = MagicMock()
        client.client.search.side_effect = Exception(
            "index_not_found_exception: no such index [elastro-health-assessments]"
        )

        records = query_assessment_history(
            client, history_index="elastro-health-assessments"
        )

        assert records == []

    def test_history_cluster_summary_missing_index_returns_empty(self):
        client = MagicMock()
        client.client.search.side_effect = Exception(
            "index_not_found_exception: no such index [elastro-health-assessments]"
        )

        rows = history_cluster_summary(client, window="7d")

        assert rows == []

    def test_filter_records_by_window(self):
        from datetime import datetime, timedelta, timezone

        recent = datetime.now(timezone.utc) - timedelta(hours=1)
        stale = datetime.now(timezone.utc) - timedelta(days=10)
        records = [
            {"assessed_at": recent.isoformat(), "overall_score": 80},
            {"assessed_at": stale.isoformat(), "overall_score": 60},
        ]

        filtered = filter_records_by_window(records, "7d")

        assert len(filtered) == 1
        assert filtered[0]["overall_score"] == 80
