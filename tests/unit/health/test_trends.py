"""Unit tests for health trend intelligence."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from elastro.health.history import parse_window, sanitize_host
from elastro.health.trends import (
    compute_trends,
    compute_trends_from_records,
    recurring_finding_ids,
)


def _record(
    *,
    score: int,
    hours_ago: float,
    finding_id: str = "disk.watermark.high",
    cluster_name: str = "docker-cluster",
):
    assessed_at = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return {
        "cluster_name": cluster_name,
        "assessed_at": assessed_at.isoformat(),
        "overall_score": score,
        "overall_status": "warn" if score < 90 else "pass",
        "findings": [
            {
                "id": finding_id,
                "status": "warn",
            }
        ],
    }


class TestTrendHelpers:
    def test_parse_window_days(self):
        assert parse_window("7d") == timedelta(days=7)

    def test_sanitize_host_strips_credentials(self):
        assert (
            sanitize_host("https://user:secret@localhost:9200")
            == "https://localhost:9200"
        )

    def test_recurring_findings_requires_majority(self):
        records = [_record(score=70, hours_ago=index) for index in range(4)]
        records.append(
            {
                "findings": [{"id": "disk.watermark.high", "status": "warn"}],
            }
        )
        recurring = recurring_finding_ids(records)
        assert recurring == ["disk.watermark.high"]

    def test_compute_trends_from_records_delta(self):
        records = [
            _record(score=60, hours_ago=48),
            _record(score=70, hours_ago=24),
            _record(score=80, hours_ago=1),
        ]
        report = compute_trends_from_records(
            records,
            cluster_name="docker-cluster",
            window="7d",
        )
        assert report.sample_count == 3
        assert report.score_delta_7d == 20
        assert len(report.points) == 3
        assert report.recurring_findings == ["disk.watermark.high"]

    def test_compute_trends_empty_history_message(self):
        client = MagicMock()
        client.client.search.return_value = {"hits": {"hits": []}}
        report = compute_trends(client, cluster_name="docker-cluster")
        assert report.sample_count == 0
        assert report.message is not None

    def test_compute_trends_queries_history(self):
        client = MagicMock()
        client.client.search.return_value = {
            "hits": {
                "hits": [
                    {"_source": _record(score=72, hours_ago=2)},
                    {"_source": _record(score=68, hours_ago=4)},
                ]
            }
        }
        report = compute_trends(
            client,
            cluster_name="docker-cluster",
            window="7d",
            limit=10,
        )
        assert report.sample_count == 2
        assert report.cluster_name == "docker-cluster"
        body = client.client.search.call_args.kwargs.get("body") or client.client.search.call_args[1].get("body")
        assert body["query"]["bool"]["filter"][0] == {
            "term": {"cluster_name": "docker-cluster"}
        }

    def test_parse_window_invalid_raises(self):
        with pytest.raises(ValueError):
            parse_window("bad")