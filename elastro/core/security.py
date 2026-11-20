"""Read-only native-realm security (RBAC) operations."""

from typing import Any, Dict, Optional

from elastro.core.base import BaseManager
from elastro.core.errors import OperationError
from elastro.core.logger import get_logger

logger = get_logger(__name__)


class SecurityManager(BaseManager):
    """List native realm users and roles. This manager is read-only."""

    def get_users(self, username: Optional[str] = None) -> Dict[str, Any]:
        """Return native realm users, optionally filtered by username.

        The Elasticsearch user document is not logged; it may contain metadata.
        """
        logger.debug("security.get_user username=%s", username or "*")
        try:
            self._ensure_connected()
            es = self._client.get_client()
            if username:
                response = es.security.get_user(username=username)
            else:
                response = es.security.get_user()
            return self._handle_response(response)
        except Exception as exc:
            logger.error("security get_user failed: %s", exc, exc_info=True)
            raise OperationError(f"Failed to list users: {exc}") from exc

    def get_roles(self, name: Optional[str] = None) -> Dict[str, Any]:
        """Return cluster roles, optionally filtered by role name."""
        logger.debug("security.get_role name=%s", name or "*")
        try:
            self._ensure_connected()
            es = self._client.get_client()
            if name:
                response = es.security.get_role(name=name)
            else:
                response = es.security.get_role()
            return self._handle_response(response)
        except Exception as exc:
            logger.error("security get_role failed: %s", exc, exc_info=True)
            raise OperationError(f"Failed to list roles: {exc}") from exc
