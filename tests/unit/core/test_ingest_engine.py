"""
Unit tests for the IngestEngine orchestrator.

Uses mocked Elasticsearch client to test batch processing,
validation integration, and error handling.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from elastro.core.ingest.engine import IngestEngine, IngestResult


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mock ElasticsearchClient."""
    client = MagicMock()
    client.is_connected.return_value = True

    es = MagicMock()
    client.get_client.return_value = es
    client.client = es

    # Default successful bulk response
    es.bulk.return_value = MagicMock(
        body={
            "errors": False,
            "items": [{"index": {"_id": "1", "result": "created", "status": 201}}],
        }
    )

    # Make bulk return dynamic based on operations
    def dynamic_bulk(**kwargs: object) -> MagicMock:
        operations = kwargs.get("operations", [])
        # Count document entries (every other item is a doc, starting at index 1)
        doc_count = len(operations) // 2
        items = [
            {"index": {"_id": str(i), "result": "created", "status": 201}}
            for i in range(doc_count)
        ]
        response = MagicMock()
        response.body = {"errors": False, "items": items}
        response.get = response.body.get
        response.__getitem__ = response.body.__getitem__
        response.__contains__ = response.body.__contains__
        # Make it work with hasattr check
        return response

    es.bulk.side_effect = dynamic_bulk

    return client


class TestIngestResult:
    def test_success_rate(self) -> None:
        result = IngestResult(total_read=100, total_indexed=95, total_failed=5)
        assert result.success_rate == 95.0

    def test_success_rate_zero(self) -> None:
        result = IngestResult()
        assert result.success_rate == 0.0

    def test_to_dict(self) -> None:
        result = IngestResult(total_read=10, total_indexed=8, total_failed=2)
        d = result.to_dict()
        assert d["total_read"] == 10
        assert d["success_rate"] == 80.0


class TestIngestEngine:
    def test_csv_import(self, mock_client: MagicMock, tmp_path: Path) -> None:
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("name,age\nAlice,30\nBob,25\nCharlie,35\n")

        engine = IngestEngine(mock_client)
        result = engine.ingest(str(csv_file), "test-index")

        assert result.total_read == 3
        assert result.total_indexed == 3
        assert result.total_failed == 0

    def test_ndjson_import(self, mock_client: MagicMock, tmp_path: Path) -> None:
        ndjson_file = tmp_path / "test.ndjson"
        ndjson_file.write_text('{"name": "Alice"}\n{"name": "Bob"}\n')

        engine = IngestEngine(mock_client)
        result = engine.ingest(str(ndjson_file), "test-index")

        assert result.total_read == 2
        assert result.total_indexed == 2

    def test_json_array_import(self, mock_client: MagicMock, tmp_path: Path) -> None:
        json_file = tmp_path / "test.json"
        json_file.write_text(json.dumps([{"a": 1}, {"b": 2}]))

        engine = IngestEngine(mock_client)
        result = engine.ingest(str(json_file), "test-index")

        assert result.total_read == 2
        assert result.total_indexed == 2

    def test_batch_size(self, mock_client: MagicMock, tmp_path: Path) -> None:
        csv_file = tmp_path / "test.csv"
        rows = "name\n" + "\n".join(f"user_{i}" for i in range(10))
        csv_file.write_text(rows)

        engine = IngestEngine(mock_client)
        result = engine.ingest(str(csv_file), "test-index", batch_size=3)

        assert result.total_read == 10
        assert result.total_indexed == 10
        # Should have called bulk 4 times (3+3+3+1)
        assert mock_client.get_client().bulk.call_count == 4

    def test_validation_rejects_bad_docs(
        self, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        ndjson_file = tmp_path / "test.ndjson"
        ndjson_file.write_text(
            '{"name": "Alice", "age": 30}\n'
            '{"name": "Bob", "age": "not_a_number"}\n'
            '{"name": "Charlie", "age": 25}\n'
        )

        engine = IngestEngine(mock_client)
        result = engine.ingest(
            str(ndjson_file),
            "test-index",
            validate=True,
            mapping_properties={"age": {"type": "integer"}},
            strict=True,
        )

        assert result.total_read == 3
        assert result.total_indexed == 2
        assert result.total_failed == 1

    def test_dlq_output(self, mock_client: MagicMock, tmp_path: Path) -> None:
        ndjson_file = tmp_path / "test.ndjson"
        ndjson_file.write_text('{"name": "Alice", "age": "bad"}\n')
        dlq_file = tmp_path / "failed.ndjson"

        engine = IngestEngine(mock_client)
        result = engine.ingest(
            str(ndjson_file),
            "test-index",
            validate=True,
            mapping_properties={"age": {"type": "integer"}},
            strict=True,
            dlq_path=str(dlq_file),
        )

        assert result.total_failed == 1
        assert dlq_file.exists()
        dlq_content = dlq_file.read_text().strip()
        assert "bad" in dlq_content

    def test_max_errors_abort(self, mock_client: MagicMock, tmp_path: Path) -> None:
        ndjson_file = tmp_path / "test.ndjson"
        lines = "\n".join(json.dumps({"age": "bad"}) for _ in range(20))
        ndjson_file.write_text(lines)

        engine = IngestEngine(mock_client)
        result = engine.ingest(
            str(ndjson_file),
            "test-index",
            validate=True,
            mapping_properties={"age": {"type": "integer"}},
            strict=True,
            max_errors=5,
        )

        # Should abort after 5 errors
        assert result.total_failed == 5
        assert result.total_read == 5

    def test_pipeline_passed_to_bulk(
        self, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("name\nAlice\n")

        engine = IngestEngine(mock_client)
        engine.ingest(str(csv_file), "test-index", pipeline="my-pipeline")

        call_args = mock_client.get_client().bulk.call_args
        operations = call_args.kwargs.get("operations", [])
        # First item should have pipeline in the action
        assert operations[0]["index"]["pipeline"] == "my-pipeline"

    def test_id_field_extracted(self, mock_client: MagicMock, tmp_path: Path) -> None:
        ndjson_file = tmp_path / "test.ndjson"
        ndjson_file.write_text('{"_id": "custom-123", "name": "Alice"}\n')

        engine = IngestEngine(mock_client)
        engine.ingest(str(ndjson_file), "test-index")

        call_args = mock_client.get_client().bulk.call_args
        operations = call_args.kwargs.get("operations", [])
        assert operations[0]["index"]["_id"] == "custom-123"
        # _id should be stripped from the document body
        assert "_id" not in operations[1]
