"""Stored script and painless execute operations."""

from typing import Any, Dict

from elastro.core.base import BaseManager
from elastro.core.errors import OperationError, ValidationError
from elastro.core.logger import get_logger

logger = get_logger(__name__)

_EXECUTE_PATH = "/_scripts/painless/_execute"
_JSON_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
}


class ScriptManager(BaseManager):
    """Manager for stored scripts and painless ``_execute``."""

    def list_scripts(self) -> Dict[str, Any]:
        """Return stored scripts from cluster state metadata."""
        try:
            logger.debug("script.list")
            self._ensure_connected()
            response = self._client.get_client().cluster.state(
                metric="metadata", filter_path="metadata.stored_scripts"
            )
            body = self._handle_response(response)
            stored = body.get("metadata", {}).get("stored_scripts") or {}
            return dict(stored) if isinstance(stored, dict) else {}
        except Exception as exc:
            logger.error("script list failed: %s", exc, exc_info=True)
            raise OperationError(f"Failed to list scripts: {exc}") from exc

    def get_script(self, script_id: str) -> Dict[str, Any]:
        """Return a stored script by id."""
        if not script_id:
            raise ValidationError("Script id is required")
        try:
            logger.debug("script.get id=%s", script_id)
            self._ensure_connected()
            response = self._client.get_client().get_script(id=script_id)
            return self._handle_response(response)
        except Exception as exc:
            logger.error("script get failed id=%s: %s", script_id, exc, exc_info=True)
            raise OperationError(f"Failed to get script: {exc}") from exc

    def put_script(
        self, script_id: str, source: str, *, lang: str = "painless"
    ) -> Dict[str, Any]:
        """Create or update a stored script."""
        if not script_id:
            raise ValidationError("Script id is required")
        body = {"script": {"lang": lang, "source": source}}
        try:
            logger.debug("script.put id=%s lang=%s", script_id, lang)
            self._ensure_connected()
            response = self._client.get_client().put_script(id=script_id, body=body)
            return self._handle_response(response)
        except Exception as exc:
            logger.error("script put failed id=%s: %s", script_id, exc, exc_info=True)
            raise OperationError(f"Failed to put script: {exc}") from exc

    def delete_script(self, script_id: str) -> Dict[str, Any]:
        """Delete a stored script by id."""
        if not script_id:
            raise ValidationError("Script id is required")
        try:
            logger.debug("script.delete id=%s", script_id)
            self._ensure_connected()
            response = self._client.get_client().delete_script(id=script_id)
            return self._handle_response(response)
        except Exception as exc:
            logger.error(
                "script delete failed id=%s: %s", script_id, exc, exc_info=True
            )
            raise OperationError(f"Failed to delete script: {exc}") from exc

    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Run a painless script via ``POST /_scripts/painless/_execute``."""
        try:
            logger.debug("script.execute path=%s", _EXECUTE_PATH)
            self._ensure_connected()
            response = self._client.get_client().perform_request(
                "POST",
                _EXECUTE_PATH,
                headers=_JSON_HEADERS,
                body=payload,
            )
            return self._handle_response(response)
        except Exception as exc:
            logger.error("script execute failed: %s", exc, exc_info=True)
            raise OperationError(f"Failed to execute painless script: {exc}") from exc
