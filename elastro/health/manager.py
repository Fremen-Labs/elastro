"""Health check and diagnostics operations for Elasticsearch."""

from typing import Any, Dict, List, Optional

from elastro.core.client import ElasticsearchClient
from elastro.core.errors import OperationError


class HealthManager:
    """Manager for Elasticsearch health and diagnostics operations."""

    def __init__(self, client: ElasticsearchClient):
        self._client = client
        self._es = client.client

    def cluster_health(
        self,
        index: Optional[str] = None,
        level: str = "cluster",
        timeout: str = "30s",
        wait_for_status: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            params: Dict[str, Any] = {"level": level, "timeout": timeout}

            if wait_for_status:
                params["wait_for_status"] = wait_for_status

            if index:
                return dict(self._es.cluster.health(index=index, **params))
            return dict(self._es.cluster.health(**params))
        except Exception as e:
            raise OperationError(f"Failed to get cluster health: {str(e)}")

    def node_stats(
        self, node_id: Optional[str] = None, metrics: Optional[List[str]] = None
    ) -> Dict[str, Any]:
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
            raise OperationError(f"Failed to get node stats: {str(e)}")

    def node_info(
        self, node_id: Optional[str] = None, metrics: Optional[List[str]] = None
    ) -> Dict[str, Any]:
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
            raise OperationError(f"Failed to get node info: {str(e)}")

    def cluster_stats(self) -> Dict[str, Any]:
        try:
            return dict(self._es.cluster.stats())
        except Exception as e:
            raise OperationError(f"Failed to get cluster stats: {str(e)}")

    def pending_tasks(self) -> List[Dict[str, Any]]:
        try:
            return self._es.cluster.pending_tasks().get("tasks", [])
        except Exception as e:
            raise OperationError(f"Failed to get pending tasks: {str(e)}")

    def allocation_explain(
        self,
        index: Optional[str] = None,
        shard: Optional[int] = None,
        primary: bool = False,
    ) -> Dict[str, Any]:
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
            raise OperationError(f"Failed to explain allocation: {str(e)}")

    def cluster_settings(self, include_defaults: bool = False) -> Dict[str, Any]:
        try:
            return dict(
                self._es.cluster.get_settings(include_defaults=include_defaults)
            )
        except Exception as e:
            raise OperationError(f"Failed to get cluster settings: {str(e)}")

    def verify_repository(self, repository: str) -> bool:
        try:
            response = self._es.snapshot.verify_repository(name=repository)
            return "nodes" in response
        except Exception as e:
            raise OperationError(
                f"Failed to verify repository {repository}: {str(e)}"
            )

    def index_stats(self, index: Optional[str] = None) -> Dict[str, Any]:
        try:
            if index:
                return dict(self._es.indices.stats(index=index))
            return dict(self._es.indices.stats())
        except Exception as e:
            raise OperationError(f"Failed to get index stats: {str(e)}")

    def diagnose(self) -> Dict[str, Any]:
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

            return diagnostic
        except Exception as e:
            raise OperationError(f"Failed to perform diagnostics: {str(e)}")