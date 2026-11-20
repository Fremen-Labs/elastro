"""Snapshot and restore utilities for Elasticsearch.

Compatible adapter over ``elastro.core.snapshot.SnapshotManager``. Public
signatures stay stable for one minor: ``SnapshotConfig``, ``RepositoryConfig``,
``create_repository(repo_config)``, ``delete_snapshot(repo_name, snapshot_name)``,
and ``get_snapshot_status``.
"""

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from elastro.core.client import ElasticsearchClient
from elastro.core.errors import OperationError
from elastro.core.snapshot import SnapshotManager as CoreSnapshotManager


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
    """Adapter for snapshot operations with the historical utils signatures.

    HTTP is delegated to ``elastro.core.snapshot.SnapshotManager``. ``_es`` is
    retained for callers that read it; it is not used for transport.
    """

    def __init__(self, client: ElasticsearchClient):
        """Initialize the SnapshotManager.

        Args:
            client: The Elasticsearch client instance.
        """
        self._client = client
        self._es = client.client
        self._core = CoreSnapshotManager(client)

    def create_repository(
        self, repo_config: Union[Dict[str, Any], RepositoryConfig]
    ) -> bool:
        """Create a snapshot repository.

        Args:
            repo_config: Repository configuration as a dict or RepositoryConfig.

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
        except Exception as e:
            repo_name = (
                repo_config.get("name")
                if isinstance(repo_config, dict)
                else getattr(repo_config, "name", "unknown")
            )
            raise OperationError(
                f"Failed to create repository {repo_name}: {str(e)}"
            ) from e

        return self._core.create_repository(config.name, config.type, config.settings)

    def delete_repository(self, name: str) -> bool:
        """Delete a snapshot repository.

        Args:
            name: Repository name to delete.

        Returns:
            bool: True if repository was deleted successfully.

        Raises:
            OperationError: If repository deletion fails.
        """
        return self._core.delete_repository(name)

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
        if name:
            return self._core.get_repository(name)
        return self._core.list_repositories()

    def create_snapshot(
        self, repo_name: str, snapshot_config: Union[Dict[str, Any], SnapshotConfig]
    ) -> Dict[str, Any]:
        """Create a snapshot in the specified repository.

        Args:
            repo_name: Repository name where the snapshot will be created.
            snapshot_config: Snapshot configuration as a dict or SnapshotConfig.

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
        except Exception as e:
            snap_name = (
                snapshot_config.get("name")
                if isinstance(snapshot_config, dict)
                else getattr(snapshot_config, "name", "unknown")
            )
            raise OperationError(
                f"Failed to create snapshot {snap_name}: {str(e)}"
            ) from e

        indices = ",".join(config.indices) if config.indices else "_all"
        return self._core.create_snapshot(
            repository=repo_name,
            snapshot=config.name,
            indices=indices,
            ignore_unavailable=config.ignore_unavailable,
            include_global_state=config.include_global_state,
            wait_for_completion=config.wait_for_completion,
            partial=config.partial,
        )

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
        return self._core.delete_snapshot(repo_name, snapshot_name)

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
        return self._core.get_snapshots(repo_name, snapshot_name)

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
        indices_arg = ",".join(indices) if indices else "_all"
        return self._core.restore_snapshot(
            repo_name,
            snapshot_name,
            indices=indices_arg,
            rename_pattern=rename_pattern,
            rename_replacement=rename_replacement,
            wait_for_completion=wait_for_completion,
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
        return self._core.get_snapshot_status(
            repository=repo_name, snapshot=snapshot_name
        )
