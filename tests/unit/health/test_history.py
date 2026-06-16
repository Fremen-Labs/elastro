"""Unit tests for assessment history indexing."""

from unittest.mock import MagicMock

from elastro.health.history import (
    assessment_document,
    ensure_index,
    index_assessment,
    query_assessment_history,
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