"""Data arrival and freshness checks for APM and Beats streams."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from pydantic import BaseModel, Field

from elastro.config import get_config
from elastro.core.client import ElasticsearchClient
from elastro.core.datastream import DatastreamManager
from elastro.core.document import DocumentManager
from elastro.core.errors import DocumentError, OperationError, ValidationError
from elastro.core.index import IndexManager
from elastro.core.logger import get_logger
from elastro.health.history import parse_window

logger = get_logger(__name__)

DEFAULT_WINDOW = "15m"
DEFAULT_MIN_DOCS = 1
DEFAULT_APM_PATTERNS = ("traces-apm*", "metrics-apm*", "logs-apm*")
DEFAULT_BEATS_PATTERNS = (
    "filebeat-*",
    "metricbeat-*",
    "logs-filebeat*",
    "metrics-metricbeat*",
)
DEFAULT_ALL_PATTERNS = DEFAULT_APM_PATTERNS + DEFAULT_BEATS_PATTERNS
_TRACK_TOTAL_HITS_CAP = 10000
_MISSING_INDEX_MARKERS = (
    "index_not_found",
    "no such index",
    "resource_not_found",
    "not_found_exception",
)


class CoverageCheck(BaseModel):
    """A single pass/fail assertion inside a coverage report."""

    name: str
    passed: bool
    summary: str
    detail: Optional[str] = None
    doc_count: int = 0
    latest_timestamp: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CoverageReport(BaseModel):
    """Aggregated coverage result for a service, pattern, or all streams."""

    passed: bool
    target: str
    window: str
    checks: List[CoverageCheck] = Field(default_factory=list)
    doc_count: int = 0
    latest_timestamp: Optional[str] = None


class CoverageValidator:
    """Validate that expected APM/Beats data is arriving."""

    def __init__(self, client: ElasticsearchClient) -> None:
        self._documents = DocumentManager(client)
        self._indices = IndexManager(client)
        self._datastreams = DatastreamManager(client)

    def check_service(
        self,
        service_name: str,
        *,
        window: str = DEFAULT_WINDOW,
        min_docs: int = DEFAULT_MIN_DOCS,
        max_age: Optional[str] = None,
        max_cardinality: Optional[int] = None,
    ) -> CoverageReport:
        """Check that ``service.name`` has recent documents on APM streams."""
        name = (service_name or "").strip()
        if not name:
            raise ValidationError("service name is required")
        return self._run(
            target=f"service:{name}",
            pattern=",".join(DEFAULT_APM_PATTERNS),
            window=window,
            min_docs=min_docs,
            max_age=max_age,
            max_cardinality=max_cardinality,
            service_name=name,
        )

    def check_pattern(
        self,
        pattern: str,
        *,
        window: str = DEFAULT_WINDOW,
        min_docs: int = DEFAULT_MIN_DOCS,
        max_age: Optional[str] = None,
        max_cardinality: Optional[int] = None,
    ) -> CoverageReport:
        """Check document arrival and freshness for an index/data-stream pattern."""
        value = (pattern or "").strip()
        if not value:
            raise ValidationError("pattern is required")
        return self._run(
            target=f"pattern:{value}",
            pattern=value,
            window=window,
            min_docs=min_docs,
            max_age=max_age,
            max_cardinality=max_cardinality,
            service_name=None,
        )

    def check_all(
        self,
        *,
        window: str = DEFAULT_WINDOW,
        min_docs: int = DEFAULT_MIN_DOCS,
        max_age: Optional[str] = None,
        max_cardinality: Optional[int] = None,
    ) -> CoverageReport:
        """Check every default APM and Beats pattern (full coverage gate)."""
        reports = [
            self.check_pattern(
                pattern,
                window=window,
                min_docs=min_docs,
                max_age=max_age,
                max_cardinality=max_cardinality,
            )
            for pattern in DEFAULT_ALL_PATTERNS
        ]
        checks: List[CoverageCheck] = []
        for report in reports:
            checks.extend(report.checks)
        timestamps = [report.latest_timestamp for report in reports]
        return CoverageReport(
            passed=all(report.passed for report in reports),
            target="all",
            window=window,
            checks=checks,
            doc_count=sum(report.doc_count for report in reports),
            latest_timestamp=_max_timestamp(timestamps),
        )

    def _run(
        self,
        *,
        target: str,
        pattern: str,
        window: str,
        min_docs: int,
        max_age: Optional[str],
        max_cardinality: Optional[int],
        service_name: Optional[str],
    ) -> CoverageReport:
        _parse_duration(window)
        if min_docs < 0:
            raise ValidationError("min_docs must be >= 0")
        if max_cardinality is not None and max_cardinality < 1:
            raise ValidationError("max_cardinality must be >= 1")
        freshness_window = max_age or window
        _parse_duration(freshness_window)

        checks: List[CoverageCheck] = []
        indices = self._list_indices(pattern)
        streams = self._list_datastreams(pattern)
        present = bool(indices or streams)
        resource_names = [str(item.get("index") or "") for item in indices]
        resource_names.extend(str(item.get("name") or "") for item in streams)
        resource_names = [name for name in resource_names if name]
        checks.append(
            CoverageCheck(
                name="streams_present",
                passed=present,
                summary=(
                    f"Found {len(resource_names)} matching index/data stream(s)"
                    if present
                    else f"No indices or data streams match '{pattern}'"
                ),
                metadata={"resources": resource_names[:50]},
            )
        )

        doc_count = 0
        latest_timestamp: Optional[str] = None
        search_body: Optional[Dict[str, Any]] = None
        search_missing = False
        if present:
            try:
                search_body = self._search(
                    pattern=pattern,
                    window=window,
                    min_docs=min_docs,
                    service_name=service_name,
                    freshness_window=freshness_window,
                )
            except DocumentError as exc:
                if _is_missing_index(exc):
                    logger.info("Coverage search found no index for %s", pattern)
                    search_body = None
                    search_missing = True
                    checks.append(
                        CoverageCheck(
                            name="doc_count",
                            passed=False,
                            summary=f"Index pattern '{pattern}' was not found",
                        )
                    )
                else:
                    logger.error(
                        "Coverage search failed pattern=%s: %s",
                        pattern,
                        exc,
                        exc_info=True,
                    )
                    raise OperationError(
                        f"Coverage search failed for '{pattern}': {exc}"
                    ) from exc

        if search_body is not None:
            doc_count = _hit_count(search_body)
            aggs = search_body.get("aggregations") or search_body.get("aggs") or {}
            scoped = _scoped_aggs(aggs)
            latest_timestamp, _latest_dt = _latest_from_agg(aggs)
            count_ok = doc_count >= min_docs
            checks.append(
                CoverageCheck(
                    name="doc_count",
                    passed=count_ok,
                    summary=(
                        f"{doc_count} document(s) in the last {window} (min {min_docs})"
                    ),
                    doc_count=doc_count,
                    latest_timestamp=latest_timestamp,
                    metadata={"min_docs": min_docs, "window": window},
                )
            )
            fresh_count = int((aggs.get("fresh") or {}).get("doc_count") or 0)
            fresh_ok = fresh_count > 0
            checks.append(
                CoverageCheck(
                    name="freshness",
                    passed=fresh_ok,
                    summary=(
                        f"Latest document at {latest_timestamp}"
                        if latest_timestamp
                        else "No @timestamp found in the window"
                    ),
                    doc_count=doc_count,
                    latest_timestamp=latest_timestamp,
                    metadata={"max_age": freshness_window, "fresh_docs": fresh_count},
                )
            )
            checks.append(
                _field_presence_check(
                    scoped,
                    doc_count=doc_count,
                    require_service=service_name is not None,
                )
            )
            if max_cardinality is not None:
                cardinality = int(
                    (scoped.get("service_cardinality") or {}).get("value") or 0
                )
                checks.append(
                    CoverageCheck(
                        name="cardinality",
                        passed=cardinality <= max_cardinality,
                        summary=(
                            f"{cardinality} unique service.name value(s) "
                            f"(max {max_cardinality})"
                        ),
                        doc_count=doc_count,
                        metadata={
                            "cardinality": cardinality,
                            "max_cardinality": max_cardinality,
                        },
                    )
                )
        elif present and not search_missing:
            checks.append(
                CoverageCheck(
                    name="doc_count",
                    passed=min_docs <= 0,
                    summary=f"No searchable documents for '{pattern}'",
                    metadata={"min_docs": min_docs},
                )
            )

        if service_name:
            _apply_service_streams_present(
                checks,
                present=present,
                doc_count=doc_count,
                service_name=service_name,
                resource_names=resource_names,
            )

        return CoverageReport(
            passed=all(check.passed for check in checks),
            target=target,
            window=window,
            checks=checks,
            doc_count=doc_count,
            latest_timestamp=latest_timestamp,
        )

    def _list_indices(self, pattern: str) -> List[Dict[str, Any]]:
        try:
            rows = self._indices.list(pattern)
        except Exception as exc:
            if _is_missing_index(exc):
                return []
            logger.error("Index list failed for %s: %s", pattern, exc, exc_info=True)
            raise OperationError(
                f"Failed to list indices for '{pattern}': {exc}"
            ) from exc
        return [row for row in rows if isinstance(row, dict)]

    def _list_datastreams(self, pattern: str) -> List[Dict[str, Any]]:
        try:
            rows = self._datastreams.list(pattern)
        except Exception as exc:
            if _is_missing_index(exc):
                return []
            logger.error(
                "Data stream list failed for %s: %s", pattern, exc, exc_info=True
            )
            raise OperationError(
                f"Failed to list data streams for '{pattern}': {exc}"
            ) from exc
        return [row for row in rows if isinstance(row, dict)]

    def _search(
        self,
        *,
        pattern: str,
        window: str,
        min_docs: int,
        service_name: Optional[str],
        freshness_window: str,
    ) -> Dict[str, Any]:
        filters: List[Dict[str, Any]] = [
            {"range": {"@timestamp": {"gte": f"now-{window}"}}}
        ]
        if service_name:
            filters.append({"term": {"service.name": service_name}})
        track = min(_TRACK_TOTAL_HITS_CAP, max(min_docs + 1, 1))
        logger.debug(
            "Coverage search pattern=%s window=%s track_total_hits=%s",
            pattern,
            window,
            track,
        )
        scoped_filters = list(filters)
        response = self._documents.search(
            index=pattern,
            query={"bool": {"filter": filters}},
            options={
                "size": 0,
                "track_total_hits": track,
                "aggs": {
                    "latest": {"max": {"field": "@timestamp"}},
                    "fresh": {
                        "filter": {
                            "range": {"@timestamp": {"gte": f"now-{freshness_window}"}}
                        }
                    },
                    "in_window": {
                        "filter": {"bool": {"filter": scoped_filters}},
                        "aggs": {
                            "has_service_name": {
                                "filter": {"exists": {"field": "service.name"}}
                            },
                            "has_host_name": {
                                "filter": {"exists": {"field": "host.name"}}
                            },
                            "service_cardinality": {
                                "cardinality": {
                                    "field": "service.name",
                                    "precision_threshold": 100,
                                }
                            },
                        },
                    },
                },
            },
        )
        if not isinstance(response, dict):
            return {}
        return response


def default_coverage_window() -> str:
    """Return ``coverage.default_window`` from config, or ``15m``."""
    try:
        raw = (get_config().get("coverage") or {}).get("default_window")
    except Exception:
        raw = None
    window = str(raw or DEFAULT_WINDOW).strip() or DEFAULT_WINDOW
    try:
        _parse_duration(window)
    except ValidationError:
        return DEFAULT_WINDOW
    return window


def _parse_duration(window: str) -> Any:
    try:
        return parse_window(window)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc


def _hit_count(body: Dict[str, Any]) -> int:
    total = (body.get("hits") or {}).get("total", 0)
    if isinstance(total, dict):
        try:
            return int(total.get("value") or 0)
        except (TypeError, ValueError):
            return 0
    try:
        return int(total or 0)
    except (TypeError, ValueError):
        return 0


def _latest_from_agg(
    aggs: Dict[str, Any],
) -> tuple[Optional[str], Optional[datetime]]:
    latest = aggs.get("latest") or {}
    stamp = latest.get("value_as_string")
    value = latest.get("value")
    parsed: Optional[datetime] = None
    if value is not None:
        try:
            parsed = datetime.fromtimestamp(float(value) / 1000.0, tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            parsed = None
    if stamp:
        return str(stamp), parsed
    if parsed is not None:
        return parsed.isoformat(), parsed
    return None, None


def _scoped_aggs(aggs: Dict[str, Any]) -> Dict[str, Any]:
    """Return field-presence aggregations nested under the time-window filter."""
    nested = aggs.get("in_window")
    if not isinstance(nested, dict):
        return aggs
    inner = nested.get("aggs")
    if isinstance(inner, dict) and (
        "has_service_name" in inner
        or "has_host_name" in inner
        or "service_cardinality" in inner
    ):
        return inner
    if (
        "has_service_name" in nested
        or "has_host_name" in nested
        or "service_cardinality" in nested
    ):
        return nested
    return aggs


def _apply_service_streams_present(
    checks: List[CoverageCheck],
    *,
    present: bool,
    doc_count: int,
    service_name: str,
    resource_names: List[str],
) -> None:
    """Do not treat stream-name matches as coverage when the service term is empty."""
    if doc_count > 0:
        return
    for check in checks:
        if check.name != "streams_present":
            continue
        check.passed = False
        if present:
            check.summary = (
                f"Found {len(resource_names)} matching index/data stream(s) "
                f"but 0 documents with service.name={service_name}"
            )
        check.metadata["service.name"] = service_name
        check.metadata["doc_count"] = doc_count
        return


def _field_presence_check(
    aggs: Dict[str, Any],
    *,
    doc_count: int,
    require_service: bool,
) -> CoverageCheck:
    has_service = int((aggs.get("has_service_name") or {}).get("doc_count") or 0)
    has_host = int((aggs.get("has_host_name") or {}).get("doc_count") or 0)
    if doc_count <= 0:
        return CoverageCheck(
            name="field_presence",
            passed=False,
            summary="Cannot verify service.name/host.name without documents",
            doc_count=0,
        )
    if require_service:
        passed = has_service > 0
        summary = (
            f"service.name present on {has_service}/{doc_count} document(s)"
            if passed
            else "service.name is missing from documents in the window"
        )
    else:
        passed = has_service > 0 or has_host > 0
        summary = (
            f"service.name={has_service}, host.name={has_host} of {doc_count} docs"
        )
    return CoverageCheck(
        name="field_presence",
        passed=passed,
        summary=summary,
        doc_count=doc_count,
        metadata={"service.name": has_service, "host.name": has_host},
    )


def _is_missing_index(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    meta = getattr(exc, "meta", None)
    if status is None and meta is not None:
        status = getattr(meta, "status", None)
    if status == 404:
        return True
    message = str(exc).lower()
    return any(marker in message for marker in _MISSING_INDEX_MARKERS)


def _max_timestamp(values: Sequence[Optional[str]]) -> Optional[str]:
    present = [value for value in values if value]
    if not present:
        return None
    return max(present)
