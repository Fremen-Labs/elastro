"""Base manager module.

This module provides the BaseManager class which centralizes common patterns
such as response parsing, validator instantiation, and connection verification
for all Elasticsearch operation managers.
"""

from typing import Any, Dict
from elastro.core.client import ElasticsearchClient
from elastro.core.validation import Validator


class BaseManager:
    """Base manager for inheriting common Elasticsearch operations."""

    def __init__(self, client: ElasticsearchClient):
        """
        Initialize the base manager.

        Args:
            client: ElasticsearchClient instance
        """
        self._client = client
        self.validator = Validator()

    def _ensure_connected(self) -> None:
        """Securely verify the client is connected before native API routing."""
        if not self._client.is_connected():
            self._client.connect()

    def _handle_response(self, response: Any) -> Dict[str, Any]:
        """Normalize the Elasticsearch payload response into a standard Python dictionary.

        Elasticsearch handles both raw dicts and `ObjectApiResponse` objects depending
        on the exact API version and method. This removes the `hasattr` boilerplate
        historically scattered across the managers.

        Args:
            response: The raw response returned directly from the ES index execution.

        Returns:
            The normalized dictionary payload.
        """
        if hasattr(response, "body"):
            return response.body  # type: ignore
        return dict(response)
