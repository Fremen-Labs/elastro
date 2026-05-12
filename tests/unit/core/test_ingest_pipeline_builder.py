"""
Unit tests for the IngestPipelineBuilder.

Tests the fluent builder API, processor chaining, on_failure routing,
and the final build() output structure.
"""

import json
from unittest.mock import MagicMock

from elastro.core.ingest.pipeline_builder import IngestPipelineBuilder


class TestBuilderMetadata:
    def test_pipeline_id(self) -> None:
        builder = IngestPipelineBuilder("test-pipe")
        assert builder.pipeline_id == "test-pipe"

    def test_description(self) -> None:
        body = IngestPipelineBuilder("p").description("Parse web logs").build()
        assert body["description"] == "Parse web logs"

    def test_empty_pipeline(self) -> None:
        body = IngestPipelineBuilder("p").build()
        assert body["processors"] == []
        assert "on_failure" not in body


class TestProcessors:
    def test_grok(self) -> None:
        body = (
            IngestPipelineBuilder("p").grok("message", ["%{COMBINEDAPACHELOG}"]).build()
        )
        proc = body["processors"][0]["grok"]
        assert proc["field"] == "message"
        assert proc["patterns"] == ["%{COMBINEDAPACHELOG}"]

    def test_grok_ignore_missing(self) -> None:
        body = (
            IngestPipelineBuilder("p")
            .grok("msg", ["%{IP:ip}"], ignore_missing=True)
            .build()
        )
        assert body["processors"][0]["grok"]["ignore_missing"] is True

    def test_date(self) -> None:
        body = (
            IngestPipelineBuilder("p")
            .date("ts", ["ISO8601"], target_field="event.time")
            .build()
        )
        proc = body["processors"][0]["date"]
        assert proc["field"] == "ts"
        assert proc["formats"] == ["ISO8601"]
        assert proc["target_field"] == "event.time"

    def test_date_with_timezone(self) -> None:
        body = (
            IngestPipelineBuilder("p").date("ts", ["ISO8601"], timezone="UTC").build()
        )
        assert body["processors"][0]["date"]["timezone"] == "UTC"

    def test_rename(self) -> None:
        body = IngestPipelineBuilder("p").rename("old_field", "new_field").build()
        proc = body["processors"][0]["rename"]
        assert proc["field"] == "old_field"
        assert proc["target_field"] == "new_field"

    def test_remove(self) -> None:
        body = (
            IngestPipelineBuilder("p").remove("temp_field", ignore_missing=True).build()
        )
        proc = body["processors"][0]["remove"]
        assert proc["field"] == "temp_field"
        assert proc["ignore_missing"] is True

    def test_convert(self) -> None:
        body = IngestPipelineBuilder("p").convert("status", "integer").build()
        proc = body["processors"][0]["convert"]
        assert proc["field"] == "status"
        assert proc["type"] == "integer"

    def test_convert_with_target(self) -> None:
        body = (
            IngestPipelineBuilder("p")
            .convert("bytes", "long", target_field="bytes_long")
            .build()
        )
        assert body["processors"][0]["convert"]["target_field"] == "bytes_long"

    def test_lowercase(self) -> None:
        body = IngestPipelineBuilder("p").lowercase("method").build()
        assert body["processors"][0]["lowercase"]["field"] == "method"

    def test_uppercase(self) -> None:
        body = IngestPipelineBuilder("p").uppercase("code").build()
        assert body["processors"][0]["uppercase"]["field"] == "code"

    def test_set_field(self) -> None:
        body = IngestPipelineBuilder("p").set_field("env", "production").build()
        proc = body["processors"][0]["set"]
        assert proc["field"] == "env"
        assert proc["value"] == "production"

    def test_gsub(self) -> None:
        body = IngestPipelineBuilder("p").gsub("message", r"\s+", " ").build()
        proc = body["processors"][0]["gsub"]
        assert proc["field"] == "message"
        assert proc["pattern"] == r"\s+"
        assert proc["replacement"] == " "

    def test_geoip(self) -> None:
        body = IngestPipelineBuilder("p").geoip("client_ip").build()
        proc = body["processors"][0]["geoip"]
        assert proc["field"] == "client_ip"
        assert proc["ignore_missing"] is True

    def test_redact(self) -> None:
        body = (
            IngestPipelineBuilder("p")
            .redact("message", ["%{EMAILADDRESS:REDACTED}"])
            .build()
        )
        proc = body["processors"][0]["redact"]
        assert proc["field"] == "message"
        assert len(proc["patterns"]) == 1

    def test_dissect(self) -> None:
        body = (
            IngestPipelineBuilder("p").dissect("log", "%{ts} %{level} %{msg}").build()
        )
        proc = body["processors"][0]["dissect"]
        assert proc["field"] == "log"
        assert proc["pattern"] == "%{ts} %{level} %{msg}"

    def test_script(self) -> None:
        body = IngestPipelineBuilder("p").script("ctx.total = ctx.a + ctx.b").build()
        proc = body["processors"][0]["script"]
        assert proc["lang"] == "painless"
        assert "ctx.total" in proc["source"]

    def test_inference(self) -> None:
        body = (
            IngestPipelineBuilder("p")
            .inference(
                "my-model",
                field_map={"message": "text"},
                target_field="ml",
            )
            .build()
        )
        proc = body["processors"][0]["inference"]
        assert proc["model_id"] == "my-model"
        assert proc["field_map"] == {"message": "text"}
        assert proc["target_field"] == "ml"

    def test_custom(self) -> None:
        body = (
            IngestPipelineBuilder("p")
            .custom({"community_id": {"source_ip": "src"}})
            .build()
        )
        assert body["processors"][0] == {"community_id": {"source_ip": "src"}}


