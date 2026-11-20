"""Unit tests for CoverageValidator."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from elastro.core.errors import (
    DocumentError,
    ElasticIndexError,
    OperationError,
    ValidationError,
)
from elastro.coverage.validators import (
    DEFAULT_APM_PATTERNS,
    DEFAULT_BEATS_PATTERNS,
    CoverageValidator,
)


def _search_hits(
    *,
    count: int = 150,
    latest_ms: float | None = None,
    service_docs: int = 150,
    host_docs: int = 140,
    cardinality: int = 3,
) -> dict:
    if latest_ms is None:
        latest_ms = datetime.now(timezone.utc).timestamp() * 1000
    return {
        "hits": {"total": {"value": count, "relation": "eq"}, "hits": []},
        "aggregations": {
            "latest": {
                "value": latest_ms,
                "value_as_string": "2026-11-20T00:00:00.000Z",
            },
            "fresh": {"doc_count": count},
            "in_window": {
                "doc_count": count,
                "has_service_name": {"doc_count": service_docs},
                "has_host_name": {"doc_count": host_docs},
                "service_cardinality": {"value": cardinality},
            },
        },
    }


def test_check_pattern_happy_path(es_client) -> None:
    with patch("elastro.coverage.validators.IndexManager") as idx:
        with patch("elastro.coverage.validators.DatastreamManager") as ds:
            with patch("elastro.coverage.validators.DocumentManager") as docs:
                idx.return_value.list.return_value = [{"index": "traces-apm-default"}]
                ds.return_value.list.return_value = [{"name": "traces-apm-default"}]
                docs.return_value.search.return_value = _search_hits()
                report = CoverageValidator(es_client).check_pattern(
                    "traces-apm*", min_docs=100, max_age="15m"
                )
    assert report.passed is True
    assert report.doc_count == 150
    names = {item.name for item in report.checks}
    assert names >= {"streams_present", "doc_count", "freshness", "field_presence"}


def test_check_pattern_missing_streams_fails(es_client) -> None:
    with patch("elastro.coverage.validators.IndexManager") as idx:
        with patch("elastro.coverage.validators.DatastreamManager") as ds:
            idx.return_value.list.return_value = []
            ds.return_value.list.return_value = []
            report = CoverageValidator(es_client).check_pattern("traces-apm*")
    assert report.passed is False
    assert report.checks[0].name == "streams_present"
    assert report.checks[0].passed is False


def test_check_service_requires_name(es_client) -> None:
    with pytest.raises(ValidationError, match="service name"):
        CoverageValidator(es_client).check_service("  ")


def test_check_service_happy_path(es_client) -> None:
    with patch("elastro.coverage.validators.IndexManager") as idx:
        with patch("elastro.coverage.validators.DatastreamManager") as ds:
            with patch("elastro.coverage.validators.DocumentManager") as docs:
                idx.return_value.list.return_value = [{"index": "traces-apm-default"}]
                ds.return_value.list.return_value = []
                docs.return_value.search.return_value = _search_hits()
                report = CoverageValidator(es_client).check_service(
                    "checkout-service", window="15m"
                )
    assert report.passed is True
    assert report.target == "service:checkout-service"
    docs.return_value.search.assert_called_once()
    query = docs.return_value.search.call_args.kwargs["query"]
    filters = query["bool"]["filter"]
    assert {"term": {"service.name": "checkout-service"}} in filters


def test_check_pattern_search_error_is_operation_error(es_client) -> None:
    with patch("elastro.coverage.validators.IndexManager") as idx:
        with patch("elastro.coverage.validators.DatastreamManager") as ds:
            with patch("elastro.coverage.validators.DocumentManager") as docs:
                idx.return_value.list.return_value = [{"index": "traces-apm-default"}]
                ds.return_value.list.return_value = []
                docs.return_value.search.side_effect = DocumentError("timeout")
                with pytest.raises(OperationError, match="Coverage search failed"):
                    CoverageValidator(es_client).check_pattern("traces-apm*")


def test_check_all_aggregates_patterns(es_client) -> None:
    with patch("elastro.coverage.validators.IndexManager") as idx:
        with patch("elastro.coverage.validators.DatastreamManager") as ds:
            with patch("elastro.coverage.validators.DocumentManager") as docs:
                idx.return_value.list.return_value = []
                ds.return_value.list.return_value = []
                report = CoverageValidator(es_client).check_all()
    assert report.target == "all"
    assert report.passed is False
    assert len(report.checks) >= 5
    docs.return_value.search.assert_not_called()


def test_list_connection_error_is_operation_error(es_client) -> None:
    with patch("elastro.coverage.validators.IndexManager") as idx:
        with patch("elastro.coverage.validators.DatastreamManager") as ds:
            idx.return_value.list.side_effect = ElasticIndexError("connection refused")
            ds.return_value.list.return_value = []
            with pytest.raises(OperationError, match="Failed to list indices"):
                CoverageValidator(es_client).check_pattern("traces-apm*")


def test_list_missing_index_is_empty_not_error(es_client) -> None:
    with patch("elastro.coverage.validators.IndexManager") as idx:
        with patch("elastro.coverage.validators.DatastreamManager") as ds:
            idx.return_value.list.side_effect = ElasticIndexError(
                "index_not_found_exception"
            )
            ds.return_value.list.return_value = []
            report = CoverageValidator(es_client).check_pattern("traces-apm*")
    assert report.passed is False
    assert report.checks[0].name == "streams_present"


def test_search_missing_index_has_single_doc_count_row(es_client) -> None:
    with patch("elastro.coverage.validators.IndexManager") as idx:
        with patch("elastro.coverage.validators.DatastreamManager") as ds:
            with patch("elastro.coverage.validators.DocumentManager") as docs:
                idx.return_value.list.return_value = [{"index": "traces-apm-default"}]
                ds.return_value.list.return_value = []
                docs.return_value.search.side_effect = DocumentError(
                    "index_not_found_exception"
                )
                report = CoverageValidator(es_client).check_pattern("traces-apm*")
    doc_rows = [item for item in report.checks if item.name == "doc_count"]
    assert len(doc_rows) == 1
    assert doc_rows[0].passed is False


def test_search_uses_es_now_freshness_agg(es_client) -> None:
    with patch("elastro.coverage.validators.IndexManager") as idx:
        with patch("elastro.coverage.validators.DatastreamManager") as ds:
            with patch("elastro.coverage.validators.DocumentManager") as docs:
                idx.return_value.list.return_value = [{"index": "traces-apm-default"}]
                ds.return_value.list.return_value = []
                docs.return_value.search.return_value = _search_hits()
                CoverageValidator(es_client).check_pattern(
                    "traces-apm*", window="15m", max_age="5m"
                )
    options = docs.return_value.search.call_args.kwargs["options"]
    fresh = options["aggs"]["fresh"]["filter"]["range"]["@timestamp"]["gte"]
    assert fresh == "now-5m"


def test_beats_patterns_include_classic_and_datastream() -> None:
    assert DEFAULT_BEATS_PATTERNS == (
        "filebeat-*",
        "metricbeat-*",
        "logs-filebeat*",
        "metrics-metricbeat*",
    )
    from elastro.health.collectors.apm_beats import (
        _BEATS_SEARCH,
        _INDEX_PATTERNS,
    )

    assert _INDEX_PATTERNS == DEFAULT_APM_PATTERNS + DEFAULT_BEATS_PATTERNS
    assert _BEATS_SEARCH == ",".join(DEFAULT_BEATS_PATTERNS)


def test_check_all_is_full_gate(es_client) -> None:
    with patch("elastro.coverage.validators.IndexManager") as idx:
        with patch("elastro.coverage.validators.DatastreamManager") as ds:
            with patch("elastro.coverage.validators.DocumentManager") as docs:
                idx.return_value.list.side_effect = lambda pattern: (
                    [{"index": "traces-apm-default"}]
                    if pattern.startswith("traces-apm")
                    else []
                )
                ds.return_value.list.return_value = []
                docs.return_value.search.return_value = _search_hits()
                report = CoverageValidator(es_client).check_all()
    assert report.passed is False
    assert report.target == "all"


def test_invalid_window_raises_validation_error(es_client) -> None:
    with pytest.raises(ValidationError, match="Invalid window"):
        CoverageValidator(es_client).check_pattern("traces-apm*", window="15x")


def test_check_service_zero_docs_fails_streams_present(es_client) -> None:
    with patch("elastro.coverage.validators.IndexManager") as idx:
        with patch("elastro.coverage.validators.DatastreamManager") as ds:
            with patch("elastro.coverage.validators.DocumentManager") as docs:
                idx.return_value.list.return_value = [{"index": "traces-apm-default"}]
                ds.return_value.list.return_value = [{"name": "traces-apm-default"}]
                docs.return_value.search.return_value = _search_hits(
                    count=0, service_docs=0, host_docs=0
                )
                report = CoverageValidator(es_client).check_service("elasticsearch")
    streams = next(item for item in report.checks if item.name == "streams_present")
    assert streams.passed is False
    assert report.passed is False
    assert "elasticsearch" in streams.summary
    assert streams.metadata.get("resources")


def test_check_pattern_zero_docs_keeps_streams_present(es_client) -> None:
    with patch("elastro.coverage.validators.IndexManager") as idx:
        with patch("elastro.coverage.validators.DatastreamManager") as ds:
            with patch("elastro.coverage.validators.DocumentManager") as docs:
                idx.return_value.list.return_value = [{"index": "filebeat-8.15.0"}]
                ds.return_value.list.return_value = []
                docs.return_value.search.return_value = _search_hits(
                    count=0, service_docs=0, host_docs=0
                )
                report = CoverageValidator(es_client).check_pattern("filebeat-*")
    streams = next(item for item in report.checks if item.name == "streams_present")
    assert streams.passed is True
    assert report.passed is False


def test_check_service_window_agg_includes_service_term(es_client) -> None:
    with patch("elastro.coverage.validators.IndexManager") as idx:
        with patch("elastro.coverage.validators.DatastreamManager") as ds:
            with patch("elastro.coverage.validators.DocumentManager") as docs:
                idx.return_value.list.return_value = [{"index": "traces-apm-default"}]
                ds.return_value.list.return_value = []
                docs.return_value.search.return_value = _search_hits()
                CoverageValidator(es_client).check_service(
                    "checkout-service", window="15m"
                )
    options = docs.return_value.search.call_args.kwargs["options"]
    filters = options["aggs"]["in_window"]["filter"]["bool"]["filter"]
    assert {"range": {"@timestamp": {"gte": "now-15m"}}} in filters
    assert {"term": {"service.name": "checkout-service"}} in filters


def test_field_presence_aggs_are_window_scoped(es_client) -> None:
    with patch("elastro.coverage.validators.IndexManager") as idx:
        with patch("elastro.coverage.validators.DatastreamManager") as ds:
            with patch("elastro.coverage.validators.DocumentManager") as docs:
                idx.return_value.list.return_value = [{"index": "filebeat-8.15.0"}]
                ds.return_value.list.return_value = []
                docs.return_value.search.return_value = _search_hits()
                CoverageValidator(es_client).check_pattern("filebeat-*", window="15m")
    options = docs.return_value.search.call_args.kwargs["options"]
    in_window = options["aggs"]["in_window"]
    assert in_window["filter"]["bool"]["filter"][0]["range"]["@timestamp"]["gte"] == (
        "now-15m"
    )
    assert "has_host_name" in in_window["aggs"]
    assert "has_service_name" in in_window["aggs"]
    assert "service_cardinality" in in_window["aggs"]


def test_field_presence_ignores_unscoped_host_count(es_client) -> None:
    body = _search_hits(count=2, service_docs=2, host_docs=2)
    body["aggregations"]["has_host_name"] = {"doc_count": 35757}
    with patch("elastro.coverage.validators.IndexManager") as idx:
        with patch("elastro.coverage.validators.DatastreamManager") as ds:
            with patch("elastro.coverage.validators.DocumentManager") as docs:
                idx.return_value.list.return_value = [{"index": "filebeat-8.15.0"}]
                ds.return_value.list.return_value = []
                docs.return_value.search.return_value = body
                report = CoverageValidator(es_client).check_pattern("filebeat-*")
    field = next(item for item in report.checks if item.name == "field_presence")
    assert "35757" not in field.summary
    assert field.metadata["host.name"] == 2
    assert field.metadata["host.name"] <= report.doc_count


def test_field_presence_uses_in_window_count_when_hits_capped(es_client) -> None:
    body = _search_hits(count=2, service_docs=10, host_docs=35757)
    body["hits"]["total"] = {"value": 2, "relation": "gte"}
    body["aggregations"]["in_window"]["doc_count"] = 35757
    body["aggregations"]["has_host_name"] = {"doc_count": 35757}
    with patch("elastro.coverage.validators.IndexManager") as idx:
        with patch("elastro.coverage.validators.DatastreamManager") as ds:
            with patch("elastro.coverage.validators.DocumentManager") as docs:
                idx.return_value.list.return_value = [{"index": "filebeat-8.15.0"}]
                ds.return_value.list.return_value = []
                docs.return_value.search.return_value = body
                report = CoverageValidator(es_client).check_pattern("filebeat-*")
    field = next(item for item in report.checks if item.name == "field_presence")
    assert "of 2 docs" not in field.summary
    assert field.doc_count == 35757
    assert report.doc_count == 35757
    assert field.metadata["host.name"] == 35757
    assert field.metadata["host.name"] <= field.doc_count
    assert "host.name=35757 of 35757 docs" in field.summary


def test_field_presence_incomplete_in_window_does_not_use_unscoped(
    es_client,
) -> None:
    body = _search_hits(count=2, service_docs=2, host_docs=2)
    body["aggregations"]["has_host_name"] = {"doc_count": 35757}
    body["aggregations"]["in_window"] = {"doc_count": 35757}
    with patch("elastro.coverage.validators.IndexManager") as idx:
        with patch("elastro.coverage.validators.DatastreamManager") as ds:
            with patch("elastro.coverage.validators.DocumentManager") as docs:
                idx.return_value.list.return_value = [{"index": "filebeat-8.15.0"}]
                ds.return_value.list.return_value = []
                docs.return_value.search.return_value = body
                report = CoverageValidator(es_client).check_pattern("filebeat-*")
    field = next(item for item in report.checks if item.name == "field_presence")
    assert field.metadata["host.name"] == 0
    assert "host.name=35757" not in field.summary
    assert report.doc_count == 35757
