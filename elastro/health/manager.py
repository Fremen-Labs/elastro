"""Health check and diagnostics operations for Elasticsearch."""

from typing import Any, Dict, List, Optional

from elastro.core.client import ElasticsearchClient
from elastro.core.errors import OperationError
from elastro.core.logger import get_logger

logger = get_logger(__name__)


class HealthManager:
    """Manager for Elasticsearch health and diagnostics operations."""

    def __init__(self, client: ElasticsearchClient):
        self._client = client
        self._es = client.client

    def health_report(
        self,
        *,
        verbose: bool = True,
        feature: Optional[str] = None,
    ) -> Dict[str, Any]:
        logger.debug(
            "Fetching _health_report verbose=%s feature=%s",
            verbose,
            feature,
        )
        try:
            kwargs: Dict[str, Any] = {"verbose": verbose}
            if feature:
                return dict(self._es.health_report(feature=feature, **kwargs))
            return dict(self._es.health_report(**kwargs))
        except Exception as e:
            logger.error("Health report request failed: %s", e, exc_info=True)
            raise OperationError(f"Failed to get health report: {str(e)}")

    def cluster_health(
        self,
        index: Optional[str] = None,
        level: str = "cluster",
        timeout: str = "30s",
        wait_for_status: Optional[str] = None,
    ) -> Dict[str, Any]:
        logger.debug(
            "Fetching cluster health level=%s wait=%s timeout=%s index=%s",
            level,
            wait_for_status,
            timeout,
            index,
        )
        try:
            params: Dict[str, Any] = {"level": level, "timeout": timeout}

            if wait_for_status:
                params["wait_for_status"] = wait_for_status

            if index:
                return dict(self._es.cluster.health(index=index, **params))
            return dict(self._es.cluster.health(**params))
        except Exception as e:
            logger.error("Cluster health request failed: %s", e, exc_info=True)
            raise OperationError(f"Failed to get cluster health: {str(e)}")

    def node_stats(
        self, node_id: Optional[str] = None, metrics: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        logger.debug("Fetching node stats node_id=%s metrics=%s", node_id, metrics)
        try:
            if node_id and metrics:
                return dict(
                    self._es.nodes.stats(node_id=node_id, metric=",".join(metrics))
                )
            if node_id:
                return dict(self._es.nodes.stats(node_id=node_id))
            if metrics:
                return dict(self._es.nodes.stats(metric=",".join(metrics)))
            return dict(self._es.nodes.stats())
        except Exception as e:
            logger.error("Node stats request failed: %s", e, exc_info=True)
            raise OperationError(f"Failed to get node stats: {str(e)}")

    def node_info(
        self, node_id: Optional[str] = None, metrics: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        logger.debug("Fetching node info node_id=%s metrics=%s", node_id, metrics)
        try:
            if node_id and metrics:
                return dict(
                    self._es.nodes.info(node_id=node_id, metric=",".join(metrics))
                )
            if node_id:
                return dict(self._es.nodes.info(node_id=node_id))
            if metrics:
                return dict(self._es.nodes.info(metric=",".join(metrics)))
            return dict(self._es.nodes.info())
        except Exception as e:
            logger.error("Node info request failed: %s", e, exc_info=True)
            raise OperationError(f"Failed to get node info: {str(e)}")

    def cluster_stats(self) -> Dict[str, Any]:
        logger.debug("Fetching cluster stats")
        try:
            return dict(self._es.cluster.stats())
        except Exception as e:
            logger.error("Cluster stats request failed: %s", e, exc_info=True)
            raise OperationError(f"Failed to get cluster stats: {str(e)}")

    def pending_tasks(self) -> List[Dict[str, Any]]:
        logger.debug("Fetching pending cluster tasks")
        try:
            return self._es.cluster.pending_tasks().get("tasks", [])
        except Exception as e:
            logger.error("Pending tasks request failed: %s", e, exc_info=True)
            raise OperationError(f"Failed to get pending tasks: {str(e)}")

    def allocation_explain(
        self,
        index: Optional[str] = None,
        shard: Optional[int] = None,
        primary: bool = False,
    ) -> Dict[str, Any]:
        logger.debug(
            "Explaining allocation index=%s shard=%s primary=%s",
            index,
            shard,
            primary,
        )
        try:
            body: Dict[str, Any] = {}
            if index:
                body["index"] = index
            if shard is not None:
                body["shard"] = shard
            if primary:
                body["primary"] = primary

            if body:
                return dict(self._es.cluster.allocation_explain(body=body))
            return dict(self._es.cluster.allocation_explain())
        except Exception as e:
            logger.error("Allocation explain request failed: %s", e, exc_info=True)
            raise OperationError(f"Failed to explain allocation: {str(e)}")

    def cluster_state(self, *, metric: Optional[str] = None) -> Dict[str, Any]:
        logger.debug("Fetching cluster state metric=%s", metric)
        try:
            params: Dict[str, Any] = {}
            if metric:
                params["metric"] = metric
            return dict(self._es.cluster.state(**params))
        except Exception as e:
            logger.error("Cluster state request failed: %s", e, exc_info=True)
            raise OperationError(f"Failed to get cluster state: {str(e)}") from e

    def cluster_settings(self, include_defaults: bool = False) -> Dict[str, Any]:
        logger.debug("Fetching cluster settings include_defaults=%s", include_defaults)
        try:
            return dict(
                self._es.cluster.get_settings(include_defaults=include_defaults)
            )
        except Exception as e:
            logger.error("Cluster settings request failed: %s", e, exc_info=True)
            raise OperationError(f"Failed to get cluster settings: {str(e)}")

    def verify_repository(self, repository: str) -> bool:
        logger.debug("Verifying snapshot repository %s", repository)
        try:
            response = self._es.snapshot.verify_repository(name=repository)
            return "nodes" in response
        except Exception as e:
            logger.error(
                "Repository verification failed for %s: %s",
                repository,
                e,
                exc_info=True,
            )
            raise OperationError(
                f"Failed to verify repository {repository}: {str(e)}"
            )

    def index_stats(self, index: Optional[str] = None) -> Dict[str, Any]:
        logger.debug("Fetching index stats index=%s", index)
        try:
            if index:
                return dict(self._es.indices.stats(index=index))
            return dict(self._es.indices.stats())
        except Exception as e:
            logger.error("Index stats request failed: %s", e, exc_info=True)
            raise OperationError(f"Failed to get index stats: {str(e)}")

    def diagnose(self) -> Dict[str, Any]:
        logger.info("Running cluster diagnostics summary")
        try:
            diagnostic: Dict[str, Any] = {
                "cluster_health": self.cluster_health(),
                "nodes_count": len(self._es.nodes.info().get("nodes", {})),
                "indices_count": len(self._es.indices.get(index="*").keys()),
                "pending_tasks": len(self.pending_tasks()),
            }

            health_status = diagnostic["cluster_health"].get("status", "unknown")
            diagnostic["status"] = {
                "is_healthy": health_status == "green",
                "health_status": health_status,
                "has_pending_tasks": diagnostic["pending_tasks"] > 0,
            }

            logger.info(
                "Diagnostics complete: status=%s nodes=%s indices=%s pending=%s",
                health_status,
                diagnostic["nodes_count"],
                diagnostic["indices_count"],
                diagnostic["pending_tasks"],
            )
            return diagnostic
        except Exception as e:
            logger.error("Diagnostics summary failed: %s", e, exc_info=True)
            raise OperationError(f"Failed to perform diagnostics: {str(e)}")