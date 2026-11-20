"""Cluster settings and allocation-explain operations."""

from typing import Any, Dict, Optional

from elastro.core.base import BaseManager
from elastro.core.errors import OperationError, ValidationError
from elastro.core.logger import get_logger

logger = get_logger(__name__)

_ROUTING_ENABLE_VALUES = frozenset({"all", "primaries", "new_primaries", "none"})


class ClusterManager(BaseManager):
    """Transient cluster settings and allocation diagnostics."""

    def get_settings(self, *, flat_settings: bool = True) -> Dict[str, Any]:
        """Return persistent and transient cluster settings."""
        logger.debug("cluster.get_settings flat_settings=%s", flat_settings)
        try:
            self._ensure_connected()
            response = self._client.get_client().cluster.get_settings(
                flat_settings=flat_settings
            )
            return self._handle_response(response)
        except Exception as exc:
            logger.error("cluster get_settings failed: %s", exc, exc_info=True)
            raise OperationError(f"Failed to get cluster settings: {exc}") from exc

    def enable_routing(self, enable: str) -> Dict[str, Any]:
        """Set ``cluster.routing.allocation.enable`` as a transient setting."""
        if enable not in _ROUTING_ENABLE_VALUES:
            raise ValidationError(f"Invalid routing allocation enable value: {enable}")
        logger.info("cluster.enable_routing enable=%s", enable)
        body = {"transient": {"cluster.routing.allocation.enable": enable}}
        try:
            self._ensure_connected()
            response = self._client.get_client().cluster.put_settings(body=body)
            return self._handle_response(response)
        except Exception as exc:
            logger.error("cluster put_settings failed: %s", exc, exc_info=True)
            raise OperationError(f"Failed to update cluster settings: {exc}") from exc

    def allocation_explain(self, index: Optional[str] = None) -> Dict[str, Any]:
        """Explain shard allocation.

        Delegates to the health shards explain path so ``cluster allocation``
        and ``health shards --explain`` share one implementation.
        """
        logger.debug("cluster.allocation_explain index=%s", index or "*")
        try:
            from elastro.health.collectors.base import CollectContext
            from elastro.health.collectors.shards import (
                explain_allocation as health_explain,
            )

            ctx = CollectContext(
                client=self._client,
                options={"index": index} if index else {},
            )
            return health_explain(ctx, index_name=index)
        except OperationError:
            raise
        except Exception as exc:
            logger.error("cluster allocation_explain failed: %s", exc, exc_info=True)
            raise OperationError(f"Failed to explain allocation: {exc}") from exc
