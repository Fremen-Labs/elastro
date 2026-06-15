"""Collector protocol and registry for health assessment data gathering."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from elastro.core.client import ElasticsearchClient
from elastro.core.logger import get_logger

logger = get_logger(__name__)


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


class CollectorRegistry:
    """Registry of named health collectors."""

    def __init__(self) -> None:
        self._collectors: Dict[str, Collector] = {}

    def register(self, collector: Collector) -> None:
        if collector.name in self._collectors:
            raise ValueError(f"Collector already registered: {collector.name}")
        self._collectors[collector.name] = collector
        logger.debug("Registered health collector: %s", collector.name)

    def get(self, name: str) -> Optional[Collector]:
        return self._collectors.get(name)

    def list(self) -> List[str]:
        return sorted(self._collectors.keys())

    def run(
        self,
        ctx: CollectContext,
        names: Optional[List[str]] = None,
    ) -> List[CollectorResult]:
        """Run collectors sequentially; failures are captured per collector."""
        targets = names if names is not None else self.list()
        results: List[CollectorResult] = []

        for name in targets:
            collector = self._collectors.get(name)
            if collector is None:
                results.append(
                    CollectorResult(
                        name=name,
                        status="skipped",
                        error=f"Unknown collector: {name}",
                    )
                )
                continue

            start = time.monotonic()
            try:
                result = collector.collect(ctx)
            except Exception as exc:
                logger.warning("Collector %s failed: %s", name, exc)
                result = CollectorResult(
                    name=name,
                    status="error",
                    error=str(exc),
                    duration_ms=int((time.monotonic() - start) * 1000),
                )
            else:
                if result.duration_ms == 0:
                    result.duration_ms = int((time.monotonic() - start) * 1000)
            results.append(result)

        return results