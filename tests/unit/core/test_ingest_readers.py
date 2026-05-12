"""
Unit tests for the Ingest Engine readers.

Tests CSV, NDJSON, and JSON Array readers with various edge cases.
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

from elastro.core.ingest.readers import (
    CSVReader,
    JSONArrayReader,
    NDJSONReader,
    detect_format,
    read_source,
)


class TestDetectFormat:
    def test_csv(self) -> None:
        assert detect_format("data.csv") == "csv"

    def test_tsv(self) -> None:
        assert detect_format("data.tsv") == "csv"

    def test_ndjson(self) -> None:
        assert detect_format("events.ndjson") == "ndjson"

    def test_jsonl(self) -> None:
        assert detect_format("events.jsonl") == "ndjson"

    def test_json(self) -> None:
        assert detect_format("bulk.json") == "json"

    def test_sql(self) -> None:
        assert detect_format("dump.sql") == "sql"

    def test_unknown(self) -> None:
        assert detect_format("data.xlsx") == "unknown"


class TestCSVReader:
    def test_basic_csv(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("name,age,active\nAlice,30,true\nBob,25,false\n")

        docs = list(CSVReader(csv_file).read())
        assert len(docs) == 2
        assert docs[0] == {"name": "Alice", "age": "30", "active": "true"}
        assert docs[1]["name"] == "Bob"

    def test_tsv_detection(self, tmp_path: Path) -> None:
        tsv_file = tmp_path / "test.tsv"
        tsv_file.write_text("name\tage\nAlice\t30\n")

        docs = list(CSVReader(tsv_file).read())
        assert len(docs) == 1
        assert docs[0] == {"name": "Alice", "age": "30"}

    def test_custom_delimiter(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("name|age\nAlice|30\n")

        docs = list(CSVReader(csv_file, delimiter="|").read())
        assert len(docs) == 1
        assert docs[0] == {"name": "Alice", "age": "30"}

    def test_empty_csv(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text("name,age\n")
        docs = list(CSVReader(csv_file).read())
        assert len(docs) == 0

    def test_missing_file(self) -> None:
        with pytest.raises(FileNotFoundError):
            list(CSVReader("/nonexistent/file.csv").read())


class TestNDJSONReader:
    def test_basic_ndjson(self, tmp_path: Path) -> None:
        ndjson_file = tmp_path / "test.ndjson"
        ndjson_file.write_text(
            '{"name": "Alice", "age": 30}\n' '{"name": "Bob", "age": 25}\n'
        )

        docs = list(NDJSONReader(ndjson_file).read())
        assert len(docs) == 2
        assert docs[0]["name"] == "Alice"
        assert docs[0]["age"] == 30  # Native int, not string

    def test_blank_lines_skipped(self, tmp_path: Path) -> None:
        ndjson_file = tmp_path / "test.ndjson"
        ndjson_file.write_text('{"a": 1}\n\n\n{"b": 2}\n')
        docs = list(NDJSONReader(ndjson_file).read())
        assert len(docs) == 2

    def test_malformed_lines_skipped(self, tmp_path: Path) -> None:
        ndjson_file = tmp_path / "test.ndjson"
        ndjson_file.write_text('{"a": 1}\n{INVALID}\n{"b": 2}\n')
        docs = list(NDJSONReader(ndjson_file).read())
        assert len(docs) == 2  # Malformed line skipped

    def test_missing_file(self) -> None:
        with pytest.raises(FileNotFoundError):
            list(NDJSONReader("/nonexistent/file.ndjson").read())


class TestJSONArrayReader:
    def test_basic_json_array(self, tmp_path: Path) -> None:
        json_file = tmp_path / "test.json"
        data = [{"name": "Alice"}, {"name": "Bob"}]
        json_file.write_text(json.dumps(data))

        docs = list(JSONArrayReader(json_file).read())
        assert len(docs) == 2
        assert docs[0]["name"] == "Alice"

    def test_single_object(self, tmp_path: Path) -> None:
        json_file = tmp_path / "test.json"
        json_file.write_text(json.dumps({"name": "Alice"}))

        docs = list(JSONArrayReader(json_file).read())
        assert len(docs) == 1

    def test_invalid_root_type(self, tmp_path: Path) -> None:
        json_file = tmp_path / "test.json"
        json_file.write_text('"just a string"')

        with pytest.raises(ValueError, match="array or object"):
            list(JSONArrayReader(json_file).read())

    def test_missing_file(self) -> None:
        with pytest.raises(FileNotFoundError):
            list(JSONArrayReader("/nonexistent/file.json").read())


class TestReadSource:
    def test_auto_detect_csv(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("name,age\nAlice,30\n")

        docs = list(read_source(str(csv_file)))
        assert len(docs) == 1
        assert docs[0]["name"] == "Alice"

    def test_auto_detect_ndjson(self, tmp_path: Path) -> None:
        ndjson_file = tmp_path / "test.ndjson"
        ndjson_file.write_text('{"name": "Alice"}\n')

        docs = list(read_source(str(ndjson_file)))
        assert len(docs) == 1

    def test_explicit_format(self, tmp_path: Path) -> None:
        # File with wrong extension but explicit format
        file = tmp_path / "data.txt"
        file.write_text("name,age\nAlice,30\n")

        docs = list(read_source(str(file), format="csv"))
        assert len(docs) == 1

    def test_unknown_format_raises(self, tmp_path: Path) -> None:
        file = tmp_path / "data.xyz"
        file.write_text("something")

        with pytest.raises(ValueError, match="Cannot detect format"):
            list(read_source(str(file)))

    def test_sql_format_raises(self, tmp_path: Path) -> None:
        file = tmp_path / "dump.sql"
        file.write_text("SELECT 1")

        with pytest.raises(ValueError, match="SQL import requires"):
            list(read_source(str(file)))
