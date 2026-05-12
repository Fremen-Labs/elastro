"""
Ingest Engine — the core orchestrator for client-side data processing.

Executes the pipeline: Read → Validate → (Sanitize) → Index.
Supports batch processing with Rich progress bars, dead-letter queue
output, and configurable error thresholds.
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Generator, List, Optional, Union

from elastro.core.base import BaseManager
from elastro.core.client import ElasticsearchClient
from elastro.core.ingest.readers import read_source
from elastro.core.ingest.validators import SchemaValidator
from elastro.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class IngestResult:
    """Result summary from an ingest operation."""

    total_read: int = 0
    total_indexed: int = 0
    total_failed: int = 0
    total_skipped: int = 0
    elapsed_seconds: float = 0.0
    errors: List[Dict[str, Any]] = field(default_factory=list)
    dlq_path: Optional[str] = None

    @property
    def success_rate(self) -> float:
        if self.total_read == 0:
            return 0.0
        return (self.total_indexed / self.total_read) * 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_read": self.total_read,
            "total_indexed": self.total_indexed,
            "total_failed": self.total_failed,
            "total_skipped": self.total_skipped,
            "success_rate": round(self.success_rate, 1),
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "dlq_path": self.dlq_path,
            "error_count": len(self.errors),
        }


class IngestEngine(BaseManager):
    """
    Client-side data processing engine.

    Sits between raw data sources and Elasticsearch, handling format
    conversion, schema validation, type coercion, and batched bulk
    indexing with progress reporting.
    """

    def ingest(
        self,
        source: Union[str, Path],
        index: str,
        *,
        format: str = "auto",
        delimiter: Optional[str] = None,
        encoding: str = "utf-8",
        pipeline: Optional[str] = None,
        batch_size: int = 2000,
        max_errors: int = 100,
        validate: bool = False,
        mapping_properties: Optional[Dict[str, Dict[str, Any]]] = None,
        required_fields: Optional[List[str]] = None,
        strict: bool = False,
        dlq_path: Optional[Union[str, Path]] = None,
        refresh: bool = False,
        progress_callback: Optional[Callable[[int, int, int], None]] = None,
    ) -> IngestResult:
        """
        Ingest data from a file source into an Elasticsearch index.

        Args:
            source: File path or '-' for stdin.
            index: Target Elasticsearch index.
            format: File format ('csv', 'ndjson', 'json', 'auto').
            delimiter: CSV delimiter override.
            encoding: File encoding.
            pipeline: ES ingest pipeline to apply server-side.
            batch_size: Documents per bulk request.
            max_errors: Abort after this many errors.
            validate: Enable schema validation.
            mapping_properties: ES mapping properties for validation.
            required_fields: Fields that must be present.
            strict: Strict validation (reject on type mismatch).
            dlq_path: Path to write failed documents (captures both
                validation errors and ES bulk indexing errors).
            refresh: Refresh the index after each batch.
            progress_callback: Optional callback invoked after each batch with
                ``(total_read, total_indexed, total_failed)``. Enables
                non-CLI consumers to display progress without Rich.

        Returns:
            IngestResult with operation statistics.
        """
        result = IngestResult()
        start_time = time.monotonic()

        # Set up validator if requested
        validator: Optional[SchemaValidator] = None
        if validate and mapping_properties:
            validator = SchemaValidator(
                mapping_properties,
                strict=strict,
                required_fields=required_fields or [],
            )
        elif validate and not mapping_properties:
            # Auto-fetch mapping from the index
            try:
                self._ensure_connected()
                es = self._client.get_client()
                idx_info = es.indices.get(index=index)
                if hasattr(idx_info, "body"):
                    idx_info = idx_info.body
                idx_data = idx_info.get(index, {})
                props = idx_data.get("mappings", {}).get("properties", {})
                if props:
                    validator = SchemaValidator(
                        props,
                        strict=strict,
                        required_fields=required_fields or [],
                    )
                    logger.info(
                        f"Loaded mapping from index '{index}' ({len(props)} fields)"
                    )
            except Exception as e:
                logger.warning(f"Could not fetch mapping for validation: {e}")

        # Set up DLQ writer
        dlq_fh = None
        if dlq_path:
            dlq_fh = open(str(dlq_path), "w", encoding="utf-8")
            result.dlq_path = str(dlq_path)

        try:
            docs = read_source(
                source, format=format, delimiter=delimiter, encoding=encoding
            )
            batch: List[Dict[str, Any]] = []

            for doc in docs:
                result.total_read += 1

                # Validate + coerce
                if validator:
                    is_valid, coerced_doc, errors = validator.validate(doc)
                    if not is_valid:
                        result.total_failed += 1
                        error_entry = {
                            "row": result.total_read,
                            "errors": errors,
                            "document": doc,
                        }
                        result.errors.append(error_entry)
                        if dlq_fh:
                            dlq_fh.write(json.dumps(error_entry) + "\n")
                        if result.total_failed >= max_errors:
                            logger.error(
                                f"Aborting: max error threshold ({max_errors}) reached"
                            )
                            break
                        continue
                    doc = coerced_doc

                batch.append(doc)

                # Flush batch
                if len(batch) >= batch_size:
                    indexed, failed = self._flush_batch(
                        batch,
                        index,
                        pipeline=pipeline,
                        refresh=refresh,
                        dlq_fh=dlq_fh,
                        result=result,
                    )
                    result.total_indexed += indexed
                    result.total_failed += failed
                    batch = []

                    if progress_callback:
                        progress_callback(
                            result.total_read,
                            result.total_indexed,
                            result.total_failed,
                        )

                    if result.total_failed >= max_errors:
                        logger.error(
                            f"Aborting: max error threshold ({max_errors}) reached"
                        )
                        break

            # Flush remaining
            if batch:
                indexed, failed = self._flush_batch(
                    batch,
                    index,
                    pipeline=pipeline,
                    refresh=refresh,
                    dlq_fh=dlq_fh,
                    result=result,
                )
                result.total_indexed += indexed
                result.total_failed += failed

                if progress_callback:
                    progress_callback(
                        result.total_read,
                        result.total_indexed,
                        result.total_failed,
                    )

        finally:
            if dlq_fh:
                dlq_fh.close()

        result.elapsed_seconds = time.monotonic() - start_time
        logger.info(
            f"Ingest complete: {result.total_indexed}/{result.total_read} indexed "
            f"({result.total_failed} failed) in {result.elapsed_seconds:.1f}s"
        )
        return result

    def _flush_batch(
        self,
        batch: List[Dict[str, Any]],
        index: str,
        *,
        pipeline: Optional[str] = None,
        refresh: bool = False,
        dlq_fh: Any = None,
        result: Optional[IngestResult] = None,
    ) -> tuple[int, int]:
        """
        Send a batch of documents to Elasticsearch via the bulk API.

        Captures per-item bulk errors in the DLQ (if provided) for
        complete observability alongside validation failures.

        Returns (indexed_count, failed_count).
        """
        if not batch:
            return 0, 0

        try:
            self._ensure_connected()
            es = self._client.get_client()

            operations: List[Dict[str, Any]] = []
            for doc in batch:
                # Shallow copy to avoid mutating caller data
                doc_copy = doc.copy()
                doc_id = doc_copy.pop("_id", None)

                action: Dict[str, Any] = {"_index": index}
                if doc_id:
                    action["_id"] = doc_id
                if pipeline:
                    action["pipeline"] = pipeline

                operations.append({"index": action})
                operations.append(doc_copy)

            response = es.bulk(
                operations=operations,
                refresh="true" if refresh else "false",
            )

            if hasattr(response, "body"):
                response = response.body

            # Count successes and failures, capturing error details
            items = response.get("items", [])
            failed = 0
            indexed = 0
            for i, item in enumerate(items):
                item_result = item.get("index", {})
                if item_result.get("error") is not None:
                    failed += 1
                    # Write bulk error to DLQ for full observability
                    if dlq_fh and i < len(batch):
                        error_entry = {
                            "source": "bulk_api",
                            "error": item_result["error"],
                            "document": batch[i],
                        }
                        dlq_fh.write(json.dumps(error_entry) + "\n")
                        if result:
                            result.errors.append(error_entry)
                else:
                    indexed += 1

            if failed > 0:
                logger.warning(f"Batch: {indexed} indexed, {failed} failed")

            return indexed, failed

        except Exception as e:
            logger.error(f"Batch failed entirely: {e}")
            return 0, len(batch)
