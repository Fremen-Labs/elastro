"""
Schema validation and type coercion for the Ingest Engine.

Provides:
- Auto-mapping inference from sample documents (with recursive nested support)
- Schema validation against ES index mappings
- Type coercion (string → int, string → date, etc.)
- Data profiling with PII risk assessment

.. note::
    Inference is sample-based and heuristic; always review generated mappings
    before production use. Edge cases (mixed-type fields, sparse nested
    structures) may require manual adjustment.
"""

import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple

from elastro.core.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# PII detection patterns — imported from the canonical sanitizers registry
# to keep profiling and redaction in sync across HIPAA + Financial patterns.
# ---------------------------------------------------------------------------

from elastro.core.ingest.sanitizers import (
    PII_PATTERNS,
    SENSITIVE_FIELD_NAMES,
)

# ---------------------------------------------------------------------------
# Type inference heuristics
# ---------------------------------------------------------------------------

_DATE_FORMATS = [
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%d/%m/%Y",
]


def _is_date(value: str) -> bool:
    """Check if a string looks like a date."""
    for fmt in _DATE_FORMATS:
        try:
            datetime.strptime(value.strip(), fmt)
            return True
        except ValueError:
            continue
    return False


def _is_integer(value: str) -> bool:
    try:
        int(value.strip())
        return True
    except (ValueError, AttributeError):
        return False


def _is_float(value: str) -> bool:
    try:
        float(value.strip())
        return not _is_integer(value)
    except (ValueError, AttributeError):
        return False


def _is_boolean(value: str) -> bool:
    return value.strip().lower() in ("true", "false", "yes", "no", "1", "0")


def _is_ip(value: str) -> bool:
    return bool(PII_PATTERNS["ipv4"].fullmatch(value.strip()))


def _infer_field_type(values: List[Any]) -> str:
    """Infer Elasticsearch field type from a sample of values.

    Handles nested dicts (mapped as 'object') and lists of dicts
    (mapped as 'nested'). Scalar lists are mapped based on the
    dominant element type.
    """
    non_null = [v for v in values if v is not None and str(v).strip() != ""]
    if not non_null:
        return "keyword"

    # Check native Python types first (for JSON/NDJSON sources)
    py_types = Counter(type(v).__name__ for v in non_null)
    dominant = py_types.most_common(1)[0][0]

    if dominant == "dict":
        return "object"
    if dominant == "list":
        # Peek inside the list to determine nested vs scalar-array
        flat_items = [item for v in non_null if isinstance(v, list) for item in v]
        if flat_items and all(isinstance(item, dict) for item in flat_items[:20]):
            return "nested"
        # Scalar arrays — infer from the element type
        if flat_items:
            return _infer_field_type(flat_items)
        return "keyword"
    if dominant == "bool":
        return "boolean"
    if dominant == "int":
        max_val = max(abs(v) for v in non_null if isinstance(v, int))
        return "long" if max_val > 2_147_483_647 else "integer"
    if dominant == "float":
        return "double"

    # String-based inference
    str_values = [str(v) for v in non_null[:200]]

    # Check dates
    date_hits = sum(1 for v in str_values[:50] if _is_date(v))
    if date_hits > len(str_values[:50]) * 0.8:
        return "date"

    # Check IPs
    ip_hits = sum(1 for v in str_values[:50] if _is_ip(v))
    if ip_hits > len(str_values[:50]) * 0.8:
        return "ip"

    # Check booleans
    bool_hits = sum(1 for v in str_values[:50] if _is_boolean(v))
    if bool_hits > len(str_values[:50]) * 0.9:
        return "boolean"

    # Check integers
    int_hits = sum(1 for v in str_values[:100] if _is_integer(v))
    if int_hits > len(str_values[:100]) * 0.9:
        return "integer"

    # Check floats
    float_hits = sum(1 for v in str_values[:100] if _is_float(v))
    if float_hits > len(str_values[:100]) * 0.9:
        return "double"

    # Text vs keyword: long strings → text, short → keyword
    avg_len = sum(len(v) for v in str_values) / len(str_values)
    unique_ratio = len(set(str_values)) / len(str_values)

    if avg_len > 128 or (avg_len > 64 and unique_ratio > 0.8):
        return "text"

    return "keyword"


# ---------------------------------------------------------------------------
# Mapping inference
# ---------------------------------------------------------------------------


def _infer_properties_recursive(
    field_values: Dict[str, List[Any]],
) -> Dict[str, Any]:
    """Build properties dict with recursive descent for nested objects."""
    properties: Dict[str, Any] = {}
    for field, values in field_values.items():
        es_type = _infer_field_type(values)
        properties[field] = {"type": es_type}

        # Recurse into object fields
        if es_type == "object":
            child_values: Dict[str, List[Any]] = defaultdict(list)
            for v in values:
                if isinstance(v, dict):
                    for ck, cv in v.items():
                        child_values[ck].append(cv)
            if child_values:
                properties[field]["properties"] = _infer_properties_recursive(
                    child_values
                )

        # Recurse into nested (array-of-objects) fields
        elif es_type == "nested":
            child_values = defaultdict(list)
            for v in values:
                if isinstance(v, list):
                    for item in v:
                        if isinstance(item, dict):
                            for ck, cv in item.items():
                                child_values[ck].append(cv)
            if child_values:
                properties[field]["properties"] = _infer_properties_recursive(
                    child_values
                )

        # Add keyword sub-field for text fields
        elif es_type == "text":
            properties[field]["fields"] = {
                "keyword": {"type": "keyword", "ignore_above": 256}
            }

    return properties


