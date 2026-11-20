"""Index, search, and delete_by_query against a named agent index."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Union

from pydantic import BaseModel

from elastro.agent.models import dump_payload
from elastro.core.base import BaseManager
from elastro.core.errors import ElasticModuleError, OperationError, ValidationError
from elastro.core.logger import get_logger

logger = get_logger(__name__)


class AgentStore(BaseManager):
    """Thin ES document store for agent memory, telemetry, and tools."""

    def _es(self) -> Any:
        self._ensure_connected()
        return self._client.get_client()

    def index(
        self,
        index: str,
        document: Union[Mapping[str, Any], BaseModel],
        id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Index ``document`` into ``index``, optionally with a fixed id."""
        if not index:
            raise ValidationError("Index name cannot be empty")
        payload = dump_payload(document)
        if not payload:
            raise ValidationError("Document must be a non-empty dictionary")

        params: Dict[str, Any] = {"index": index, "document": payload}
        if id:
            params["id"] = id

        try:
            logger.debug("agent store index index=%s id=%s", index, id or "-")
            response = self._es().index(**params)
            return self._handle_response(response)
        except ElasticModuleError:
            raise
        except Exception as exc:
            logger.error(
                "agent store index failed index=%s: %s", index, exc, exc_info=True
            )
            raise OperationError(f"Failed to index into {index}: {exc}") from exc

    def search(self, index: str, body: Mapping[str, Any]) -> Dict[str, Any]:
        """Run ``body`` against ``index`` and return the search response."""
        if not index:
            raise ValidationError("Index name cannot be empty")
        if not body:
            raise ValidationError("Search body cannot be empty")

        try:
            logger.debug("agent store search index=%s", index)
            response = self._es().search(index=index, body=dict(body))
            return self._handle_response(response)
        except ElasticModuleError:
            raise
        except Exception as exc:
            logger.error(
                "agent store search failed index=%s: %s", index, exc, exc_info=True
            )
            raise OperationError(f"Failed to search {index}: {exc}") from exc

    def delete_by_query(self, index: str, body: Mapping[str, Any]) -> Dict[str, Any]:
        """Run delete_by_query on ``index`` with ``body``."""
        if not index:
            raise ValidationError("Index name cannot be empty")
        if not body:
            raise ValidationError("Delete query cannot be empty")

        try:
            logger.debug("agent store delete_by_query index=%s", index)
            response = self._es().delete_by_query(index=index, body=dict(body))
            return self._handle_response(response)
        except ElasticModuleError:
            raise
        except Exception as exc:
            logger.error(
                "agent store delete_by_query failed index=%s: %s",
                index,
                exc,
                exc_info=True,
            )
            raise OperationError(
                f"Failed to delete_by_query on {index}: {exc}"
            ) from exc
