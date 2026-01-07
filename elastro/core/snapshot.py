"""
Snapshot and Restore module.

This module provides functionality for managing Snapshot Repositories and Snapshots.
"""

from typing import Dict, List, Any, Optional
from elastro.core.client import ElasticsearchClient
from elastro.core.errors import OperationError, ValidationError
from elastro.core.logger import get_logger

logger = get_logger(__name__)


class SnapshotManager:
    """
    Manager for Snapshot and Restore operations.
    """

    def __init__(self, client: ElasticsearchClient):
        """
        Initialize the Snapshot manager.

        Args:
            client: ElasticsearchClient instance
        """
        self.client = client
        self._client = client

    # --- Repository Management ---

    def list_repositories(self) -> Dict[str, Any]:
        """
        List all snapshot repositories.

        Returns:
            Dict of repository definitions.
        """
        try:
            logger.debug("Listing snapshot repositories")
            # Get all repositories
            response = self.client.client.snapshot.get_repository(name="_all")
            return response.body if hasattr(response, 'body') else dict(response)
        except Exception as e:
            logger.error(f"Failed to list repositories: {str(e)}")
            raise OperationError(f"Failed to list repositories: {str(e)}")

    def get_repository(self, name: str) -> Dict[str, Any]:
        """
        Get a specific snapshot repository.

        Args:
            name: Repository name

        Returns:
            Repository definition
        """
        if not name:
            raise ValidationError("Repository name is required")

        try:
            logger.debug(f"Getting repository '{name}'")
            response = self.client.client.snapshot.get_repository(name=name)
            return response.body if hasattr(response, 'body') else dict(response)
        except Exception as e:
            logger.error(f"Failed to get repository '{name}': {str(e)}")
            raise OperationError(f"Failed to get repository '{name}': {str(e)}")

    def create_repository(self, name: str, repo_type: str, settings: Dict[str, Any]) -> bool:
        """
        Create or update a snapshot repository.

        Args:
            name: Repository name
            repo_type: Repository type (fs, s3, gcs, azure, etc)
            settings: Repository settings (location, compress, etc)

        Returns:
            True if acknowledged
        """
        if not name or not repo_type:
            raise ValidationError("Repository name and type are required")

        try:
            logger.info(f"Creating repository '{name}' (type={repo_type})")
            body = {
                "type": repo_type,
                "settings": settings
            }
            response = self.client.client.snapshot.create_repository(name=name, body=body)
            body_resp = response.body if hasattr(response, 'body') else dict(response)
            return body_resp.get("acknowledged", False)
        except Exception as e:
            logger.error(f"Failed to create repository '{name}': {str(e)}")
            raise OperationError(f"Failed to create repository '{name}': {str(e)}")

    def delete_repository(self, name: str) -> bool:
        """
        Delete a snapshot repository.

        Args:
            name: Repository name

        Returns:
            True if acknowledged
        """
        if not name:
            raise ValidationError("Repository name is required")

        try:
            logger.info(f"Deleting repository '{name}'")
            response = self.client.client.snapshot.delete_repository(name=name)
            body_resp = response.body if hasattr(response, 'body') else dict(response)
            return body_resp.get("acknowledged", False)
        except Exception as e:
            logger.error(f"Failed to delete repository '{name}': {str(e)}")
            raise OperationError(f"Failed to delete repository '{name}': {str(e)}")

    # --- Snapshot Management ---

    def list_snapshots(self, repository: str) -> List[Dict[str, Any]]:
        """
        List all snapshots in a repository.

        Args:
            repository: Repository name

        Returns:
            List of snapshot info dicts
        """
        if not repository:
            raise ValidationError("Repository name is required")

        try:
            logger.debug(f"Listing snapshots in '{repository}'")
            response = self.client.client.snapshot.get(repository=repository, snapshot="_all")
            body = response.body if hasattr(response, 'body') else dict(response)
            return body.get("snapshots", [])
        except Exception as e:
            logger.error(f"Failed to list snapshots in '{repository}': {str(e)}")
            raise OperationError(f"Failed to list snapshots in '{repository}': {str(e)}")

    def get_snapshot(self, repository: str, snapshot: str) -> Dict[str, Any]:
        """
        Get details of a specific snapshot.

        Args:
            repository: Repository name
            snapshot: Snapshot name

        Returns:
            Snapshot details
        """
        if not repository or not snapshot:
            raise ValidationError("Repository and Snapshot names are required")

        try:
            logger.debug(f"Getting snapshot '{snapshot}' from '{repository}'")
            response = self.client.client.snapshot.get(repository=repository, snapshot=snapshot)
            body = response.body if hasattr(response, 'body') else dict(response)
            snapshots = body.get("snapshots", [])
            if snapshots:
                return snapshots[0]
            raise OperationError(f"Snapshot '{snapshot}' not found")
        except Exception as e:
            logger.error(f"Failed to get snapshot '{snapshot}': {str(e)}")
            raise OperationError(f"Failed to get snapshot '{snapshot}': {str(e)}")

    def create_snapshot(
        self, 
        repository: str, 
        snapshot: str, 
        indices: str = "_all", 
        ignore_unavailable: bool = False,
        include_global_state: bool = False,
        wait_for_completion: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a snapshot.

        Args:
            repository: Repository name
            snapshot: Snapshot name
            indices: Comma-separated list of indices (default: _all)
            ignore_unavailable: Whether to ignore unavailable indices
            include_global_state: Whether to include cluster state
            wait_for_completion: Whether to wait for snapshot to complete
            metadata: Optional metadata to add to snapshot

        Returns:
            Snapshot response (status or info)
        """
        if not repository or not snapshot:
             raise ValidationError("Repository and Snapshot names are required")

        try:
            logger.info(f"Creating snapshot '{snapshot}' in '{repository}'")
            body = {
                "indices": indices,
                "ignore_unavailable": ignore_unavailable,
                "include_global_state": include_global_state,
            }
            if metadata:
                body["metadata"] = metadata

            response = self.client.client.snapshot.create(
                repository=repository, 
                snapshot=snapshot, 
                body=body,
                wait_for_completion=wait_for_completion
            )
            return response.body if hasattr(response, 'body') else dict(response)
        except Exception as e:
            logger.error(f"Failed to create snapshot '{snapshot}': {str(e)}")
            raise OperationError(f"Failed to create snapshot '{snapshot}': {str(e)}")

    def delete_snapshot(self, repository: str, snapshot: str) -> bool:
        """
        Delete a snapshot.

        Args:
            repository: Repository name
            snapshot: Snapshot name

        Returns:
            True if acknowledged
        """
        if not repository or not snapshot:
            raise ValidationError("Repository and Snapshot names are required")

        try:
            logger.info(f"Deleting snapshot '{snapshot}' from '{repository}'")
            response = self.client.client.snapshot.delete(repository=repository, snapshot=snapshot)
            body = response.body if hasattr(response, 'body') else dict(response)
            return body.get("acknowledged", False)
        except Exception as e:
            logger.error(f"Failed to delete snapshot '{snapshot}': {str(e)}")
            raise OperationError(f"Failed to delete snapshot '{snapshot}': {str(e)}")

    def restore_snapshot(
        self, 
        repository: str, 
        snapshot: str, 
        indices: str = "_all", 
        rename_pattern: str = None, 
        rename_replacement: str = None,
        wait_for_completion: bool = False
    ) -> Dict[str, Any]:
        """
        Restore a snapshot.

        Args:
            repository: Repository name
            snapshot: Snapshot name
            indices: Indices to restore
            rename_pattern: Regex pattern for index renaming
            rename_replacement: Replacement string
            wait_for_completion: Whether to wait

        Returns:
            Restore response
        """
        if not repository or not snapshot:
            raise ValidationError("Repository and Snapshot names are required")

        try:
            logger.info(f"Restoring snapshot '{snapshot}' from '{repository}'")
            body = {
                "indices": indices,
            }
            if rename_pattern and rename_replacement:
                body["rename_pattern"] = rename_pattern
                body["rename_replacement"] = rename_replacement

            response = self.client.client.snapshot.restore(
                repository=repository,
                snapshot=snapshot,
                body=body,
                wait_for_completion=wait_for_completion
            )
            return response.body if hasattr(response, 'body') else dict(response)
        except Exception as e:
            logger.error(f"Failed to restore snapshot '{snapshot}': {str(e)}")
            raise OperationError(f"Failed to restore snapshot '{snapshot}': {str(e)}")
