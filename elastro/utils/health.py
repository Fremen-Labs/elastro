"""Health check and diagnostics utilities for Elasticsearch."""
from typing import Dict, List, Any, Optional, Union

from elastro.core.client import ElasticsearchClient
from elastro.core.errors import OperationError


class HealthManager:
    """Manager for Elasticsearch health and diagnostics operations.

    This class provides methods to check cluster health, node status,
    and perform various diagnostic operations.
    """

    def __init__(self, client: ElasticsearchClient):
        """Initialize the HealthManager.

        Args:
            client: The Elasticsearch client instance.
        """
        self._client = client
        self._es = client.client

    def cluster_health(self, index: Optional[str] = None,
                     level: str = "cluster",
                     timeout: str = "30s",
                     wait_for_status: Optional[str] = None) -> Dict[str, Any]:
        """Get cluster health information.

        Args:
            index: Optional index to get health for.
level: Health information detail level ('cluster', 'indices', or 'shards').
            timeout: Request timeout.

        Returns:
            dict: Cluster health information.

        Raises:
            OperationError: If health retrieval fails.
        """
        try:
            params = {
                "level": level,
                "timeout": timeout
            }

            if wait_for_status:
                params["wait_for_status"] = wait_for_status

            if index:
                return self._es.cluster.health(index=index, **params)
            else:
                return self._es.cluster.health(**params)
        except Exception as e:
            raise OperationError(f"Failed to get cluster health: {str(e)}")

    def node_stats(self, node_id: Optional[str] = None,
                 metrics: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get node statistics.

        Args:
            node_id: Optional node ID to get stats for.
            metrics: Optional list of metrics to retrieve.

        Returns:
            dict: Node statistics.

        Raises:
            OperationError: If node stats retrieval fails.
        """
        try:
            if node_id and metrics:
                return self._es.nodes.stats(node_id=node_id, metric=",".join(metrics))
            elif node_id:
                return self._es.nodes.stats(node_id=node_id)
            elif metrics:
                return self._es.nodes.stats(metric=",".join(metrics))
            else:
                return self._es.nodes.stats()
        except Exception as e:
            raise OperationError(f"Failed to get node stats: {str(e)}")

    def node_info(self, node_id: Optional[str] = None,
                metrics: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get node information.

        Args:
            node_id: Optional node ID to get info for.
            metrics: Optional list of metrics to retrieve.

        Returns:
            dict: Node information.

        Raises:
            OperationError: If node info retrieval fails.
        """
        try:
            if node_id and metrics:
                return self._es.nodes.info(node_id=node_id, metric=",".join(metrics))
            elif node_id:
                return self._es.nodes.info(node_id=node_id)
            elif metrics:
                return self._es.nodes.info(metric=",".join(metrics))
            else:
                return self._es.nodes.info()
        except Exception as e:
            raise OperationError(f"Failed to get node info: {str(e)}")

    def cluster_stats(self) -> Dict[str, Any]:
        """Get cluster statistics.

        Returns:
            dict: Cluster statistics.

        Raises:
            OperationError: If cluster stats retrieval fails.
        """
        try:
            return self._es.cluster.stats()
        except Exception as e:
            raise OperationError(f"Failed to get cluster stats: {str(e)}")

    def pending_tasks(self) -> List[Dict[str, Any]]:
        """Get pending cluster tasks.

        Returns:
            list: Pending tasks in the cluster.

        Raises:
            OperationError: If pending tasks retrieval fails.
        """
        try:
            return self._es.cluster.pending_tasks().get("tasks", [])
        except Exception as e:
            raise OperationError(f"Failed to get pending tasks: {str(e)}")

    def allocation_explain(self, index: Optional[str] = None,
                         shard: Optional[int] = None,
                         primary: bool = False) -> Dict[str, Any]:
        """Explain shard allocation decisions.

        Args:
            index: Optional index name.
            shard: Optional shard ID.
            primary: Whether to explain primary shard allocation.

        Returns:
            dict: Shard allocation explanation.

        Raises:
            OperationError: If explanation retrieval fails.
        """
        try:
            body = {}
            if index:
                body["index"] = index
            if shard is not None:
                body["shard"] = shard
            if primary:
                body["primary"] = primary

            if body:
                return self._es.cluster.allocation_explain(body=body)
            else:
                return self._es.cluster.allocation_explain()
        except Exception as e:
            raise OperationError(f"Failed to explain allocation: {str(e)}")

    def cluster_settings(self, include_defaults: bool = False) -> Dict[str, Any]:
        """Get cluster settings.

        Args:
            include_defaults: Whether to include default settings.

        Returns:
            dict: Cluster settings.

        Raises:
            OperationError: If settings retrieval fails.
        """
        try:
            return self._es.cluster.get_settings(include_defaults=include_defaults)
        except Exception as e:
            raise OperationError(f"Failed to get cluster settings: {str(e)}")

    def verify_repository(self, repository: str) -> bool:
        """Verify a snapshot repository.

        Args:
            repository: Repository name to verify.

        Returns:
            bool: True if repository verification succeeded.

        Raises:
            OperationError: If repository verification fails.
        """
        try:
            response = self._es.snapshot.verify_repository(repository=repository)
            return "nodes" in response
        except Exception as e:
            raise OperationError(f"Failed to verify repository {repository}: {str(e)}")

    def index_stats(self, index: Optional[str] = None) -> Dict[str, Any]:
        """Get index statistics.

        Args:
            index: Optional index name to get stats for.

        Returns:
            dict: Index statistics.

        Raises:
            OperationError: If stats retrieval fails.
        """
        try:
            if index:
                return self._es.indices.stats(index=index)
            else:
                return self._es.indices.stats()
        except Exception as e:
            raise OperationError(f"Failed to get index stats: {str(e)}")

    def diagnose(self) -> Dict[str, Any]:
        """Perform a basic diagnostic check on the cluster.

        Returns:
            dict: Diagnostic results.

        Raises:
            OperationError: If diagnostic fails.
        """
        try:
            diagnostic = {
                "cluster_health": self.cluster_health(),
                "nodes_count": len(self._es.nodes.info().get("nodes", {})),
                "indices_count": len(self._es.indices.get("*").keys()),
                "pending_tasks": len(self.pending_tasks())
            }

            # Add status assessment
            health_status = diagnostic["cluster_health"].get("status", "unknown")
            diagnostic["status"] = {
                "is_healthy": health_status == "green",
                "health_status": health_status,
                "has_pending_tasks": diagnostic["pending_tasks"] > 0
            }

            return diagnostic
        except Exception as e:
            raise OperationError(f"Failed to perform diagnostics: {str(e)}")
