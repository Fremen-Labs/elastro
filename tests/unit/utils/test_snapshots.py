"""Unit tests for snapshot management utilities."""

import pytest
from unittest.mock import MagicMock, patch

from elastro.core.client import ElasticsearchClient
from elastro.core.errors import OperationError
from elastro.utils.snapshots import SnapshotManager, SnapshotConfig, RepositoryConfig


@pytest.fixture
def mock_elasticsearch():
    """Return a mocked Elasticsearch client."""
    with patch("elasticsearch.Elasticsearch") as mock_es:
        mock_client = MagicMock()
        mock_es.return_value = mock_client
        yield mock_client


@pytest.fixture
def es_client(mock_elasticsearch):
    """Return an ElasticsearchClient instance with a mocked ES client."""
    client = ElasticsearchClient(hosts=["http://localhost:9200"])
    # Replace the _client with our mock
    client._client = mock_elasticsearch
    client._connected = True
    return client


@pytest.fixture
def snapshot_manager(es_client):
    """Return a SnapshotManager instance with a mocked client."""
    return SnapshotManager(es_client)


class TestSnapshotConfig:
    """Test suite for SnapshotConfig model."""

    def test_init_minimal(self):
        """Test initializing SnapshotConfig with minimal parameters."""
        config = SnapshotConfig(name="test-snapshot")
        assert config.name == "test-snapshot"
        assert config.indices is None
        assert config.ignore_unavailable is False
        assert config.include_global_state is True
        assert config.partial is False
        assert config.wait_for_completion is False

    def test_init_full(self):
        """Test initializing SnapshotConfig with all parameters."""
        config = SnapshotConfig(
            name="test-snapshot",
            indices=["index1", "index2"],
            ignore_unavailable=True,
            include_global_state=False,
            partial=True,
            wait_for_completion=True,
        )
        assert config.name == "test-snapshot"
        assert config.indices == ["index1", "index2"]
        assert config.ignore_unavailable is True
        assert config.include_global_state is False
        assert config.partial is True
        assert config.wait_for_completion is True


class TestRepositoryConfig:
    """Test suite for RepositoryConfig model."""

    def test_init_minimal(self):
        """Test initializing RepositoryConfig with minimal parameters."""
        config = RepositoryConfig(name="test-repo", type="fs")
        assert config.name == "test-repo"
        assert config.type == "fs"
        assert config.settings == {}

    def test_init_with_settings(self):
        """Test initializing RepositoryConfig with settings."""
        settings = {"location": "/backup/es_snapshots"}
        config = RepositoryConfig(name="test-repo", type="fs", settings=settings)
        assert config.name == "test-repo"
        assert config.type == "fs"
        assert config.settings == settings


