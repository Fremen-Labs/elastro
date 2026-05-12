"""
Elastro Ingest Engine package.

Provides client-side data processing capabilities that sit between raw data
sources and Elasticsearch:

- Multi-format readers (CSV, NDJSON, JSON, SQL)
- Schema validation and type coercion
- Data profiling and PII risk assessment
- Client-side sanitization (PII redaction, dedup, field filtering)
- Fluent ingest pipeline builder
- Deterministic Grok pattern builder
- Dead-letter queue for failed documents
"""

from elastro.core.ingest.engine import IngestEngine, IngestResult
from elastro.core.ingest.grok_builder import GrokBuilder, GrokResult
from elastro.core.ingest.pipeline_builder import IngestPipelineBuilder
from elastro.core.ingest.readers import (
    read_source,
    CSVReader,
    NDJSONReader,
    JSONArrayReader,
    SQLReader,
    SQLDumpReader,
)
from elastro.core.ingest.sanitizers import SanitizationChain
from elastro.core.ingest.validators import SchemaValidator, infer_mapping

__all__ = [
    "IngestEngine",
    "IngestResult",
    "IngestPipelineBuilder",
    "GrokBuilder",
    "GrokResult",
    "SanitizationChain",
    "read_source",
    "CSVReader",
    "NDJSONReader",
    "JSONArrayReader",
    "SQLReader",
    "SQLDumpReader",
    "SchemaValidator",
    "infer_mapping",
]
