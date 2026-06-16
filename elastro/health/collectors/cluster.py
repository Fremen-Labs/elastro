"""Cluster-level health collectors."""

from typing import Any, Dict

from elastro.core.errors import OperationError
from elastro.core.logger import get_logger
from elastro.health.collectors.base import CollectContext, CollectorResult
from elastro.health.manager import HealthManager

logger = get_logger(__name__)


class ClusterHealthCollector:
    """Collect cluster health from _cluster/health."""

    name = "cluster_health"

    def collect(self, ctx: CollectContext) -> CollectorResult:
        manager = HealthManager(ctx.client)
        try:
            data: Dict[str, Any] = manager.cluster_health(timeout=ctx.timeout)
            try:
                state = manager.cluster_state(metric="blocks")
                blocks = state.get("blocks", {}) if isinstance(state, dict) else {}
                if isinstance(blocks, dict):
                    data["blocks"] = blocks
            except Exception as exc:
                logger.debug("Cluster blocks unavailable: %s", exc)
            return CollectorResult(name=self.name, status="ok", data=data)
        except OperationError as exc:
            logger.error("Cluster health collector failed: %s", exc)
            return CollectorResult(name=self.name, status="error", error=str(exc))


class PendingTasksCollector:
    """Collect pending cluster master tasks."""

    name = "pending_tasks"

    def collect(self, ctx: CollectContext) -> CollectorResult:
        manager = HealthManager(ctx.client)
        try:
            tasks = manager.pending_tasks()
            return CollectorResult(
                name=self.name,
                status="ok",
                data={"count": len(tasks), "tasks": tasks},
            )
        except OperationError as exc:
            logger.error("Pending tasks collector failed: %s", exc)
            return CollectorResult(name=self.name, status="error", error=str(exc))