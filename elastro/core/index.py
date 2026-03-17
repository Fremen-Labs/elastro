"""
Index management module.

This module provides functionality for managing Elasticsearch indices.
"""

from typing import Dict, Optional, Any, List, Union
from elastro.core.client import ElasticsearchClient
from elastro.core.base import BaseManager
from elastro.core.errors import ElasticIndexError, ValidationError
from elastro.core.logger import get_logger

logger = get_logger(__name__)


class IndexManager(BaseManager):
    """
    Manager for Elasticsearch index operations.

    This class provides methods for creating, updating, and managing Elasticsearch indices.
    """

    def create(
        self,
        name: str,
        settings: Optional[Dict[str, Any]] = None,
        mappings: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Create a new Elasticsearch index.

        Args:
            name: Name of the index
            settings: Index settings
            mappings: Index mappings

        Returns:
            Creation response
        """
        if not name:
            raise ValidationError("Index name is required")

        # Prepare request body
        body: Dict[str, Any] = {}

        # Handle case where settings contains both settings and mappings
        if settings and "mappings" in settings and mappings is None:
            mappings = settings.get("mappings")
            if "settings" in settings:
                settings = settings.get("settings")

        # Process settings
        if settings:
            try:
                self.validator.validate_index_settings(settings)
                body["settings"] = settings
            except ValidationError as e:
                logger.error(f"Invalid index settings for {name}: {str(e)}")
                raise ValidationError(f"Invalid index settings: {str(e)}")

        # Process mappings
        if mappings:
            try:
                self.validator.validate_index_mappings(mappings)
                body["mappings"] = mappings
            except ValidationError as e:
                logger.error(f"Invalid index mappings for {name}: {str(e)}")
                raise ValidationError(f"Invalid index mappings: {str(e)}")

        try:
            logger.info(f"Creating index '{name}'...")
            self._ensure_connected()
            response = self._client.get_client().indices.create(index=name, body=body)
            logger.info(f"Index '{name}' created successfully")
            return self._handle_response(response)
        except Exception as e:
            logger.error(f"Failed to create index '{name}': {str(e)}")
            raise ElasticIndexError(f"Failed to create index '{name}': {str(e)}")

    def exists(self, name: str) -> bool:
        """
        Check if an index exists.

        Args:
            name: Name of the index

        Returns:
            True if index exists, False otherwise
        """
        if not name:
            raise ValidationError("Index name is required")

        try:
            self._ensure_connected()
            # exists() returns a boolean in the python client usually, but types might say HeadApiResponse
            exists = self._client.get_client().indices.exists(index=name)
            logger.debug(f"Index '{name}' exists: {exists}")
            # Ensure boolean return
            if hasattr(exists, "body"):
                return bool(exists.body)
            return bool(exists)
        except Exception as e:
            logger.error(f"Failed to check if index '{name}' exists: {str(e)}")
            raise ElasticIndexError(
                f"Failed to check if index '{name}' exists: {str(e)}"
            )

    def get(self, name: str) -> Any:
        """
        Get index information.

        Args:
            name: Name of the index

        Returns:
            Index information
        """
        if not name:
            raise ValidationError("Index name is required")

        try:
            if not self.exists(name):
                raise ElasticIndexError(f"Index '{name}' does not exist")

            self._ensure_connected()
            response = self._client.get_client().indices.get(index=name)
            return self._handle_response(response)
        except ElasticIndexError:
            raise
        except Exception as e:
            logger.error(f"Failed to get index '{name}': {str(e)}")
            raise ElasticIndexError(f"Failed to get index '{name}': {str(e)}")

    def update(self, name: str, settings: Dict[str, Any]) -> Any:
        """
        Update index settings.

        Args:
            name: Name of the index
            settings: Updated index settings

        Returns:
            Update response
        """
        if not name:
            raise ValidationError("Index name is required")

        if not settings:
            raise ValidationError("Settings are required for update")

        try:
            self.validator.validate_index_settings(settings)
        except ValidationError as e:
            logger.error(f"Invalid index settings for {name}: {str(e)}")
            raise ValidationError(f"Invalid index settings: {str(e)}")

        try:
            if not self.exists(name):
                raise ElasticIndexError(f"Index '{name}' does not exist")

            logger.info(f"Updating settings for index '{name}'")
            self._ensure_connected()
            # Unlike create, update expects the settings without the 'settings' wrapper
            response = self._client.get_client().indices.put_settings(
                index=name, body=settings
            )
            return self._handle_response(response)
        except ElasticIndexError:
            raise
        except Exception as e:
            logger.error(f"Failed to update index '{name}': {str(e)}")
            raise ElasticIndexError(f"Failed to update index '{name}': {str(e)}")

    def delete(self, name: str) -> Any:
        """
        Delete an index.

        Args:
            name: Name of the index

        Returns:
            Deletion response
        """
        if not name:
            raise ValidationError("Index name is required")

        try:
            if not self.exists(name):
                raise ElasticIndexError(f"Index '{name}' does not exist")

            logger.info(f"Deleting index '{name}'")
            self._ensure_connected()
            response = self._client.get_client().indices.delete(index=name)
            return self._handle_response(response)
        except ElasticIndexError:
            raise
        except Exception as e:
            logger.error(f"Failed to delete index '{name}': {str(e)}")
            raise ElasticIndexError(f"Failed to delete index '{name}': {str(e)}")

    def open(self, name: str) -> Any:
        """
        Open an index.

        Args:
            name: Name of the index

        Returns:
            Open response
        """
        if not name:
            raise ValidationError("Index name is required")

        try:
            if not self.exists(name):
                raise ElasticIndexError(f"Index '{name}' does not exist")

            logger.info(f"Opening index '{name}'")
            self._ensure_connected()
            response = self._client.get_client().indices.open(index=name)
            return self._handle_response(response)
        except ElasticIndexError:
            raise
        except Exception as e:
            logger.error(f"Failed to open index '{name}': {str(e)}")
            raise ElasticIndexError(f"Failed to open index '{name}': {str(e)}")

    def close(self, name: str) -> Any:
        """
        Close an index.

        Args:
            name: Name of the index

        Returns:
            Close response
        """
        if not name:
            raise ValidationError("Index name is required")

        try:
            if not self.exists(name):
                raise ElasticIndexError(f"Index '{name}' does not exist")

            logger.info(f"Closing index '{name}'")
            self._ensure_connected()
            response = self._client.get_client().indices.close(index=name)
            return self._handle_response(response)
        except ElasticIndexError:
            raise
        except Exception as e:
            logger.error(f"Failed to close index '{name}': {str(e)}")
            raise ElasticIndexError(f"Failed to close index '{name}': {str(e)}")

    def list(self, pattern: str = "*", verbose: bool = False) -> List[Dict[str, Any]]:
        """
        List indices matching a pattern.

        Args:
            pattern: Index pattern to match (default: "*")
            verbose: Whether to include extensive index details (default: False)

        Returns:
            List of dictionaries containing index details (name, health, status, docs.count, etc.)
        """
        try:
            self._ensure_connected()
            # use cat.indices for efficient summary
            # headers: health, status, index, uuid, pri, rep, docs.count, docs.deleted, store.size, pri.store.size
            response = self._client.get_client().cat.indices(
                index=pattern, format="json"
            )

            # The Elasticsearch python client returns a ListAPIResponse which is a list-like object
            # Convert to standard list of dicts
            result: List[Dict[str, Any]] = []
            
            raw_data = self._handle_response(response)

            # If raw_data is just a list, great.
            if isinstance(raw_data, list):
                result = raw_data

            logger.debug(f"Listed {len(result)} indices with pattern '{pattern}'")
            return result

        except Exception as e:
            logger.error(f"Failed to list indices with pattern '{pattern}': {str(e)}")
            raise ElasticIndexError(f"Failed to list indices: {str(e)}")

    def allocation_explain(self, name: str) -> Dict[str, Any]:
        """
        Explain allocation for an index.

        Args:
            name: Name of the index

        Returns:
            Allocation explanation dictionary
        """
        if not name:
            raise ValidationError("Index name is required")

        try:
            # First, we must find a specific unassigned shard for this index.
            # The Elasticsearch API STRICTLY requires `shard` and `primary` when `index` is provided.
            self._ensure_connected()
            shards = self._client.get_client().cat.shards(index=name, format="json")
            unassigned = [
                s
                for s in shards
                if isinstance(s, dict) and s.get("state") == "UNASSIGNED"
            ]

            if not unassigned:
                return {
                    "allocate_explanation": "All shards are currently assigned.",
                    "unassigned_info": {"reason": "ASSIGNED"},
                }

            target_shard = unassigned[0]
            if not isinstance(target_shard, dict):
                return {
                    "allocate_explanation": "Error casting shard",
                    "unassigned_info": {},
                }
            shard_id = int(target_shard.get("shard", 0))
            is_primary = target_shard.get("prirep") == "p"

            self._ensure_connected()
            response = self._client.get_client().cluster.allocation_explain(
                body={"index": name, "shard": shard_id, "primary": is_primary}
            )
            return self._handle_response(response)
        except Exception as e:
            logger.error(f"Failed to explain allocation for index '{name}': {str(e)}")
            raise ElasticIndexError(f"Failed to explain allocation: {str(e)}")

    def reroute(self, retry_failed: bool = True) -> Any:
        """
        Reroute unassigned shards.

        Args:
            retry_failed: Whether to retry allocation of failed shards

        Returns:
            Reroute response
        """
        try:
            self._ensure_connected()
            response = self._client.get_client().cluster.reroute(
                retry_failed=retry_failed
            )
            return self._handle_response(response)
        except Exception as e:
            logger.error(f"Failed to reroute cluster: {str(e)}")
            raise ElasticIndexError(f"Failed to reroute cluster: {str(e)}")