class TestSnapshotManager:
    """Test suite for SnapshotManager class."""

    def test_init(self, es_client):
        """Test initializing SnapshotManager."""
        manager = SnapshotManager(es_client)
        assert manager._client == es_client
        assert manager._es == es_client.client

    def test_create_repository_success(self, snapshot_manager, mock_elasticsearch):
        """Test creating a repository successfully."""
        # Setup mock response
        mock_elasticsearch.snapshot.create_repository.return_value = {
            "acknowledged": True
        }

        # Test with dict config
        repo_config = {
            "name": "test-repo",
            "type": "fs",
            "settings": {"location": "/backup/es_snapshots"},
        }

        result = snapshot_manager.create_repository(repo_config)
        assert result is True
        mock_elasticsearch.snapshot.create_repository.assert_called_once_with(
            repository="test-repo",
            body={"type": "fs", "settings": {"location": "/backup/es_snapshots"}},
        )

        # Reset mock
        mock_elasticsearch.snapshot.create_repository.reset_mock()

        # Test with RepositoryConfig object
        repo_config = RepositoryConfig(
            name="test-repo", type="fs", settings={"location": "/backup/es_snapshots"}
        )

        result = snapshot_manager.create_repository(repo_config)
        assert result is True
        mock_elasticsearch.snapshot.create_repository.assert_called_once_with(
            repository="test-repo",
            body={"type": "fs", "settings": {"location": "/backup/es_snapshots"}},
        )

    def test_create_repository_error(self, snapshot_manager, mock_elasticsearch):
        """Test error handling when creating a repository."""
        # Setup mock to raise an exception
        mock_elasticsearch.snapshot.create_repository.side_effect = Exception(
            "Test error"
        )

        # Test error handling
        repo_config = RepositoryConfig(name="test-repo", type="fs")
        with pytest.raises(
            OperationError, match="Failed to create repository test-repo: Test error"
        ):
            snapshot_manager.create_repository(repo_config)

    def test_delete_repository_success(self, snapshot_manager, mock_elasticsearch):
        """Test deleting a repository successfully."""
        # Setup mock response
        mock_elasticsearch.snapshot.delete_repository.return_value = {
            "acknowledged": True
        }

        result = snapshot_manager.delete_repository("test-repo")
        assert result is True
        mock_elasticsearch.snapshot.delete_repository.assert_called_once_with(
            repository="test-repo"
        )

    def test_delete_repository_error(self, snapshot_manager, mock_elasticsearch):
        """Test error handling when deleting a repository."""
        # Setup mock to raise an exception
        mock_elasticsearch.snapshot.delete_repository.side_effect = Exception(
            "Test error"
        )

        with pytest.raises(
            OperationError, match="Failed to delete repository test-repo: Test error"
        ):
            snapshot_manager.delete_repository("test-repo")

    def test_get_repository_by_name(self, snapshot_manager, mock_elasticsearch):
        """Test getting a repository by name."""
        # Setup mock response
        mock_response = {
            "test-repo": {
                "type": "fs",
                "settings": {"location": "/backup/es_snapshots"},
            }
        }
        mock_elasticsearch.snapshot.get_repository.return_value = mock_response

        result = snapshot_manager.get_repository("test-repo")
        assert result == mock_response
        mock_elasticsearch.snapshot.get_repository.assert_called_once_with(
            repository="test-repo"
        )

    def test_get_all_repositories(self, snapshot_manager, mock_elasticsearch):
        """Test getting all repositories."""
        # Setup mock response
        mock_response = {
            "test-repo1": {
                "type": "fs",
                "settings": {"location": "/backup/es_snapshots1"},
            },
            "test-repo2": {
                "type": "fs",
                "settings": {"location": "/backup/es_snapshots2"},
            },
        }
        mock_elasticsearch.snapshot.get_repository.return_value = mock_response

        result = snapshot_manager.get_repository()
        assert result == mock_response
        mock_elasticsearch.snapshot.get_repository.assert_called_once_with()

    def test_get_repository_error(self, snapshot_manager, mock_elasticsearch):
        """Test error handling when getting repositories."""
        # Setup mock to raise an exception
        mock_elasticsearch.snapshot.get_repository.side_effect = Exception("Test error")

        with pytest.raises(
            OperationError, match="Failed to get repository information: Test error"
        ):
            snapshot_manager.get_repository()

    def test_create_snapshot_success(self, snapshot_manager, mock_elasticsearch):
        """Test creating a snapshot successfully."""
        # Setup mock response
        mock_response = {
            "accepted": True,
            "snapshot": {
                "name": "test-snapshot",
                "uuid": "XYZ123",
                "state": "IN_PROGRESS",
            },
        }
        mock_elasticsearch.snapshot.create.return_value = mock_response

        # Test with dict config
        snapshot_config = {
            "name": "test-snapshot",
            "indices": ["index1", "index2"],
            "wait_for_completion": False,
        }

        result = snapshot_manager.create_snapshot("test-repo", snapshot_config)
        assert result == mock_response
        mock_elasticsearch.snapshot.create.assert_called_once_with(
            repository="test-repo",
            snapshot="test-snapshot",
            body={
                "ignore_unavailable": False,
                "include_global_state": True,
                "partial": False,
                "indices": "index1,index2",
            },
            wait_for_completion=False,
        )

        # Reset mock
        mock_elasticsearch.snapshot.create.reset_mock()

        # Test with SnapshotConfig object
        snapshot_config = SnapshotConfig(
            name="test-snapshot",
            indices=["index1", "index2"],
            wait_for_completion=False,
        )

        result = snapshot_manager.create_snapshot("test-repo", snapshot_config)
        assert result == mock_response
        mock_elasticsearch.snapshot.create.assert_called_once_with(
            repository="test-repo",
            snapshot="test-snapshot",
            body={
                "ignore_unavailable": False,
                "include_global_state": True,
                "partial": False,
                "indices": "index1,index2",
            },
            wait_for_completion=False,
        )

    def test_create_snapshot_error(self, snapshot_manager, mock_elasticsearch):
        """Test error handling when creating a snapshot."""
        # Setup mock to raise an exception
        mock_elasticsearch.snapshot.create.side_effect = Exception("Test error")

        snapshot_config = SnapshotConfig(name="test-snapshot")
        with pytest.raises(
            OperationError, match="Failed to create snapshot test-snapshot: Test error"
        ):
            snapshot_manager.create_snapshot("test-repo", snapshot_config)

    def test_delete_snapshot_success(self, snapshot_manager, mock_elasticsearch):
        """Test deleting a snapshot successfully."""
        # Setup mock response
        mock_elasticsearch.snapshot.delete.return_value = {"acknowledged": True}

        result = snapshot_manager.delete_snapshot("test-repo", "test-snapshot")
        assert result is True
        mock_elasticsearch.snapshot.delete.assert_called_once_with(
            repository="test-repo", snapshot="test-snapshot"
        )

    def test_delete_snapshot_error(self, snapshot_manager, mock_elasticsearch):
        """Test error handling when deleting a snapshot."""
        # Setup mock to raise an exception
        mock_elasticsearch.snapshot.delete.side_effect = Exception("Test error")

        with pytest.raises(
            OperationError, match="Failed to delete snapshot test-snapshot: Test error"
        ):
            snapshot_manager.delete_snapshot("test-repo", "test-snapshot")

    def test_get_snapshot_by_name(self, snapshot_manager, mock_elasticsearch):
        """Test getting a snapshot by name."""
        # Setup mock response
        mock_response = {
            "snapshots": [
                {
                    "snapshot": "test-snapshot",
                    "uuid": "XYZ123",
                    "version_id": 7,
                    "version": "7.0.0",
                    "indices": ["index1", "index2"],
                    "state": "SUCCESS",
                }
            ]
        }
        mock_elasticsearch.snapshot.get.return_value = mock_response

        result = snapshot_manager.get_snapshot("test-repo", "test-snapshot")
        assert result == mock_response
        mock_elasticsearch.snapshot.get.assert_called_once_with(
            repository="test-repo", snapshot="test-snapshot"
        )

    def test_get_all_snapshots(self, snapshot_manager, mock_elasticsearch):
        """Test getting all snapshots from a repository."""
        # Setup mock response
        mock_response = {
            "snapshots": [
                {"snapshot": "snapshot1", "uuid": "ABC123", "state": "SUCCESS"},
                {"snapshot": "snapshot2", "uuid": "DEF456", "state": "SUCCESS"},
            ]
        }
        mock_elasticsearch.snapshot.get.return_value = mock_response

        result = snapshot_manager.get_snapshot("test-repo")
        assert result == mock_response
        mock_elasticsearch.snapshot.get.assert_called_once_with(
            repository="test-repo", snapshot="_all"
        )

    def test_get_snapshot_error(self, snapshot_manager, mock_elasticsearch):
        """Test error handling when getting snapshots."""
        # Setup mock to raise an exception
        mock_elasticsearch.snapshot.get.side_effect = Exception("Test error")

        with pytest.raises(
            OperationError, match="Failed to get snapshot information: Test error"
        ):
            snapshot_manager.get_snapshot("test-repo")

    def test_restore_snapshot_success(self, snapshot_manager, mock_elasticsearch):
        """Test restoring a snapshot successfully."""
        # Setup mock response
        mock_response = {"accepted": True}
        mock_elasticsearch.snapshot.restore.return_value = mock_response

        # Test minimal restore
        result = snapshot_manager.restore_snapshot("test-repo", "test-snapshot")
        assert result == mock_response
        mock_elasticsearch.snapshot.restore.assert_called_once_with(
            repository="test-repo",
            snapshot="test-snapshot",
            body={},
            wait_for_completion=False,
        )

        # Reset mock
        mock_elasticsearch.snapshot.restore.reset_mock()

        # Test with all parameters
        result = snapshot_manager.restore_snapshot(
            repo_name="test-repo",
            snapshot_name="test-snapshot",
            indices=["index1", "index2"],
            rename_pattern="(.+)",
            rename_replacement="restored_$1",
            wait_for_completion=True,
        )
        assert result == mock_response
        mock_elasticsearch.snapshot.restore.assert_called_once_with(
            repository="test-repo",
            snapshot="test-snapshot",
            body={
                "indices": "index1,index2",
                "rename_pattern": "(.+)",
                "rename_replacement": "restored_$1",
            },
            wait_for_completion=True,
        )

    def test_restore_snapshot_error(self, snapshot_manager, mock_elasticsearch):
        """Test error handling when restoring a snapshot."""
        # Setup mock to raise an exception
        mock_elasticsearch.snapshot.restore.side_effect = Exception("Test error")

        with pytest.raises(
            OperationError, match="Failed to restore snapshot test-snapshot: Test error"
        ):
            snapshot_manager.restore_snapshot("test-repo", "test-snapshot")

    def test_get_snapshot_status_all(self, snapshot_manager, mock_elasticsearch):
        """Test getting status for all snapshots."""
        # Setup mock response
        mock_response = {
            "snapshots": [
                {"snapshot": "snapshot1", "repository": "repo1", "state": "SUCCESS"},
                {
                    "snapshot": "snapshot2",
                    "repository": "repo2",
                    "state": "IN_PROGRESS",
                },
            ]
        }
        mock_elasticsearch.snapshot.status.return_value = mock_response

        result = snapshot_manager.get_snapshot_status()
        assert result == mock_response
        mock_elasticsearch.snapshot.status.assert_called_once_with()

    def test_get_snapshot_status_by_repo(self, snapshot_manager, mock_elasticsearch):
        """Test getting status for all snapshots in a repository."""
        # Setup mock response
        mock_response = {
            "snapshots": [
                {
                    "snapshot": "snapshot1",
                    "repository": "test-repo",
                    "state": "SUCCESS",
                },
                {
                    "snapshot": "snapshot2",
                    "repository": "test-repo",
                    "state": "IN_PROGRESS",
                },
            ]
        }
        mock_elasticsearch.snapshot.status.return_value = mock_response

        result = snapshot_manager.get_snapshot_status(repo_name="test-repo")
        assert result == mock_response
        mock_elasticsearch.snapshot.status.assert_called_once_with(
            repository="test-repo"
        )

    def test_get_snapshot_status_by_repo_and_snapshot(
        self, snapshot_manager, mock_elasticsearch
    ):
        """Test getting status for a specific snapshot."""
        # Setup mock response
        mock_response = {
            "snapshots": [
                {
                    "snapshot": "test-snapshot",
                    "repository": "test-repo",
                    "state": "IN_PROGRESS",
                    "stats": {"total": {"file_count": 100, "size_in_bytes": 1024}},
                }
            ]
        }
        mock_elasticsearch.snapshot.status.return_value = mock_response

        result = snapshot_manager.get_snapshot_status(
            repo_name="test-repo", snapshot_name="test-snapshot"
        )
        assert result == mock_response
        mock_elasticsearch.snapshot.status.assert_called_once_with(
            repository="test-repo", snapshot="test-snapshot"
        )

    def test_get_snapshot_status_error(self, snapshot_manager, mock_elasticsearch):
        """Test error handling when getting snapshot status."""
        # Setup mock to raise an exception
        mock_elasticsearch.snapshot.status.side_effect = Exception("Test error")

        with pytest.raises(
            OperationError, match="Failed to get snapshot status: Test error"
        ):
            snapshot_manager.get_snapshot_status()
