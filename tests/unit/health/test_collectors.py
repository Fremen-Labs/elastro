"""Unit tests for health collector registry."""

import os
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from unittest.mock import Mock, patch

from elastro.core.client import ElasticsearchClient
from elastro.health.collectors.base import (
    COLLECTOR_WORKERS_ENV,
    CollectContext,
    CollectorRegistry,
    CollectorResult,
    collector_worker_count,
)
from elastro.health.collectors.cluster import (
    ClusterHealthCollector,
    PendingTasksCollector,
)


class _FailingCollector:
    name = "failing"

    def collect(self, ctx: CollectContext) -> CollectorResult:
        raise RuntimeError("boom")


class _StubCollector:
    def __init__(self, name: str, *, delay: float = 0, error: Optional[str] = None):
        self.name = name
        self._delay = delay
        self._error = error

    def collect(self, ctx: CollectContext) -> CollectorResult:
        if self._delay:
            time.sleep(self._delay)
        if self._error:
            raise RuntimeError(self._error)
        return CollectorResult(name=self.name, status="ok", data={"name": self.name})


class TestCollectorRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = CollectorRegistry()
        self.mock_client = Mock(spec=ElasticsearchClient)
        self.ctx = CollectContext(client=self.mock_client)

    def _run_with_workers(self, workers: int, names=None):
        with patch.dict(os.environ, {COLLECTOR_WORKERS_ENV: str(workers)}):
            return self.registry.run(self.ctx, names=names)

    def test_register_and_list(self):
        self.registry.register(ClusterHealthCollector())
        self.registry.register(PendingTasksCollector())
        self.assertEqual(
            self.registry.list(), ["cluster_health", "pending_tasks"]
        )  # registration order, not alphabetical

    def test_duplicate_registration_raises(self):
        self.registry.register(ClusterHealthCollector())
        with self.assertRaises(ValueError):
            self.registry.register(ClusterHealthCollector())

    def test_run_unknown_collector(self):
        for workers in (1, 4):
            with self.subTest(workers=workers):
                results = self._run_with_workers(workers, names=["missing"])
                self.assertEqual(len(results), 1)
                self.assertEqual(results[0].status, "skipped")
                self.assertIn("Unknown collector", results[0].error or "")

    def test_run_captures_collector_exception(self):
        self.registry.register(_FailingCollector())
        for workers in (1, 4):
            with self.subTest(workers=workers):
                results = self._run_with_workers(workers, names=["failing"])
                self.assertEqual(results[0].status, "error")
                self.assertEqual(results[0].error, "boom")

    def test_run_keeps_sibling_results_in_registration_order(self):
        self.registry.register(_StubCollector("alpha", delay=0.05))
        self.registry.register(_StubCollector("bravo"))
        self.registry.register(_StubCollector("charlie", error="boom"))
        for workers in (1, 4):
            with self.subTest(workers=workers):
                results = self._run_with_workers(workers)
                self.assertEqual(
                    [result.name for result in results],
                    ["alpha", "bravo", "charlie"],
                )
                self.assertEqual(
                    [result.status for result in results],
                    ["ok", "ok", "error"],
                )
                self.assertEqual(results[2].error, "boom")
                self.assertEqual(results[0].data["name"], "alpha")
                self.assertEqual(results[1].data["name"], "bravo")

    def test_workers_one_does_not_use_thread_pool(self):
        self.registry.register(_StubCollector("alpha"))
        with patch.dict(os.environ, {COLLECTOR_WORKERS_ENV: "1"}):
            with patch("elastro.health.collectors.base.ThreadPoolExecutor") as pool_cls:
                results = self.registry.run(self.ctx)
        pool_cls.assert_not_called()
        self.assertEqual(results[0].status, "ok")

    def test_workers_four_uses_thread_pool(self):
        self.registry.register(_StubCollector("alpha"))
        self.registry.register(_StubCollector("bravo"))
        with patch.dict(os.environ, {COLLECTOR_WORKERS_ENV: "4"}):
            with patch(
                "elastro.health.collectors.base.ThreadPoolExecutor",
                wraps=ThreadPoolExecutor,
            ) as pool_cls:
                results = self.registry.run(self.ctx)
        pool_cls.assert_called_once()
        self.assertEqual(pool_cls.call_args.kwargs.get("max_workers"), 2)
        self.assertEqual([result.name for result in results], ["alpha", "bravo"])
        self.assertEqual([result.status for result in results], ["ok", "ok"])

    def test_slow_collector_result_is_kept(self):
        self.registry.register(_StubCollector("slow", delay=0.05))
        self.registry.register(_StubCollector("fast"))
        results = self._run_with_workers(4)
        self.assertEqual([result.name for result in results], ["slow", "fast"])
        self.assertEqual([result.status for result in results], ["ok", "ok"])

    def test_pooled_health_report_publishes_before_siblings(self):
        main_thread = threading.get_ident()
        health_thread: dict = {}

        class _HealthReport:
            name = "health_report"

            def collect(self, ctx: CollectContext) -> CollectorResult:
                health_thread["id"] = threading.get_ident()
                return CollectorResult(
                    name=self.name,
                    status="ok",
                    data={"report": {"stagnating": True}},
                )

        class _Ilm:
            name = "ilm"

            def collect(self, ctx: CollectContext) -> CollectorResult:
                return CollectorResult(
                    name=self.name,
                    status="ok",
                    data={"hint": ctx.options.get("health_report")},
                )

        self.registry.register(_Ilm())
        self.registry.register(_HealthReport())
        results = self._run_with_workers(4)
        self.assertEqual(health_thread["id"], main_thread)
        self.assertEqual([result.name for result in results], ["ilm", "health_report"])
        self.assertEqual(results[0].status, "ok")
        self.assertEqual(results[0].data["hint"], {"stagnating": True})
        self.assertEqual(results[1].status, "ok")


class TestCollectorWorkerCount(unittest.TestCase):
    def test_default_is_four(self):
        with patch.dict(os.environ):
            os.environ.pop(COLLECTOR_WORKERS_ENV, None)
            self.assertEqual(collector_worker_count(), 4)

    def test_parses_one_and_four(self):
        with patch.dict(os.environ, {COLLECTOR_WORKERS_ENV: "1"}):
            self.assertEqual(collector_worker_count(), 1)
        with patch.dict(os.environ, {COLLECTOR_WORKERS_ENV: "4"}):
            self.assertEqual(collector_worker_count(), 4)

    def test_invalid_falls_back_to_default(self):
        with patch.dict(os.environ, {COLLECTOR_WORKERS_ENV: "nope"}):
            self.assertEqual(collector_worker_count(), 4)


class TestClusterHealthCollector(unittest.TestCase):
    def test_collect_success(self):
        mock_es = Mock()
        mock_es.cluster.health.return_value = {
            "cluster_name": "test",
            "status": "green",
        }
        mock_client = Mock(spec=ElasticsearchClient)
        mock_client.client = mock_es

        collector = ClusterHealthCollector()
        result = collector.collect(CollectContext(client=mock_client))

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.data["status"], "green")
        mock_es.cluster.health.assert_called_once_with(level="cluster", timeout="30s")


if __name__ == "__main__":
    unittest.main()
