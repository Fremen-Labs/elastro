"""
Fluent builder for Elasticsearch ingest pipeline definitions.

Allows programmatic construction of pipeline JSON via a chained
method API, with optional deployment to a live cluster.

Example::

    pipeline = (
        IngestPipelineBuilder("web-logs")
        .description("Parse and enrich web access logs")
        .grok("message", ["%{COMBINEDAPACHELOG}"])
        .date("timestamp", ["dd/MMM/yyyy:HH:mm:ss Z"])
        .geoip("clientip")
        .convert("response", "integer")
        .rename("clientip", "client.ip")
        .remove("message")
        .on_failure("failed-web-logs")
        .build()
    )
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from elastro.core.logger import get_logger

logger = get_logger(__name__)


class IngestPipelineBuilder:
    """Fluent builder for Elasticsearch ingest pipeline definitions.

    Each processor method appends to an internal list and returns
    ``self`` so calls can be chained.  Call :meth:`build` to produce
    the final JSON dict, or :meth:`deploy` to push it to a cluster.
    """

    def __init__(self, pipeline_id: str) -> None:
        self._pipeline_id = pipeline_id
        self._description: str = ""
        self._processors: List[Dict[str, Any]] = []
        self._on_failure: Optional[List[Dict[str, Any]]] = None

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def description(self, text: str) -> IngestPipelineBuilder:
        """Set the pipeline description."""
        self._description = text
        return self

    # ------------------------------------------------------------------
    # Processors
    # ------------------------------------------------------------------

    def grok(
        self,
        field: str,
        patterns: List[str],
        *,
        ignore_missing: bool = False,
    ) -> IngestPipelineBuilder:
        """Add a Grok processor for pattern-based text parsing."""
        proc: Dict[str, Any] = {
            "grok": {
                "field": field,
                "patterns": patterns,
            }
        }
        if ignore_missing:
            proc["grok"]["ignore_missing"] = True
        self._processors.append(proc)
        return self

    def date(
        self,
        field: str,
        formats: List[str],
        *,
        target_field: str = "@timestamp",
        timezone: Optional[str] = None,
    ) -> IngestPipelineBuilder:
        """Add a Date processor for timestamp parsing."""
        cfg: Dict[str, Any] = {
            "field": field,
            "formats": formats,
            "target_field": target_field,
        }
        if timezone:
            cfg["timezone"] = timezone
        self._processors.append({"date": cfg})
        return self

    def rename(
        self,
        field: str,
        target_field: str,
        *,
        ignore_missing: bool = False,
    ) -> IngestPipelineBuilder:
        """Add a Rename processor."""
        cfg: Dict[str, Any] = {
            "field": field,
            "target_field": target_field,
        }
        if ignore_missing:
            cfg["ignore_missing"] = True
        self._processors.append({"rename": cfg})
        return self

    def remove(
        self,
        field: str,
        *,
        ignore_missing: bool = False,
    ) -> IngestPipelineBuilder:
        """Add a Remove processor."""
        cfg: Dict[str, Any] = {"field": field}
        if ignore_missing:
            cfg["ignore_missing"] = True
        self._processors.append({"remove": cfg})
        return self

    def convert(
        self,
        field: str,
        target_type: str,
        *,
        target_field: Optional[str] = None,
        ignore_missing: bool = False,
    ) -> IngestPipelineBuilder:
        """Add a Convert processor for type conversion."""
        cfg: Dict[str, Any] = {"field": field, "type": target_type}
        if target_field:
            cfg["target_field"] = target_field
        if ignore_missing:
            cfg["ignore_missing"] = True
        self._processors.append({"convert": cfg})
        return self

    def lowercase(
        self,
        field: str,
        *,
        ignore_missing: bool = False,
    ) -> IngestPipelineBuilder:
        """Add a Lowercase processor."""
        cfg: Dict[str, Any] = {"field": field}
        if ignore_missing:
            cfg["ignore_missing"] = True
        self._processors.append({"lowercase": cfg})
        return self

    def uppercase(
        self,
        field: str,
        *,
        ignore_missing: bool = False,
    ) -> IngestPipelineBuilder:
        """Add an Uppercase processor."""
        cfg: Dict[str, Any] = {"field": field}
        if ignore_missing:
            cfg["ignore_missing"] = True
        self._processors.append({"uppercase": cfg})
        return self

    def set_field(
        self,
        field: str,
        value: Any,
    ) -> IngestPipelineBuilder:
        """Add a Set processor to inject a static or template value."""
        self._processors.append({"set": {"field": field, "value": value}})
        return self

    def gsub(
        self,
        field: str,
        pattern: str,
        replacement: str,
    ) -> IngestPipelineBuilder:
        """Add a Gsub processor for regex replacement."""
        self._processors.append(
            {
                "gsub": {
                    "field": field,
                    "pattern": pattern,
                    "replacement": replacement,
                }
            }
        )
        return self

    def geoip(
        self,
        field: str,
        *,
        target_field: Optional[str] = None,
        ignore_missing: bool = True,
    ) -> IngestPipelineBuilder:
        """Add a GeoIP enrichment processor."""
        cfg: Dict[str, Any] = {"field": field}
        if target_field:
            cfg["target_field"] = target_field
        if ignore_missing:
            cfg["ignore_missing"] = True
        self._processors.append({"geoip": cfg})
        return self

    def redact(
        self,
        field: str,
        patterns: List[str],
        *,
        pattern_definitions: Optional[Dict[str, str]] = None,
    ) -> IngestPipelineBuilder:
        """Add a Redact processor for PII removal."""
        cfg: Dict[str, Any] = {"field": field, "patterns": patterns}
        if pattern_definitions:
            cfg["pattern_definitions"] = pattern_definitions
        self._processors.append({"redact": cfg})
        return self

    def dissect(
        self,
        field: str,
        pattern: str,
        *,
        append_separator: Optional[str] = None,
    ) -> IngestPipelineBuilder:
        """Add a Dissect processor for delimiter-based parsing."""
        cfg: Dict[str, Any] = {"field": field, "pattern": pattern}
        if append_separator:
            cfg["append_separator"] = append_separator
        self._processors.append({"dissect": cfg})
        return self

    def script(
        self,
        source: str,
        *,
        lang: str = "painless",
        params: Optional[Dict[str, Any]] = None,
    ) -> IngestPipelineBuilder:
        """Add a Script processor for custom logic."""
        cfg: Dict[str, Any] = {"lang": lang, "source": source}
        if params:
            cfg["params"] = params
        self._processors.append({"script": cfg})
        return self

    def inference(
        self,
        model_id: str,
        *,
        field_map: Optional[Dict[str, str]] = None,
        target_field: Optional[str] = None,
    ) -> IngestPipelineBuilder:
        """Add an Inference processor for ML model execution."""
        cfg: Dict[str, Any] = {"model_id": model_id}
        if field_map:
            cfg["field_map"] = field_map
        if target_field:
            cfg["target_field"] = target_field
        self._processors.append({"inference": cfg})
        return self

    def custom(self, processor: Dict[str, Any]) -> IngestPipelineBuilder:
        """Add an arbitrary processor dict (escape hatch)."""
        self._processors.append(processor)
        return self

    # ------------------------------------------------------------------
    # Failure handling
    # ------------------------------------------------------------------

    def on_failure(
        self,
        dead_letter_index: str,
    ) -> IngestPipelineBuilder:
        """Configure on_failure to route errors to a dead-letter index.

        Captures the original document and error metadata.
        """
        self._on_failure = [
            {
                "set": {
                    "field": "_index",
                    "value": dead_letter_index,
                }
            },
            {
                "set": {
                    "field": "error.message",
                    "value": "{{ _ingest.on_failure_message }}",
                }
            },
            {
                "set": {
                    "field": "error.processor_type",
                    "value": "{{ _ingest.on_failure_processor_type }}",
                }
            },
        ]
        return self

    # ------------------------------------------------------------------
    # Build & deploy
    # ------------------------------------------------------------------

    def build(self) -> Dict[str, Any]:
        """Build the pipeline definition dict.

        Returns:
            Dict ready for the Elasticsearch Put Pipeline API.
        """
        body: Dict[str, Any] = {
            "description": self._description,
            "processors": list(self._processors),
        }
        if self._on_failure:
            body["on_failure"] = self._on_failure
        return body

    @property
    def pipeline_id(self) -> str:
        """The pipeline ID this builder was initialized with."""
        return self._pipeline_id

    @property
    def processor_count(self) -> int:
        """Number of processors currently in the pipeline."""
        return len(self._processors)

    def deploy(
        self,
        client: Any,
        *,
        pipeline_id: Optional[str] = None,
    ) -> None:
        """Deploy the pipeline to an Elasticsearch cluster.

        Args:
            client: An ``ElasticsearchClient`` instance.
            pipeline_id: Override the builder's pipeline ID.
        """
        pid = pipeline_id or self._pipeline_id
        body = self.build()
        es = client.get_client()
        es.ingest.put_pipeline(id=pid, body=body)
        logger.info(f"Pipeline '{pid}' deployed ({self.processor_count} processors)")
