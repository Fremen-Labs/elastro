"""
Multi-format data readers for the Ingest Engine.

Each reader is a streaming generator that yields one document (dict) at a time,
ensuring constant memory usage regardless of source file size.

Supported formats:
- CSV  (.csv)      — stdlib csv.DictReader
- NDJSON (.ndjson) — line-by-line json.loads
- JSON Array (.json) — ijson streaming (falls back to stdlib for small files)
- SQL  (.sql)      — sqlalchemy streaming via yield_per  [optional dep]
"""

import csv
import io
import json
from pathlib import Path
from typing import Any, Dict, Generator, Optional, TextIO, Union

from elastro.core.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

_EXT_MAP = {
    ".csv": "csv",
    ".tsv": "csv",
    ".ndjson": "ndjson",
    ".jsonl": "ndjson",
    ".json": "json",
    ".sql": "sql",
}


def detect_format(source: Union[str, Path]) -> str:
    """Infer the file format from extension. Returns 'unknown' if unrecognised."""
    ext = Path(str(source)).suffix.lower()
    return _EXT_MAP.get(ext, "unknown")


# ---------------------------------------------------------------------------
# CSV Reader
# ---------------------------------------------------------------------------


class CSVReader:
    """Streaming CSV/TSV reader that yields one dict per row."""

    def __init__(
        self,
        source: Union[str, Path, TextIO],
        *,
        delimiter: Optional[str] = None,
        encoding: str = "utf-8",
    ) -> None:
        self.source = source
        self.delimiter = delimiter
        self.encoding = encoding

    def read(self) -> Generator[Dict[str, Any], None, None]:
        """Yield documents row-by-row from the CSV source."""
        if hasattr(self.source, "read"):
            yield from self._read_stream(self.source)  # type: ignore[arg-type]
        else:
            path = Path(str(self.source))
            if not path.exists():
                raise FileNotFoundError(f"CSV source not found: {path}")

            delimiter = self.delimiter
            if delimiter is None:
                delimiter = "\t" if path.suffix.lower() == ".tsv" else ","

            with open(path, "r", encoding=self.encoding, newline="") as fh:
                yield from self._read_stream(fh, delimiter)

    def _read_stream(
        self,
        fh: TextIO,
        delimiter: Optional[str] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        delim = delimiter or self.delimiter or ","
        reader = csv.DictReader(fh, delimiter=delim)
        row_num = 0
        for row in reader:
            row_num += 1
            # csv.DictReader may return OrderedDicts; normalise to plain dict
            yield dict(row)
        logger.debug(f"CSVReader: read {row_num} rows")


# ---------------------------------------------------------------------------
# NDJSON Reader
# ---------------------------------------------------------------------------


class NDJSONReader:
    """Streaming newline-delimited JSON reader."""

    def __init__(
        self,
        source: Union[str, Path, TextIO],
        *,
        encoding: str = "utf-8",
    ) -> None:
        self.source = source
        self.encoding = encoding

    def read(self) -> Generator[Dict[str, Any], None, None]:
        if hasattr(self.source, "read"):
            yield from self._read_stream(self.source)  # type: ignore[arg-type]
        else:
            path = Path(str(self.source))
            if not path.exists():
                raise FileNotFoundError(f"NDJSON source not found: {path}")
            with open(path, "r", encoding=self.encoding) as fh:
                yield from self._read_stream(fh)

    def _read_stream(self, fh: TextIO) -> Generator[Dict[str, Any], None, None]:
        line_num = 0
        for line in fh:
            line = line.strip()
            if not line:
                continue
            line_num += 1
            try:
                doc = json.loads(line)
                if isinstance(doc, dict):
                    yield doc
                else:
                    logger.warning(
                        f"NDJSON line {line_num}: expected object, got {type(doc).__name__}"
                    )
            except json.JSONDecodeError as e:
                logger.warning(f"NDJSON line {line_num}: parse error — {e}")
        logger.debug(f"NDJSONReader: read {line_num} lines")


# ---------------------------------------------------------------------------
# JSON Array Reader
# ---------------------------------------------------------------------------


class JSONArrayReader:
    """
    Reader for standard JSON files containing an array of objects.

    For files under 50 MB uses stdlib json.load for simplicity.
    For larger files attempts streaming via ijson (optional dependency).
    """

    MAX_SIMPLE_BYTES = 50 * 1024 * 1024  # 50 MB threshold

    def __init__(
        self,
        source: Union[str, Path, TextIO],
        *,
        encoding: str = "utf-8",
    ) -> None:
        self.source = source
        self.encoding = encoding

    def read(self) -> Generator[Dict[str, Any], None, None]:
        if hasattr(self.source, "read"):
            yield from self._read_simple(self.source)  # type: ignore[arg-type]
            return

        path = Path(str(self.source))
        if not path.exists():
            raise FileNotFoundError(f"JSON source not found: {path}")

        size = path.stat().st_size
        if size > self.MAX_SIMPLE_BYTES:
            try:
                yield from self._read_streaming(path)
                return
            except ImportError:
                logger.warning(
                    "Large JSON file detected but 'ijson' not installed. "
                    "Loading entire file into memory. Install ijson for streaming: "
                    "pip install ijson"
                )

        with open(path, "r", encoding=self.encoding) as fh:
            yield from self._read_simple(fh)

    def _read_simple(self, fh: TextIO) -> Generator[Dict[str, Any], None, None]:
        data = json.load(fh)
        if isinstance(data, list):
            count = 0
            for item in data:
                if isinstance(item, dict):
                    count += 1
                    yield item
            logger.debug(f"JSONArrayReader: read {count} documents from array")
        elif isinstance(data, dict):
            yield data
            logger.debug("JSONArrayReader: read 1 document (single object)")
        else:
            raise ValueError(
                f"JSON root must be an array or object, got {type(data).__name__}"
            )

    def _read_streaming(self, path: Path) -> Generator[Dict[str, Any], None, None]:
        import ijson  # type: ignore[import-untyped, import-not-found]

        count = 0
        with open(path, "rb") as fh:
            for item in ijson.items(fh, "item"):
                if isinstance(item, dict):
                    count += 1
                    yield item
        logger.debug(f"JSONArrayReader (streaming): read {count} documents")


# ---------------------------------------------------------------------------
# Unified entry point
# ---------------------------------------------------------------------------


def read_source(
    source: Union[str, Path, TextIO],
    *,
    format: str = "auto",
    delimiter: Optional[str] = None,
    encoding: str = "utf-8",
) -> Generator[Dict[str, Any], None, None]:
    """
    Auto-detecting source reader. Yields one document dict at a time.

    Args:
        source: File path, Path object, or open text stream ('-' for stdin).
        format: One of 'csv', 'ndjson', 'json', 'auto'. Auto-detects from extension.
        delimiter: CSV delimiter override (default: ',' for .csv, '\\t' for .tsv).
        encoding: File encoding (default: utf-8).

    Yields:
        Dict[str, Any] — one document per iteration.
    """
    # Handle stdin sentinel
    if source == "-":
        import sys

        if format == "auto":
            raise ValueError(
                "Cannot auto-detect format when reading from stdin. Use --format."
            )
        source_stream: TextIO = sys.stdin
        if format == "csv":
            yield from CSVReader(source_stream, delimiter=delimiter).read()
        elif format in ("ndjson", "jsonl"):
            yield from NDJSONReader(source_stream).read()
        elif format == "json":
            yield from JSONArrayReader(source_stream).read()
        else:
            raise ValueError(f"Unsupported format for stdin: {format}")
        return

    # Resolve format
    resolved = format
    if resolved == "auto":
        if hasattr(source, "read"):
            raise ValueError(
                "Cannot auto-detect format from an open stream. Use --format."
            )
        resolved = detect_format(source)  # type: ignore[arg-type]
        
    if resolved == "unknown":
        raise ValueError(
            f"Cannot detect format for '{source}'. "
            "Use --format to specify (csv, ndjson, json)."
        )

    if resolved == "csv":
        yield from CSVReader(source, delimiter=delimiter, encoding=encoding).read()
    elif resolved in ("ndjson", "jsonl"):
        yield from NDJSONReader(source, encoding=encoding).read()
    elif resolved == "json":
        yield from JSONArrayReader(source, encoding=encoding).read()
    elif resolved == "sql":
        raise ValueError(
            "SQL import requires a DSN connection string. "
            "Use: elastro ingest import --sql 'SELECT ...' --dsn 'postgresql://...'"
        )
    else:
        raise ValueError(f"Unsupported format: {resolved}")
