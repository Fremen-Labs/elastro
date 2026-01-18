"""Alias management utilities for Elasticsearch."""

from typing import Dict, List, Any, Union, Optional

from pydantic import BaseModel, Field, ConfigDict

from elastro.core.client import ElasticsearchClient
from elastro.core.errors import OperationError


class AliasAction(BaseModel):
    """Pydantic model for alias action validation."""

    add: Optional[Dict[str, Any]] = None
    remove: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="allow")


class AliasManager:
    """Manager for Elasticsearch index aliases operations.

    This class provides methods to create, get, update, and delete index aliases.
    """

    def __init__(self, client: ElasticsearchClient):
        """Initialize the AliasManager.

        Args:
            client: The Elasticsearch client instance.
        """
        self._client = client
        self._es = client.client

    def create(
        self,
        name: str,
        index: str,
        filter_query: Optional[Dict[str, Any]] = None,
        routing: Optional[str] = None,
        is_write_index: bool = False,
    ) -> bool:
        """Create a new index alias.

        Args:
            name: The alias name.
            index: The index name to associate with the alias.
            filter_query: Optional filter query for the alias.
            routing: Optional routing value.

        Returns:
            bool: True if alias was created successfully.

        Raises:
            OperationError: If alias creation fails.
        """
        try:
            body: Dict[str, Any] = {}
            if filter_query:
                body["filter"] = filter_query
            if routing:
                body["routing"] = routing
            if is_write_index:
                body["is_write_index"] = is_write_index

            response = self._es.indices.put_alias(index=index, name=name, body=body)
            return response.get("acknowledged", False)
        except Exception as e:
            raise OperationError(f"Failed to create alias {name}: {str(e)}")

    def get(
        self, name: Optional[str] = None, index: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get alias information.

                Args:
        name: Optional alias name. If not provided, all aliases will be returned.
                    index: Optional index name to filter by.

                Returns:
                    dict: Alias information mapped by index.

                Raises:
                    OperationError: If alias retrieval fails.
        """
        try:
            if name and index:
                return self._es.indices.get_alias(name=name, index=index)
            elif name:
                return self._es.indices.get_alias(name=name)
            elif index:
                return self._es.indices.get_alias(index=index)
            else:
                return self._es.indices.get_alias()
        except Exception as e:
            raise OperationError(f"Failed to get alias information: {str(e)}")

    def exists(self, name: str, index: Optional[str] = None) -> bool:
        """Check if an alias exists.

        Args:
            name: Alias name to check.
            index: Optional index name to check against.

        Returns:
            bool: True if alias exists, False otherwise.
        """
        try:
            if index:
                return self._es.indices.exists_alias(name=name, index=index)
            else:
                return self._es.indices.exists_alias(name=name)
        except Exception:
            return False

    def delete(self, name: str, index: Optional[str] = None) -> bool:
        """Delete an alias.

        Args:
            name: Alias name to delete.
            index: Optional index name to delete the alias from.

        Returns:
            bool: True if alias was deleted successfully.

        Raises:
            OperationError: If alias deletion fails.
        """
        try:
            response = self._es.indices.delete_alias(
                name=name, index=index if index else "*"
            )
            return response.get("acknowledged", False)
        except Exception as e:
            raise OperationError(f"Failed to delete alias {name}: {str(e)}")

    def update(self, actions: List[Union[Dict[str, Any], AliasAction]]) -> bool:
        """Update aliases with multiple actions in a single atomic operation.

        Args:
            actions: List of alias actions (add or remove).

        Returns:
            bool: True if update was successful.

        Raises:
            OperationError: If update fails.
        """
        try:
            validated_actions = []
            for action in actions:
                if isinstance(action, dict):
                    action = AliasAction(**action)
                if action.add:
                    validated_actions.append({"add": action.add})
                if action.remove:
                    validated_actions.append({"remove": action.remove})

            response = self._es.indices.update_aliases(
                body={"actions": validated_actions}
            )
            return response.get("acknowledged", False)
        except Exception as e:
            raise OperationError(f"Failed to update aliases: {str(e)}")

    def list(
        self, index: Optional[str] = None, name: Optional[str] = None
    ) -> List[str]:
        """List all aliases or aliases for a specific index.

        Args:
            index: Optional index name to filter by.

        Returns:
            list: List of alias names.

        Raises:
            OperationError: If listing aliases fails.
        """
        try:
            if index:
                response = self._es.indices.get_alias(
                    index=index, name=name if name else "*"
                )
            elif name:
                response = self._es.indices.get_alias(name=name)
            else:
                response = self._es.indices.get_alias()

            aliases = set()
            for idx_aliases in response.values():
                aliases.update(idx_aliases.get("aliases", {}).keys())

            return list(aliases)
        except Exception as e:
            raise OperationError(f"Failed to list aliases: {str(e)}")
