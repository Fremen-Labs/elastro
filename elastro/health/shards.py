"""Shard size analysis helpers for health diagnostics."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from elastro.core.logger import get_logger

logger = get_logger(__name__)

DEFAULT_OVERSHARD_THRESHOLD_MB = 1.0
DEFAULT_UNDERSHARD_THRESHOLD_GB = 50.0

_SIZE_MULTIPLIERS = {
    "b": 1,
    "kb": 1024,
    "mb": 1024**2,
    "gb": 1024**3,
    "tb": 1024**4,
}


@dataclass
class ShardSizeRecord:
    """Parsed shard row with a normalized byte size."""

    index: str
    shard: str
    prirep: str
    state: str
    store_bytes: int
    node: str = ""


@dataclass
class ShardAnalysis:
    """Aggregate shard size statistics."""

    total_shards: int = 0
    measured_shards: int = 0
    avg_bytes: float = 0.0
    oversharded_count: int = 0
    undersharded_count: int = 0
    unassigned_count: int = 0
    oversharded: List[ShardSizeRecord] = field(default_factory=list)
    undersharded: List[ShardSizeRecord] = field(default_factory=list)
    overshard_threshold_bytes: int = 0
    undershard_threshold_bytes: int = 0


def parse_store_size(value: Any) -> Optional[int]:
    """Parse Elasticsearch cat.shards store size strings into bytes."""
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text or text in {"n/a", "null", "-"}:
        return None
    for suffix, multiplier in sorted(
        _SIZE_MULTIPLIERS.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        if text.endswith(suffix):
            number = text[: -len(suffix)].strip()
            try:
                return int(float(number) * multiplier)
            except ValueError:
                return None
    try:
        return int(float(text))
    except ValueError:
        return None


def format_bytes(num_bytes: float) -> str:
    """Render a byte count in human-readable form."""
    size = float(num_bytes)
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} B"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def normalize_shard_rows(rows: List[Dict[str, Any]]) -> List[ShardSizeRecord]:
    """Convert raw cat.shards rows into normalized records."""
    records: List[ShardSizeRecord] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        index = str(row.get("index", "")).strip()
        if not index:
            continue
        store_bytes = parse_store_size(row.get("store"))
        records.append(
            ShardSizeRecord(
                index=index,
                shard=str(row.get("shard", "")),
                prirep=str(row.get("prirep", "")).lower(),
                state=str(row.get("state", "")).upper(),
                store_bytes=store_bytes or 0,
                node=str(row.get("node", "")),
            )
        )
    return records


def analyze_shards(
    rows: List[Dict[str, Any]],
    *,
    overshard_threshold_mb: float = DEFAULT_OVERSHARD_THRESHOLD_MB,
    undershard_threshold_gb: float = DEFAULT_UNDERSHARD_THRESHOLD_GB,
) -> ShardAnalysis:
    """Analyze shard sizes for oversharding and undersharding patterns."""
    overshard_bytes = int(overshard_threshold_mb * _SIZE_MULTIPLIERS["mb"])
    undershard_bytes = int(undershard_threshold_gb * _SIZE_MULTIPLIERS["gb"])

    records = normalize_shard_rows(rows)
    measured: List[ShardSizeRecord] = []
    oversharded: List[ShardSizeRecord] = []
    undersharded: List[ShardSizeRecord] = []
    unassigned = 0

    for record in records:
        if record.state == "UNASSIGNED":
            unassigned += 1
            continue
        if record.store_bytes <= 0:
            continue
        measured.append(record)
        if record.store_bytes < overshard_bytes:
            oversharded.append(record)
        elif record.store_bytes > undershard_bytes:
            undersharded.append(record)

    avg_bytes = (
        sum(item.store_bytes for item in measured) / len(measured)
        if measured
        else 0.0
    )
    logger.debug(
        "Shard analysis: total=%s measured=%s oversharded=%s undersharded=%s",
        len(records),
        len(measured),
        len(oversharded),
        len(undersharded),
    )
    return ShardAnalysis(
        total_shards=len(records),
        measured_shards=len(measured),
        avg_bytes=avg_bytes,
        oversharded_count=len(oversharded),
        undersharded_count=len(undersharded),
        unassigned_count=unassigned,
        oversharded=oversharded,
        undersharded=undersharded,
        overshard_threshold_bytes=overshard_bytes,
        undershard_threshold_bytes=undershard_bytes,
    )