class TestProcessorCount:
    def test_count(self) -> None:
        builder = (
            IngestPipelineBuilder("p")
            .grok("msg", ["%{IP:ip}"])
            .date("ts", ["ISO8601"])
            .rename("a", "b")
        )
        assert builder.processor_count == 3


class TestChaining:
    def test_fluent_chain(self) -> None:
        """All methods return self for chaining."""
        body = (
            IngestPipelineBuilder("web-logs")
            .description("Parse and enrich web access logs")
            .grok("message", ["%{COMBINEDAPACHELOG}"])
            .date("timestamp", ["dd/MMM/yyyy:HH:mm:ss Z"])
            .geoip("clientip")
            .convert("response", "integer")
            .rename("clientip", "client.ip")
            .remove("message")
            .on_failure("failed-web-logs")
            .build()
        )

        assert len(body["processors"]) == 6
        assert body["on_failure"] is not None
        assert body["description"] == "Parse and enrich web access logs"

        # Verify processor order is preserved
        proc_types = [list(p.keys())[0] for p in body["processors"]]
        assert proc_types == ["grok", "date", "geoip", "convert", "rename", "remove"]


class TestOnFailure:
    def test_on_failure_structure(self) -> None:
        body = IngestPipelineBuilder("p").on_failure("dead-letters").build()
        assert "on_failure" in body
        assert len(body["on_failure"]) == 3

        # First step routes to DLQ index
        first = body["on_failure"][0]
        assert first["set"]["field"] == "_index"
        assert first["set"]["value"] == "dead-letters"

    def test_no_on_failure_by_default(self) -> None:
        body = IngestPipelineBuilder("p").grok("msg", ["."]).build()
        assert "on_failure" not in body


class TestDeploy:
    def test_deploy_calls_put_pipeline(self) -> None:
        mock_client = MagicMock()
        mock_es = MagicMock()
        mock_client.get_client.return_value = mock_es

        builder = (
            IngestPipelineBuilder("test-pipe")
            .description("test")
            .grok("msg", ["%{IP:ip}"])
        )
        builder.deploy(mock_client)

        mock_es.ingest.put_pipeline.assert_called_once()
        call_kwargs = mock_es.ingest.put_pipeline.call_args
        assert call_kwargs[1]["id"] == "test-pipe"

    def test_deploy_with_override_id(self) -> None:
        mock_client = MagicMock()
        mock_es = MagicMock()
        mock_client.get_client.return_value = mock_es

        builder = IngestPipelineBuilder("original-id")
        builder.deploy(mock_client, pipeline_id="override-id")

        call_kwargs = mock_es.ingest.put_pipeline.call_args
        assert call_kwargs[1]["id"] == "override-id"


class TestBuildJSON:
    def test_json_serializable(self) -> None:
        """Build output must be JSON-serializable."""
        body = (
            IngestPipelineBuilder("p")
            .grok("msg", ["%{IP:ip}"])
            .date("ts", ["ISO8601"])
            .on_failure("dlq")
            .build()
        )
        # Should not raise
        json_str = json.dumps(body)
        assert json_str is not None
