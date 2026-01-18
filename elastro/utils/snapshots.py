"""Snapshot and restore utilities for Elasticsearch."""

from typing import Dict, List, Any, Optional, Union
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict

from elastro.core.client import ElasticsearchClient
from elastro.core.errors import OperationError


class SnapshotConfig(BaseModel):
    """Pydantic model for snapshot configuration validation."""

    name: str
    indices: Optional[List[str]] = None
    ignore_unavailable: bool = False
    include_global_state: bool = True
    partial: bool = False
    wait_for_completion: bool = False

    model_config = ConfigDict(extra="allow")


class RepositoryConfig(BaseModel):
    """Pydantic model for repository configuration validation."""

    name: str
    type: str
    settings: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class SnapshotManager:
    """Manager for Elasticsearch snapshot and restore operations.

    This class provides methods to create and manage snapshot repositories,
    create snapshots, and restore from snapshots.
    """

    def __init__(self, client: ElasticsearchClient):
        """Initialize the SnapshotManager.

        Args:
            client: The Elasticsearch client instance.
        """
        self._client = client
        self._es = client.client

    def create_repository(
        self, repo_config: Union[Dict[str, Any], RepositoryConfig]
    ) -> bool:
        """Create a snapshot repository.

                Args:
        repo_config: Repository configuration as a dict or RepositoryConfig instance.

                Returns:
                    bool: True if repository was created successfully.

                Raises:
                    OperationError: If repository creation fails.
        """
        try:
            config: RepositoryConfig
            if isinstance(repo_config, dict):
                config = RepositoryConfig(**repo_config)
            else:
                config = repo_config

            response = self._es.snapshot.create_repository(
                repository=config.name,
                body={"type": config.type, "settings": config.settings},
            )
            return bool(response.get("acknowledged", False))
        except Exception as e:
            # We need to access name safely if config creation failed (hard to do cleanly)
            # but usually it fails in create_repository call
            repo_name = (
                repo_config.get("name")
                if isinstance(repo_config, dict)
                else repo_config.name
            )
            raise OperationError(f"Failed to create repository {repo_name}: {str(e)}")

    def delete_repository(self, name: str) -> bool:
        """Delete a snapshot repository.

        Args:
            name: Repository name to delete.

        Returns:
            bool: True if repository was deleted successfully.

        Raises:
            OperationError: If repository deletion fails.
        """
        try:
            response = self._es.snapshot.delete_repository(repository=name)
            return response.get("acknowledged", False)
        except Exception as e:
            raise OperationError(f"Failed to delete repository {name}: {str(e)}")

    def get_repository(self, name: Optional[str] = None) -> Dict[str, Any]:
        """Get repository information.

                Args:
        name: Optional repository name. If not provided, all repositories will be
        returned.

                Returns:
                    dict: Repository information.

                Raises:
                    OperationError: If repository retrieval fails.
        """
        try:
            if name:
                return self._es.snapshot.get_repository(repository=name)
            else:
                return self._es.snapshot.get_repository()
        except Exception as e:
            raise OperationError(f"Failed to get repository information: {str(e)}")

    def create_snapshot(
        self, repo_name: str, snapshot_config: Union[Dict[str, Any], SnapshotConfig]
    ) -> Dict[str, Any]:
        """Create a snapshot in the specified repository.

                Args:
                    repo_name: Repository name where the snapshot will be created.
        snapshot_config: Snapshot configuration as a dict or SnapshotConfig instance.

                Returns:
                    dict: Snapshot creation response.

                Raises:
                    OperationError: If snapshot creation fails.
        """
        try:
            config: SnapshotConfig
            if isinstance(snapshot_config, dict):
                config = SnapshotConfig(**snapshot_config)
            else:
                config = snapshot_config

            body: Dict[str, Any] = {
                "ignore_unavailable": config.ignore_unavailable,
                "include_global_state": config.include_global_state,
                "partial": config.partial,
            }

            if config.indices:
                body["indices"] = ",".join(config.indices)

            response = self._es.snapshot.create(
                repository=repo_name,
                snapshot=config.name,
                body=body,
                wait_for_completion=config.wait_for_completion,
            )
            return dict(response)
        except Exception as e:
            snap_name = (
                snapshot_config.get("name")
                if isinstance(snapshot_config, dict)
                else snapshot_config.name
            )
            raise OperationError(f"Failed to create snapshot {snap_name}: {str(e)}")

    def delete_snapshot(self, repo_name: str, snapshot_name: str) -> bool:
        """Delete a snapshot.

        Args:
            repo_name: Repository name containing the snapshot.
            snapshot_name: Name of the snapshot to delete.

        Returns:
            bool: True if snapshot was deleted successfully.

        Raises:
            OperationError: If snapshot deletion fails.
        """
        try:
            response = self._es.snapshot.delete(
                repository=repo_name, snapshot=snapshot_name
            )
            return response.get("acknowledged", False)
        except Exception as e:
            raise OperationError(f"Failed to delete snapshot {snapshot_name}: {str(e)}")

    def get_snapshot(
        self, repo_name: str, snapshot_name: str = "_all"
    ) -> Dict[str, Any]:
        """Get snapshot information.

                Args:
                    repo_name: Repository name containing the snapshot.
        snapshot_name: Name of the snapshot to retrieve, defaults to all snapshots.

                Returns:
                    dict: Snapshot information.

                Raises:
                    OperationError: If snapshot retrieval fails.
        """
        try:
            return self._es.snapshot.get(repository=repo_name, snapshot=snapshot_name)
        except Exception as e:
            raise OperationError(f"Failed to get snapshot information: {str(e)}")

    def restore_snapshot(
        self,
        repo_name: str,
        snapshot_name: str,
        indices: Optional[List[str]] = None,
        rename_pattern: Optional[str] = None,
        rename_replacement: Optional[str] = None,
        wait_for_completion: bool = False,
    ) -> Dict[str, Any]:
        """Restore a snapshot.

                Args:
                    repo_name: Repository name containing the snapshot.
                    snapshot_name: Name of the snapshot to restore.
                    indices: Optional list of indices to restore.
                    rename_pattern: Optional rename pattern for restored indices.
        rename_replacement: Optional rename replacement for restored indices.
        wait_for_completion: Whether to wait for the restore operation to complete.

                Returns:
                    dict: Restore operation response.

                Raises:
                    OperationError: If snapshot restoration fails.
        """
        try:
            body = {}
            if indices:
                body["indices"] = ",".join(indices)
            if rename_pattern and rename_replacement:
                body["rename_pattern"] = rename_pattern
                body["rename_replacement"] = rename_replacement

            return self._es.snapshot.restore(
                repository=repo_name,
                snapshot=snapshot_name,
                body=body,
                wait_for_completion=wait_for_completion,
            )
        except Exception as e:
            raise OperationError(
                f"Failed to restore snapshot {snapshot_name}: {str(e)}"
            )

    def get_snapshot_status(
        self, repo_name: Optional[str] = None, snapshot_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get snapshot status.

        Args:
            repo_name: Optional repository name.
            snapshot_name: Optional snapshot name.

        Returns:
            dict: Snapshot status information.

        Raises:
            OperationError: If status retrieval fails.
        """
        try:
            if repo_name and snapshot_name:
                return self._es.snapshot.status(
                    repository=repo_name, snapshot=snapshot_name
                )
            elif repo_name:
                return self._es.snapshot.status(repository=repo_name)
            else:
                return self._es.snapshot.status()
        except Exception as e:
            raise OperationError(f"Failed to get snapshot status: {str(e)}")