def infer_mapping(
    docs: Generator[Dict[str, Any], None, None],
    *,
    sample_size: int = 500,
) -> Dict[str, Any]:
    """
    Infer an Elasticsearch mapping from a sample of documents.

    Samples up to ``sample_size`` documents and uses heuristics to determine
    optimal field types. Supports recursive inference for nested objects
    and arrays of objects.

    .. note::
        Inference is sample-based and heuristic; always review the generated
        mapping before production use.

    Args:
        docs: Generator of document dicts.
        sample_size: Number of documents to sample.

    Returns:
        Dict with ``{"mappings": {"properties": {...}}}`` structure.
    """
    field_values: Dict[str, List[Any]] = defaultdict(list)
    count = 0

    for doc in docs:
        if count >= sample_size:
            break
        for key, value in doc.items():
            field_values[key].append(value)
        count += 1

    properties = _infer_properties_recursive(field_values)

    logger.info(f"Inferred mapping from {count} documents, {len(properties)} fields")
    return {"mappings": {"properties": properties}}


# ---------------------------------------------------------------------------
# Data profiling
# ---------------------------------------------------------------------------


def profile_data(
    docs: Generator[Dict[str, Any], None, None],
    *,
    sample_size: int = 1000,
) -> Dict[str, Any]:
    """
    Profile a data source for quality assessment before import.

    Returns per-field statistics including type, null rate, uniqueness,
    and PII risk assessment.
    """
    field_values: Dict[str, List[Any]] = defaultdict(list)
    total_rows = 0

    for doc in docs:
        if total_rows >= sample_size:
            break
        for key, value in doc.items():
            field_values[key].append(value)
        total_rows += 1

    fields: List[Dict[str, Any]] = []
    pii_risk_count = 0

    for field, values in field_values.items():
        non_null = [v for v in values if v is not None and str(v).strip() != ""]
        non_null_pct = (len(non_null) / len(values) * 100) if values else 0
        unique_pct = len(set(str(v) for v in non_null)) / max(len(non_null), 1) * 100

        es_type = _infer_field_type(values)

        # PII risk check — value-based regex detection
        pii_risk = "NONE"
        _HIGH_CONFIDENCE_PII = frozenset(
            {
                "email",
                "ssn",
                "credit_card",
                "dob",
                "npi",
                "dea_number",
                "iban",
                "tax_id_ein",
            }
        )

        # 1. Field-name heuristic (HIPAA/Financial identifiers with no
        #    standard format — MRN, beneficiary, device serial, etc.)
        if field.lower() in SENSITIVE_FIELD_NAMES:
            pii_risk = "PHI"
            pii_risk_count += 1
        elif non_null:
            # 2. Regex-based value scanning
            sample_str = " ".join(str(v) for v in non_null[:100])
            for pii_name, pattern in PII_PATTERNS.items():
                if pattern.search(sample_str):
                    pii_risk = "PII" if pii_name in _HIGH_CONFIDENCE_PII else "HIGH"
                    pii_risk_count += 1
                    break

        # Sample values
        samples = [str(v) for v in non_null[:3]]

        fields.append(
            {
                "field": field,
                "inferred_type": es_type,
                "non_null_pct": round(non_null_pct, 1),
                "unique_pct": round(unique_pct, 1),
                "pii_risk": pii_risk,
                "sample_values": samples,
            }
        )

    return {
        "total_rows_sampled": total_rows,
        "total_fields": len(fields),
        "pii_risk_fields": pii_risk_count,
        "fields": fields,
    }


# ---------------------------------------------------------------------------
# Schema validator
# ---------------------------------------------------------------------------


_TYPE_COERCION: Dict[str, Callable[[Any], Any]] = {
    "integer": int,
    "long": int,
    "short": int,
    "byte": int,
    "float": float,
    "double": float,
    "half_float": float,
    "scaled_float": float,
    "boolean": lambda v: (
        v if isinstance(v, bool) else str(v).lower() in ("true", "1", "yes")
    ),
}


class SchemaValidator:
    """
    Validates and coerces documents against an Elasticsearch mapping.

    Can operate in two modes:
    - **Strict**: reject documents with type mismatches or missing required fields.
    - **Coerce** (default): attempt to convert values to the expected type.
    """

    def __init__(
        self,
        mapping_properties: Dict[str, Dict[str, Any]],
        *,
        strict: bool = False,
        required_fields: Optional[List[str]] = None,
    ) -> None:
        self.mapping = mapping_properties
        self.strict = strict
        self.required_fields = required_fields or []

    def validate(self, doc: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], List[str]]:
        """
        Validate and optionally coerce a document.

        Returns:
            Tuple of (is_valid, coerced_doc, list_of_errors).
        """
        errors: List[str] = []
        result = doc.copy()

        # Check required fields
        for field in self.required_fields:
            if field not in result or result[field] is None:
                errors.append(f"Missing required field: {field}")

        # Type coercion / validation
        for field, value in list(result.items()):
            if value is None:
                continue
            if field not in self.mapping:
                continue  # Unmapped fields pass through (dynamic mapping)

            expected_type = self.mapping[field].get("type", "keyword")

            if expected_type in _TYPE_COERCION and not isinstance(value, (dict, list)):
                if self.strict:
                    # Strict mode: check without coercing
                    coercer = _TYPE_COERCION[expected_type]
                    try:
                        coercer(value)
                    except (ValueError, TypeError):
                        errors.append(
                            f"Field '{field}': expected {expected_type}, got {type(value).__name__}"
                        )
                else:
                    # Coerce mode: attempt conversion
                    coercer = _TYPE_COERCION[expected_type]
                    try:
                        result[field] = coercer(value)
                    except (ValueError, TypeError):
                        errors.append(
                            f"Field '{field}': cannot coerce '{value}' to {expected_type}"
                        )

        is_valid = len(errors) == 0
        return is_valid, result, errors
