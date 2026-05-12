"""
Integration-style tests for the Ingest Engine.

Tests edge cases with real-world data patterns: malformed CSV/JSON,
nested objects, large-file ijson path, coercion failures, and the
progress callback API.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, call

import pytest

from elastro.core.ingest.engine import IngestEngine, IngestResult
from elastro.core.ingest.readers import (
    CSVReader,
    NDJSONReader,
    JSONArrayReader,
    read_source,
)
from elastro.core.ingest.validators import (
    SchemaValidator,
    infer_mapping,
    profile_data,
    _infer_field_type,
)

# ---------------------------------------------------------------------------
# Recursive / Nested inference
# ---------------------------------------------------------------------------


class TestNestedInference:
    def test_object_field_detected(self) -> None:
        assert _infer_field_type([{"a": 1}, {"a": 2}]) == "object"

    def test_nested_field_detected(self) -> None:
        """Array of dicts should be 'nested', not 'object'."""
        values = [
            [{"x": 1}, {"x": 2}],
            [{"x": 3}],
        ]
        assert _infer_field_type(values) == "nested"

    def test_scalar_array_inferred(self) -> None:
        """Array of ints should infer the element type."""
        values = [[1, 2, 3], [4, 5]]
        assert _infer_field_type(values) == "integer"

    def test_recursive_mapping_object(self) -> None:
        docs = iter(
            [
                {"user": {"name": "Alice", "age": 30}},
                {"user": {"name": "Bob", "age": 25}},
            ]
        )
        mapping = infer_mapping(docs, sample_size=10)
        props = mapping["mappings"]["properties"]

        assert props["user"]["type"] == "object"
        assert "properties" in props["user"]
        assert props["user"]["properties"]["name"]["type"] == "keyword"
        assert props["user"]["properties"]["age"]["type"] == "integer"

    def test_recursive_mapping_nested(self) -> None:
        docs = iter(
            [
                {
                    "tags": [
                        {"key": "env", "value": "prod"},
                        {"key": "team", "value": "eng"},
                    ]
                },
                {"tags": [{"key": "region", "value": "us-east"}]},
            ]
        )
        mapping = infer_mapping(docs, sample_size=10)
        props = mapping["mappings"]["properties"]

        assert props["tags"]["type"] == "nested"
        assert "properties" in props["tags"]
        assert props["tags"]["properties"]["key"]["type"] == "keyword"
        assert props["tags"]["properties"]["value"]["type"] == "keyword"

    def test_deeply_nested_object(self) -> None:
        docs = iter(
            [
                {"meta": {"geo": {"lat": 40.7, "lon": -74.0}}},
            ]
        )
        mapping = infer_mapping(docs, sample_size=10)
        geo = mapping["mappings"]["properties"]["meta"]["properties"]["geo"]
        assert geo["type"] == "object"
        assert geo["properties"]["lat"]["type"] == "double"


# ---------------------------------------------------------------------------
# Malformed CSV edge cases
# ---------------------------------------------------------------------------


class TestMalformedCSV:
    def test_csv_with_empty_cells(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "sparse.csv"
        csv_file.write_text("name,email,age\nAlice,,30\n,bob@test.com,\n")

        docs = list(CSVReader(csv_file).read())
        assert len(docs) == 2
        assert docs[0]["email"] == ""
        assert docs[1]["name"] == ""

    def test_csv_with_extra_columns(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "extra.csv"
        csv_file.write_text("name,age\nAlice,30,extra_value\n")

        docs = list(CSVReader(csv_file).read())
        assert len(docs) == 1
        # csv.DictReader puts extra values under None key
        assert docs[0]["name"] == "Alice"

    def test_csv_with_quoted_commas(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "quoted.csv"
        csv_file.write_text('name,address\nAlice,"123 Main St, Suite 4"\n')

        docs = list(CSVReader(csv_file).read())
        assert docs[0]["address"] == "123 Main St, Suite 4"

    def test_csv_unicode(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "unicode.csv"
        csv_file.write_text(
            "name,city\nJürgen,München\nRené,Montréal\n", encoding="utf-8"
        )

        docs = list(CSVReader(csv_file).read())
        assert docs[0]["name"] == "Jürgen"
        assert docs[1]["city"] == "Montréal"


# ---------------------------------------------------------------------------
# Malformed JSON edge cases
# ---------------------------------------------------------------------------


class TestMalformedJSON:
    def test_ndjson_with_non_objects(self, tmp_path: Path) -> None:
        """Non-object lines (arrays, primitives) should be skipped."""
        ndjson_file = tmp_path / "mixed.ndjson"
        ndjson_file.write_text('{"a": 1}\n[1,2,3]\n"just a string"\n{"b": 2}\n')
        docs = list(NDJSONReader(ndjson_file).read())
        assert len(docs) == 2  # Only the two objects

    def test_json_array_with_mixed_types(self, tmp_path: Path) -> None:
        json_file = tmp_path / "mixed.json"
        json_file.write_text(json.dumps([{"a": 1}, "string", {"b": 2}, 42]))

        docs = list(JSONArrayReader(json_file).read())
        assert len(docs) == 2  # Only dicts

    def test_json_nested_documents(self, tmp_path: Path) -> None:
        """Ensure nested objects are preserved through the reader."""
        data = [
            {
                "user": {"name": "Alice", "address": {"city": "NYC", "zip": "10001"}},
                "tags": [{"key": "env", "value": "prod"}],
            }
        ]
        json_file = tmp_path / "nested.json"
        json_file.write_text(json.dumps(data))

        docs = list(JSONArrayReader(json_file).read())
        assert docs[0]["user"]["address"]["city"] == "NYC"
        assert docs[0]["tags"][0]["key"] == "env"


# ---------------------------------------------------------------------------
# Large JSON (ijson path)
# ---------------------------------------------------------------------------


class TestLargeJSON:
    def test_large_json_falls_back_without_ijson(self, tmp_path: Path) -> None:
        """Without ijson installed, large files should still load via stdlib fallback."""
        json_file = tmp_path / "big.json"
        # Create a file that would normally trigger streaming
        # (won't actually be 50MB, but we can test the threshold logic)
        data = [{"id": i, "value": f"item_{i}"} for i in range(100)]
        json_file.write_text(json.dumps(data))

        reader = JSONArrayReader(json_file)
        # Force the threshold to 0 to trigger streaming path
        reader.MAX_SIMPLE_BYTES = 0

        docs = list(reader.read())
        # Should succeed via fallback or ijson
        assert len(docs) == 100


# ---------------------------------------------------------------------------
# Coercion edge cases
# ---------------------------------------------------------------------------


class TestCoercionEdgeCases:
    def test_coerce_empty_string_integer(self) -> None:
        """Empty string should fail coercion to integer."""
        mapping = {"count": {"type": "integer"}}
        validator = SchemaValidator(mapping)

        is_valid, doc, errors = validator.validate({"count": ""})
        assert is_valid is False
        assert any("coerce" in e for e in errors)

    def test_coerce_float_string_to_int(self) -> None:
        """'3.14' should fail strict int coercion."""
        mapping = {"count": {"type": "integer"}}
        validator = SchemaValidator(mapping, strict=True)

        is_valid, _, errors = validator.validate({"count": "3.14"})
        assert is_valid is False

    def test_coerce_boolean_edge_cases(self) -> None:
        mapping = {"flag": {"type": "boolean"}}
        validator = SchemaValidator(mapping)

        _, doc, _ = validator.validate({"flag": "yes"})
        assert doc["flag"] is True

        _, doc, _ = validator.validate({"flag": "0"})
        assert doc["flag"] is False

        _, doc, _ = validator.validate({"flag": "no"})
        assert doc["flag"] is False

    def test_nested_values_not_coerced(self) -> None:
        """Dicts and lists should pass through without coercion attempts."""
        mapping = {"meta": {"type": "integer"}}
        validator = SchemaValidator(mapping)

        is_valid, doc, errors = validator.validate({"meta": {"nested": "value"}})
        assert is_valid is True  # Skipped because value is a dict
        assert doc["meta"] == {"nested": "value"}


# ---------------------------------------------------------------------------
# Progress callback
# ---------------------------------------------------------------------------


class TestProgressCallback:
    def test_callback_invoked(self, tmp_path: Path) -> None:
        """progress_callback should be called after each batch flush."""
        csv_file = tmp_path / "test.csv"
        rows = "name\n" + "\n".join(f"user_{i}" for i in range(10))
        csv_file.write_text(rows)

        mock_client = MagicMock()
        mock_client.is_connected.return_value = True
        es = MagicMock()
        mock_client.get_client.return_value = es
        mock_client.client = es

        def dynamic_bulk(**kwargs: object) -> MagicMock:
            operations = kwargs.get("operations", [])
            doc_count = len(operations) // 2
            items = [
                {"index": {"_id": str(i), "result": "created", "status": 201}}
                for i in range(doc_count)
            ]
            resp = MagicMock()
            resp.body = {"errors": False, "items": items}
            resp.get = resp.body.get
            resp.__getitem__ = resp.body.__getitem__
            resp.__contains__ = resp.body.__contains__
            return resp

        es.bulk.side_effect = dynamic_bulk

        callback = MagicMock()
        engine = IngestEngine(mock_client)
        result = engine.ingest(
            str(csv_file), "test-index", batch_size=3, progress_callback=callback
        )

        # With 10 docs and batch_size=3, we get 4 flushes (3+3+3+1)
        assert callback.call_count == 4
        # Last call should have total_read=10, total_indexed=10, total_failed=0
        last_call = callback.call_args_list[-1]
        assert last_call == call(10, 10, 0)


# ---------------------------------------------------------------------------
# DLQ captures bulk errors
# ---------------------------------------------------------------------------


class TestDLQBulkErrors:
    def test_bulk_errors_written_to_dlq(self, tmp_path: Path) -> None:
        """Bulk API errors should be captured in the DLQ alongside validation errors."""
        ndjson_file = tmp_path / "test.ndjson"
        ndjson_file.write_text('{"name": "Alice"}\n{"name": "Bob"}\n')
        dlq_file = tmp_path / "dlq.ndjson"

        mock_client = MagicMock()
        mock_client.is_connected.return_value = True
        es = MagicMock()
        mock_client.get_client.return_value = es
        mock_client.client = es

        # Simulate one success + one bulk error
        resp = MagicMock()
        resp.body = {
            "errors": True,
            "items": [
                {"index": {"_id": "1", "result": "created", "status": 201}},
                {
                    "index": {
                        "_id": "2",
                        "status": 400,
                        "error": {
                            "type": "mapper_parsing_exception",
                            "reason": "failed to parse field [name]",
                        },
                    }
                },
            ],
        }
        resp.get = resp.body.get
        resp.__getitem__ = resp.body.__getitem__
        resp.__contains__ = resp.body.__contains__
        es.bulk.return_value = resp

        engine = IngestEngine(mock_client)
        result = engine.ingest(str(ndjson_file), "test-index", dlq_path=str(dlq_file))

        assert result.total_indexed == 1
        assert result.total_failed == 1

        # DLQ should contain the bulk error
        assert dlq_file.exists()
        dlq_entries = [
            json.loads(line) for line in dlq_file.read_text().strip().split("\n")
        ]
        assert len(dlq_entries) == 1
        assert dlq_entries[0]["source"] == "bulk_api"
        assert dlq_entries[0]["error"]["type"] == "mapper_parsing_exception"
        assert dlq_entries[0]["document"]["name"] == "Bob"
