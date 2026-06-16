"""Mapping field counting helpers for health lint and rules."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from elastro.core.logger import get_logger

logger = get_logger(__name__)

DEFAULT_FIELD_LIMIT = 1000
DEFAULT_FIELD_WARN_RATIO = 0.8
DEFAULT_MAX_INDICES = 50


def is_system_index(index_name: str) -> bool:
    """Return True for Elasticsearch system indices."""
    name = index_name.strip()
    return name.startswith(".") or name.startswith("elastro-")


def count_mapping_fields(properties: Optional[Dict[str, Any]]) -> int:
    """Recursively count mapped fields including nested and multi-fields."""
    if not isinstance(properties, dict):
        return 0

    total = 0
    for spec in properties.values():
        if not isinstance(spec, dict):
            total += 1
            continue
        total += 1
        if "properties" in spec:
            total += count_mapping_fields(spec.get("properties"))
        if "fields" in spec:
            total += count_mapping_fields(spec.get("fields"))
    return total


def extract_field_limit(settings: Dict[str, Any]) -> int:
    """Read index.mapping.total_fields.limit from index settings."""
    index_settings = settings.get("index") if isinstance(settings, dict) else {}
    if not isinstance(index_settings, dict):
        return DEFAULT_FIELD_LIMIT
    raw = index_settings.get("mapping.total_fields.limit", DEFAULT_FIELD_LIMIT)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return DEFAULT_FIELD_LIMIT


def summarize_index_mapping(
    index_name: str,
    index_body: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a field-count summary for a single index."""
    mappings = index_body.get("mappings") or {}
    properties = mappings.get("properties") or {}
    settings = index_body.get("settings") or {}
    field_count = count_mapping_fields(properties)
    field_limit = extract_field_limit(settings)
    ratio = field_count / field_limit if field_limit else 0.0
    return {
        "index": index_name,
        "field_count": field_count,
        "field_limit": field_limit,
        "field_ratio": round(ratio, 4),
    }


def select_user_indices(
    indices: List[Dict[str, Any]],
    *,
    limit: int = DEFAULT_MAX_INDICES,
) -> List[str]:
    """Return non-system index names up to a scan limit."""
    names: List[str] = []
    for entry in indices:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("index", "")).strip()
        if not name or is_system_index(name):
            continue
        names.append(name)
        if len(names) >= limit:
            break
    return sorted(names)
