"""Unit tests for agent payload models and index-name constants."""

from datetime import datetime, timezone

from elastro.agent.models import (
    AGENT_SEMANTIC_MEMORY,
    AGENT_TELEMETRY_DEEP,
    FLOW_TOOLS,
    FREMEN_CODEBASE_RAG,
    MemoryNote,
    MlDetector,
    MlJobConfig,
    TelemetryDocument,
    dump_payload,
    memory_search_body,
    tactical_prune_query,
    wake_search_body,
    wake_search_fields,
)


def test_index_name_constants_are_stable() -> None:
    assert AGENT_SEMANTIC_MEMORY == "agent_semantic_memory"
    assert AGENT_TELEMETRY_DEEP == "agent_telemetry_deep"
    assert FLOW_TOOLS == "flow_tools"
    assert FREMEN_CODEBASE_RAG == "fremen_codebase_rag"


def test_memory_note_round_trip() -> None:
    note = MemoryNote(
        timestamp="2026-11-19T12:00:00Z",
        note_type="tactical",
        subject="handoff",
        content="rotate the alias",
        tags=["ops"],
    )
    payload = dump_payload(note)
    assert payload["note_type"] == "tactical"
    assert payload["tags"] == ["ops"]
    assert MemoryNote.model_validate(payload).subject == "handoff"


def test_telemetry_document_dump_matches_ingest_shape() -> None:
    doc = TelemetryDocument(
        timestamp="2026-11-19T12:00:00Z",
        workload_reference="session-1",
        t_elastro_query_ms=15,
        token_count_query={"input_tokens": 9, "output_tokens": 3},
    )
    payload = dump_payload(doc)
    parsed = TelemetryDocument.model_validate(payload)
    assert parsed.workload_reference == "session-1"
    assert parsed.t_elastro_query_ms == 15
    assert parsed.token_count_query.input_tokens == 9
    assert parsed.token_count_query.output_tokens == 3
    assert "bounded_layer" not in payload["token_count_query"]


def test_tactical_prune_query_cutoff() -> None:
    now = datetime(2026, 11, 19, 12, 0, 0, tzinfo=timezone.utc)
    body = tactical_prune_query(days=7, now=now)
    assert body["query"]["bool"]["must"][0] == {"term": {"note_type": "tactical"}}
    assert body["query"]["bool"]["must"][1]["range"]["timestamp"]["lt"] == (
        "2026-11-12T12:00:00Z"
    )


def test_wake_fields_fremen_special_case() -> None:
    assert wake_search_fields(FREMEN_CODEBASE_RAG) == [
        "file_path^3",
        "content",
        "chunk_name^2",
    ]
    assert wake_search_fields(AGENT_SEMANTIC_MEMORY) == [
        "subject^3",
        "content",
        "tags",
    ]
    rag_body = wake_search_body("find parser", index=FREMEN_CODEBASE_RAG, k=3)
    fields = rag_body["query"]["function_score"]["query"]["bool"]["must"][0][
        "multi_match"
    ]["fields"]
    assert fields == ["file_path^3", "content", "chunk_name^2"]
    assert rag_body["size"] == 3


def test_memory_search_body_filters_note_type() -> None:
    body = memory_search_body("alias", note_type="strategic", size=5)
    assert body["size"] == 5
    assert body["query"]["bool"]["filter"] == [{"term": {"note_type": "strategic"}}]


def test_ml_job_count_omits_field_name() -> None:
    detector = MlDetector(function="count")
    payload = dump_payload(
        MlJobConfig(
            description="count job",
            analysis_config={"bucket_span": "15m", "detectors": [detector]},
            data_description={"time_field": "@timestamp"},
        )
    )
    assert "field_name" not in payload["analysis_config"]["detectors"][0]
