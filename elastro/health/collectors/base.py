"""Collector protocol and registry for health assessment data gathering."""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Protocol,
    Sequence,
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
    # Caller-thread health_report (sequential or pooled barrier) for ILM.
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

        When ``health_report`` is selected, it runs to completion on this
        thread and publishes ``ctx.options["health_report"]`` before the
        remaining collectors are submitted.

        Workers > 1 assume ``ctx.client`` is already connected. Collector
        threads must not reconnect (``ElasticsearchClient.connect`` is not
        thread-safe). Use workers=1 if reconnect is required.
        """
        targets = names if names is not None else self.list()
        workers = collector_worker_count()
        if workers <= 1:
            return self._run_sequential(ctx, targets)
        return self._run_pooled(ctx, targets, workers)

    def _run_one(self, ctx: CollectContext, name: str) -> CollectorResult:
        collector = self._collectors.get(name)
        if collector is None:
            return _unknown_result(name)
        return _invoke_collector(collector, ctx, name)

    def _run_sequential(
        self,
        ctx: CollectContext,
        targets: Sequence[str],
    ) -> List[CollectorResult]:
        return [self._run_one(ctx, name) for name in targets]

    def _run_pooled(
        self,
        ctx: CollectContext,
        targets: Sequence[str],
        workers: int,
    ) -> List[CollectorResult]:
        rest = [name for name in targets if name != "health_report"]
        health_result = (
            self._run_one(ctx, "health_report") if "health_report" in targets else None
        )
        rest_results: List[CollectorResult] = []
        if rest:
            max_workers = max(1, min(workers, len(rest)))
            logger.debug(
                "Collector pool max_workers=%s count=%s",
                max_workers,
                len(rest),
            )
            with ThreadPoolExecutor(
                max_workers=max_workers,
                thread_name_prefix="elastro-health",
            ) as executor:
                futures = [executor.submit(self._run_one, ctx, name) for name in rest]
                rest_results = [future.result() for future in futures]
        rest_iter = iter(rest_results)
        results: List[CollectorResult] = []
        for name in targets:
            if name == "health_report":
                assert health_result is not None
                results.append(health_result)
            else:
                results.append(next(rest_iter))
        return results
