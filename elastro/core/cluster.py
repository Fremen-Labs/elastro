"""Cluster settings and allocation-explain operations."""

from typing import Any, Dict, Optional

from elastro.core.base import BaseManager
from elastro.core.errors import OperationError, ValidationError
from elastro.core.index import IndexManager
from elastro.core.logger import get_logger

logger = get_logger(__name__)

_ROUTING_ENABLE_VALUES = frozenset({"all", "primaries", "new_primaries", "none"})
_NO_SHARD_MARKERS = ("no shard was specified", "no unassigned shards")


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

        When ``index`` is set, reuses ``IndexManager.allocation_explain`` so the
        index path matches health shards. The cluster-wide call is owned here.
        """
        logger.debug("cluster.allocation_explain index=%s", index or "*")
        if index:
            return IndexManager(self._client).allocation_explain(index)
        try:
            self._ensure_connected()
            response = self._client.get_client().cluster.allocation_explain()
            return self._handle_response(response)
        except Exception as exc:
            if _is_no_unassigned_shard(exc):
                logger.info("No unassigned shards to explain")
                return {"message": "no unassigned shards to explain"}
            logger.error("cluster allocation_explain failed: %s", exc, exc_info=True)
            raise OperationError(f"Failed to explain allocation: {exc}") from exc


def _is_no_unassigned_shard(exc: Exception) -> bool:
    """Return True for ES 400 'No shard was specified' (green, nothing to explain)."""
    message = str(exc).lower()
    if any(marker in message for marker in _NO_SHARD_MARKERS):
        return True
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error = body.get("error") or {}
        reason = str(error.get("reason") or "").lower()
        if any(marker in reason for marker in _NO_SHARD_MARKERS):
            return True
    return False
