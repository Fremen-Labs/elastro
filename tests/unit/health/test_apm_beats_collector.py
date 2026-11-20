"""Unit tests for ApmBeatsCollector."""

from unittest.mock import patch

from elastro.core.errors import DocumentError, OperationError
from elastro.health.collectors.apm_beats import ApmBeatsCollector
from elastro.health.collectors.base import CollectContext


def test_collect_happy_path(es_client) -> None:
    ctx = CollectContext(client=es_client)
    with patch("elastro.health.collectors.apm_beats.IndexManager") as idx:
        with patch("elastro.health.collectors.apm_beats.DatastreamManager") as ds:
            with patch("elastro.health.collectors.apm_beats.IlmManager") as ilm:
                with patch(
                    "elastro.health.collectors.apm_beats.DocumentManager"
                ) as docs:
                    with patch(
                        "elastro.health.collectors.apm_beats.HealthManager"
                    ) as health:
                        idx.return_value.list.return_value = [
                            {"index": "traces-apm-default"}
                        ]
                        ds.return_value.list.return_value = [
                            {"name": "traces-apm-default"}
                        ]
                        ilm.return_value.explain_lifecycle.return_value = {
                            "managed": True,
                            "phase": "hot",
                        }
                        docs.return_value.search.return_value = {
                            "hits": {"total": {"value": 3, "relation": "eq"}}
                        }
                        health.return_value.index_stats.return_value = {
                            "indices": {
                                "traces-apm-default": {
                                    "primaries": {
                                        "indexing": {
                                            "index_total": 10,
                                            "index_failed": 0,
                                        }
                                    }
                                }
                            }
                        }
                        result = ApmBeatsCollector().collect(ctx)
    assert result.status == "ok"
    assert result.data["indices"]
    assert result.data["freshness"]["apm"]["doc_count"] == 3
    assert "traces-apm-default" in result.data["ilm"]
    assert result.data["ilm_truncated"] is False
    assert result.data["ilm_explained"] == 1


def test_collect_list_connection_error(es_client) -> None:
    ctx = CollectContext(client=es_client)
    with patch("elastro.health.collectors.apm_beats.IndexManager") as idx:
        with patch("elastro.health.collectors.apm_beats.DatastreamManager"):
            idx.return_value.list.side_effect = OperationError("connection refused")
            result = ApmBeatsCollector().collect(ctx)
    assert result.status == "error"
    assert "connection refused" in (result.error or "")


def test_collect_missing_index_is_empty(es_client) -> None:
    ctx = CollectContext(client=es_client)
    with patch("elastro.health.collectors.apm_beats.IndexManager") as idx:
        with patch("elastro.health.collectors.apm_beats.DatastreamManager") as ds:
            with patch("elastro.health.collectors.apm_beats.IlmManager"):
                with patch(
                    "elastro.health.collectors.apm_beats.DocumentManager"
                ) as docs:
                    with patch(
                        "elastro.health.collectors.apm_beats.HealthManager"
                    ) as health:
                        idx.return_value.list.side_effect = OperationError(
                            "index_not_found_exception"
                        )
                        ds.return_value.list.return_value = []
                        docs.return_value.search.side_effect = DocumentError(
                            "index_not_found"
                        )
                        health.return_value.index_stats.side_effect = OperationError(
                            "index_not_found"
                        )
                        result = ApmBeatsCollector().collect(ctx)
    assert result.status == "ok"
    assert result.data["indices"] == []


def test_collect_error_path(es_client) -> None:
    ctx = CollectContext(client=es_client)
    with patch(
        "elastro.health.collectors.apm_beats.IndexManager",
        side_effect=OperationError("boom"),
    ):
        result = ApmBeatsCollector().collect(ctx)
    assert result.status == "error"
    assert "boom" in (result.error or "")
