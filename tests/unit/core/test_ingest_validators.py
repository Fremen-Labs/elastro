"""
Unit tests for the Ingest Engine validators (schema validation, type inference, profiling).
"""

import pytest

from elastro.core.ingest.validators import (
    SchemaValidator,
    infer_mapping,
    profile_data,
    _infer_field_type,
    _is_date,
    _is_integer,
    _is_float,
    _is_boolean,
)


class TestTypeHeuristics:
    def test_is_date_iso(self) -> None:
        assert _is_date("2026-05-12T09:00:00Z") is True

    def test_is_date_simple(self) -> None:
        assert _is_date("2026-05-12") is True

    def test_is_date_us(self) -> None:
        assert _is_date("05/12/2026") is True

    def test_is_date_not(self) -> None:
        assert _is_date("hello world") is False

    def test_is_integer(self) -> None:
        assert _is_integer("42") is True
        assert _is_integer("-7") is True
        assert _is_integer("3.14") is False

    def test_is_float(self) -> None:
        assert _is_float("3.14") is True
        assert _is_float("42") is False  # int, not float

    def test_is_boolean(self) -> None:
        assert _is_boolean("true") is True
        assert _is_boolean("False") is True
        assert _is_boolean("yes") is True
        assert _is_boolean("maybe") is False


class TestInferFieldType:
    def test_native_ints(self) -> None:
        assert _infer_field_type([1, 2, 3]) == "integer"

    def test_native_large_ints(self) -> None:
        assert _infer_field_type([3_000_000_000]) == "long"

    def test_native_floats(self) -> None:
        assert _infer_field_type([1.5, 2.7]) == "double"

    def test_native_bools(self) -> None:
        assert _infer_field_type([True, False, True]) == "boolean"

    def test_string_dates(self) -> None:
        dates = ["2026-01-01", "2026-02-15", "2026-03-20"] * 20
        assert _infer_field_type(dates) == "date"

    def test_string_ips(self) -> None:
        ips = ["10.0.0.1", "192.168.1.1", "172.16.0.1"] * 20
        assert _infer_field_type(ips) == "ip"

    def test_short_strings_keyword(self) -> None:
        assert _infer_field_type(["active", "inactive", "pending"]) == "keyword"

    def test_long_strings_text(self) -> None:
        long_texts = ["a" * 200] * 10
        assert _infer_field_type(long_texts) == "text"

    def test_empty_values(self) -> None:
        assert _infer_field_type([None, "", None]) == "keyword"


class TestInferMapping:
    def test_basic_inference(self) -> None:
        docs = iter(
            [
                {"name": "Alice", "age": 30, "active": True},
                {"name": "Bob", "age": 25, "active": False},
            ]
        )
        mapping = infer_mapping(docs, sample_size=10)
        props = mapping["mappings"]["properties"]

        assert props["age"]["type"] == "integer"
        assert props["active"]["type"] == "boolean"
        assert props["name"]["type"] == "keyword"  # Short strings

    def test_text_field_has_keyword_subfield(self) -> None:
        docs = iter([{"body": "x" * 200}] * 10)
        mapping = infer_mapping(docs, sample_size=10)
        props = mapping["mappings"]["properties"]
        assert props["body"]["type"] == "text"
        assert "fields" in props["body"]
        assert props["body"]["fields"]["keyword"]["type"] == "keyword"


class TestProfileData:
    def test_basic_profile(self) -> None:
        docs = iter(
            [
                {"name": "Alice", "email": "alice@example.com", "age": 30},
                {"name": "Bob", "email": "bob@example.com", "age": 25},
            ]
        )
        report = profile_data(docs, sample_size=10)

        assert report["total_rows_sampled"] == 2
        assert report["total_fields"] == 3

        fields_by_name = {f["field"]: f for f in report["fields"]}
        assert "name" in fields_by_name
        assert "email" in fields_by_name
        # Email should flag PII
        assert fields_by_name["email"]["pii_risk"] == "PII"

    def test_pii_detection_ssn(self) -> None:
        docs = iter(
            [
                {"notes": "SSN: 123-45-6789"},
            ]
        )
        report = profile_data(docs, sample_size=10)
        fields_by_name = {f["field"]: f for f in report["fields"]}
        assert fields_by_name["notes"]["pii_risk"] == "PII"


class TestSchemaValidator:
    def test_valid_document(self) -> None:
        mapping = {"name": {"type": "keyword"}, "age": {"type": "integer"}}
        validator = SchemaValidator(mapping)

        is_valid, doc, errors = validator.validate({"name": "Alice", "age": 30})
        assert is_valid is True
        assert errors == []

    def test_coerce_string_to_int(self) -> None:
        mapping = {"age": {"type": "integer"}}
        validator = SchemaValidator(mapping)

        is_valid, doc, errors = validator.validate({"age": "42"})
        assert is_valid is True
        assert doc["age"] == 42  # Coerced

    def test_coerce_string_to_float(self) -> None:
        mapping = {"score": {"type": "double"}}
        validator = SchemaValidator(mapping)

        is_valid, doc, errors = validator.validate({"score": "3.14"})
        assert is_valid is True
        assert doc["score"] == 3.14

    def test_coerce_to_boolean(self) -> None:
        mapping = {"active": {"type": "boolean"}}
        validator = SchemaValidator(mapping)

        is_valid, doc, errors = validator.validate({"active": "true"})
        assert is_valid is True
        assert doc["active"] is True

    def test_strict_rejects_type_mismatch(self) -> None:
        mapping = {"age": {"type": "integer"}}
        validator = SchemaValidator(mapping, strict=True)

        is_valid, doc, errors = validator.validate({"age": "not_a_number"})
        assert is_valid is False
        assert len(errors) == 1
        assert "integer" in errors[0]

    def test_required_fields(self) -> None:
        mapping = {"name": {"type": "keyword"}}
        validator = SchemaValidator(mapping, required_fields=["name", "email"])

        is_valid, _, errors = validator.validate({"name": "Alice"})
        assert is_valid is False
        assert any("email" in e for e in errors)

    def test_unmapped_fields_pass_through(self) -> None:
        mapping = {"name": {"type": "keyword"}}
        validator = SchemaValidator(mapping)

        is_valid, doc, errors = validator.validate({"name": "Alice", "extra": "data"})
        assert is_valid is True
        assert doc["extra"] == "data"  # Not stripped

    def test_no_mutation_of_input(self) -> None:
        mapping = {"age": {"type": "integer"}}
        validator = SchemaValidator(mapping)
        original = {"age": "42"}

        _, coerced, _ = validator.validate(original)
        assert original["age"] == "42"  # Input not mutated
        assert coerced["age"] == 42  # Copy was coerced
