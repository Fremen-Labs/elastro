"""Collector protocol and registry for health assessment data gathering."""

from __future__ import annotations

import os
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    runtime_checkable,
)

from pydantic import BaseModel, Field

from elastro.core.client import ElasticsearchClient
from elastro.core.logger import get_logger

logger = get_logger(__name__)

COLLECTOR_WORKERS_ENV = "ELASTRO_HEALTH_COLLECTOR_WORKERS"
DEFAULT_COLLECTOR_WORKERS = 4


class CollectorResult(BaseModel):
    name: str
    status: str = "ok"
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    duration_ms: int = 0


@dataclass
class CollectContext:
    client: ElasticsearchClient
    timeout: str = "30s"
    es_version: Optional[str] = None
    options: Dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Collector(Protocol):
    """Protocol for health assessment data collectors."""

    name: str

    def collect(self, ctx: CollectContext) -> CollectorResult: ...


def collector_worker_count() -> int:
    """Return the collector pool size from ELASTRO_HEALTH_COLLECTOR_WORKERS.

    Values ``<= 1`` select the sequential loop. Invalid values fall back to 4.
    """
    raw = os.environ.get(COLLECTOR_WORKERS_ENV)
    if raw is None or raw.strip() == "":
        return DEFAULT_COLLECTOR_WORKERS
    try:
        workers = int(raw)
    except ValueError:
        logger.warning(
            "Invalid %s=%s; using default %s",
            COLLECTOR_WORKERS_ENV,
            raw,
            DEFAULT_COLLECTOR_WORKERS,
        )
        return DEFAULT_COLLECTOR_WORKERS
    if workers < 1:
        return 1
    return workers


def _unknown_result(name: str) -> CollectorResult:
    return CollectorResult(
        name=name,
        status="skipped",
        error=f"Unknown collector: {name}",
    )


def _invoke_collector(
    collector: Collector,
    ctx: CollectContext,
    name: str,
) -> CollectorResult:
    start = time.monotonic()
    try:
        result = collector.collect(ctx)
    except Exception as exc:
        logger.warning("Collector %s failed: %s", name, exc, exc_info=True)
        return CollectorResult(
            name=name,
            status="error",
            error=str(exc),
            duration_ms=int((time.monotonic() - start) * 1000),
        )
    if result.duration_ms == 0:
        result.duration_ms = int((time.monotonic() - start) * 1000)
    logger.debug(
        "Collector %s finished: status=%s duration_ms=%s",
        name,
        result.status,
        result.duration_ms,
    )
    # Sequential workers=1 runs health_report first; ILM reads this hint.
    if result.name == "health_report" and result.status == "ok":
        ctx.options["health_report"] = result.data.get("report")
    return result


class CollectorRegistry:
    """Registry of named health collectors."""

    def __init__(self) -> None:
        self._collectors: Dict[str, Collector] = {}
        self._order: List[str] = []

    def register(self, collector: Collector) -> None:
        if collector.name in self._collectors:
            raise ValueError(f"Collector already registered: {collector.name}")
        self._collectors[collector.name] = collector
        self._order.append(collector.name)
        logger.debug("Registered health collector: %s", collector.name)

    def get(self, name: str) -> Optional[Collector]:
        return self._collectors.get(name)

    def list(self) -> List[str]:
        return list(self._order)

    def run(
        self,
        ctx: CollectContext,
        names: Optional[List[str]] = None,
    ) -> List[CollectorResult]:
        """Run collectors; failures are captured per collector.

        ``ELASTRO_HEALTH_COLLECTOR_WORKERS`` > 1 (default 4) uses a thread
        pool. Results are joined in registration / ``names`` order. There is
        no Future timeout; in-flight HTTP calls are not cancelled.
        """
        targets = names if names is not None else self.list()
        workers = collector_worker_count()
        if workers <= 1:
            return self._run_sequential(ctx, targets)
        return self._run_pooled(ctx, targets, workers)

    def _run_sequential(
        self,
        ctx: CollectContext,
        targets: Sequence[str],
    ) -> List[CollectorResult]:
        results: List[CollectorResult] = []
        for name in targets:
            collector = self._collectors.get(name)
            if collector is None:
                results.append(_unknown_result(name))
                continue
            results.append(_invoke_collector(collector, ctx, name))
        return results

    def _run_pooled(
        self,
        ctx: CollectContext,
        targets: Sequence[str],
        workers: int,
    ) -> List[CollectorResult]:
        max_workers = max(1, min(workers, len(targets) or 1))
        logger.debug(
            "Collector pool max_workers=%s count=%s",
            max_workers,
            len(targets),
        )
        ordered: List[Tuple[str, Optional[Future[CollectorResult]]]] = []
        with ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="elastro-health",
        ) as executor:
            for name in targets:
                collector = self._collectors.get(name)
                if collector is None:
                    ordered.append((name, None))
                    continue
                ordered.append(
                    (name, executor.submit(_invoke_collector, collector, ctx, name))
                )
            results: List[CollectorResult] = []
            for name, future in ordered:
                if future is None:
                    results.append(_unknown_result(name))
                    continue
                try:
                    results.append(future.result())
                except Exception as exc:
                    logger.warning(
                        "Collector %s failed: %s",
                        name,
                        exc,
                        exc_info=True,
                    )
                    results.append(
                        CollectorResult(
                            name=name,
                            status="error",
                            error=str(exc),
                        )
                    )
        return results
