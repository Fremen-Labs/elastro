"""
Elastro Ingest Engine package.

Provides client-side data processing capabilities that sit between raw data
sources and Elasticsearch:

- Multi-format readers (CSV, NDJSON, JSON, SQL)
- Schema validation and type coercion
- Data profiling and PII risk assessment
- Dead-letter queue for failed documents
"""

from elastro.core.ingest.engine import IngestEngine, IngestResult
from elastro.core.ingest.readers import (
    read_source,
    CSVReader,
    NDJSONReader,
    JSONArrayReader,
    SQLReader,
    SQLDumpReader,
)
from elastro.core.ingest.validators import SchemaValidator, infer_mapping

__all__ = [
    "IngestEngine",
    "IngestResult",
    "read_source",
    "CSVReader",
    "NDJSONReader",
    "JSONArrayReader",
    "SQLReader",
    "SQLDumpReader",
    "SchemaValidator",
    "infer_mapping",
]
