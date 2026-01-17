"""
Unit tests for the IndexManager class.
"""

import pytest
from unittest.mock import patch, MagicMock

from elastro.core.index import IndexManager
from elastro.core.errors import IndexError, ValidationError


class TestIndexManager:
    """Tests for the IndexManager class."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.mock_client = MagicMock()
        self.mock_client.client = MagicMock()
        self.mock_validator = MagicMock()

        with patch("elastro.core.index.Validator", return_value=self.mock_validator):
            self.index_manager = IndexManager(self.mock_client)

    def test_init(self):
        """Test initialization of IndexManager."""
        with patch("elastro.core.index.Validator") as mock_validator_class:
            mock_validator = MagicMock()
            mock_validator_class.return_value = mock_validator

            client = MagicMock()
            index_manager = IndexManager(client)

            assert index_manager.client == client
            assert index_manager._client == client
            assert index_manager.validator == mock_validator

    def test_create_index_basic(self):
        """Test creating an index with basic configuration."""
        # Setup
        index_name = "test_index"
        expected_response = {"acknowledged": True}
        self.mock_client.client.indices.create.return_value = expected_response

        # Execute
        response = self.index_manager.create(index_name)

        # Verify
        self.mock_client.client.indices.create.assert_called_once_with(
            index=index_name, body={}
        )
        assert response == expected_response

    def test_create_index_with_settings_and_mappings(self):
        """Test creating an index with settings and mappings."""
        # Setup
        index_name = "test_index"
        settings = {"number_of_shards": 3, "number_of_replicas": 2}
        mappings = {"properties": {"field1": {"type": "text"}}}
        expected_response = {"acknowledged": True}

        self.mock_client.client.indices.create.return_value = expected_response

        # Execute
        response = self.index_manager.create(
            name=index_name, settings=settings, mappings=mappings
        )

        # Verify
        self.mock_client.client.indices.create.assert_called_once_with(
            index=index_name, body={"settings": settings, "mappings": mappings}
        )
        assert response == expected_response

    def test_create_index_with_combined_settings(self):
        """Test creating an index with settings containing both settings and mappings."""
        # Setup
        index_name = "test_index"
        combined_settings = {
            "settings": {"number_of_shards": 3},
            "mappings": {"properties": {"field1": {"type": "text"}}},
        }
        expected_response = {"acknowledged": True}

        self.mock_client.client.indices.create.return_value = expected_response

        # Execute
        response = self.index_manager.create(
            name=index_name, settings=combined_settings
        )

        # Verify
        self.mock_client.client.indices.create.assert_called_once_with(
            index=index_name,
            body={
                "settings": combined_settings.get("settings"),
                "mappings": combined_settings.get("mappings"),
            },
        )
        assert response == expected_response

    def test_create_index_validation_error_settings(self):
        """Test validation error when creating an index with invalid settings."""
        # Setup
        index_name = "test_index"
        invalid_settings = {"invalid_setting": "value"}

        self.mock_validator.validate_index_settings.side_effect = ValidationError(
            "Invalid settings"
        )

        # Execute and Verify
        with pytest.raises(ValidationError) as excinfo:
            self.index_manager.create(name=index_name, settings=invalid_settings)

        assert "Invalid settings" in str(excinfo.value)
        self.mock_validator.validate_index_settings.assert_called_once_with(
            invalid_settings
        )
        self.mock_client.client.indices.create.assert_not_called()

    def test_create_index_validation_error_mappings(self):
        """Test validation error when creating an index with invalid mappings."""
        # Setup
        index_name = "test_index"
        valid_settings = {"number_of_shards": 3}
        invalid_mappings = {"invalid_mapping": "value"}

        self.mock_validator.validate_index_mappings.side_effect = ValidationError(
            "Invalid mappings"
        )

        # Execute and Verify
        with pytest.raises(ValidationError) as excinfo:
            self.index_manager.create(
                name=index_name, settings=valid_settings, mappings=invalid_mappings
            )

        assert "Invalid mappings" in str(excinfo.value)
        self.mock_validator.validate_index_settings.assert_called_once_with(
            valid_settings
        )
        self.mock_validator.validate_index_mappings.assert_called_once_with(
            invalid_mappings
        )
        self.mock_client.client.indices.create.assert_not_called()

    def test_create_index_missing_name(self):
        """Test validation error when index name is missing."""
        # Execute and Verify
        with pytest.raises(ValidationError) as excinfo:
            self.index_manager.create(name="")

        assert "Index name is required" in str(excinfo.value)
        self.mock_client.client.indices.create.assert_not_called()

    def test_create_index_client_error(self):
        """Test error handling when the client fails to create the index."""
        # Setup
        index_name = "test_index"
        self.mock_client.client.indices.create.side_effect = Exception(
            "Connection refused"
        )

        # Execute and Verify
        with pytest.raises(IndexError) as excinfo:
            self.index_manager.create(name=index_name)

        assert f"Failed to create index '{index_name}'" in str(excinfo.value)
        self.mock_client.client.indices.create.assert_called_once()

    def test_exists_true(self):
        """Test index exists check when index exists."""
        # Setup
        index_name = "test_index"
        self.mock_client.client.indices.exists.return_value = True

        # Execute
        result = self.index_manager.exists(index_name)

        # Verify
        assert result is True
        self.mock_client.client.indices.exists.assert_called_once_with(index=index_name)

    def test_exists_false(self):
        """Test index exists check when index does not exist."""
        # Setup
        index_name = "test_index"
        self.mock_client.client.indices.exists.return_value = False

        # Execute
        result = self.index_manager.exists(index_name)

        # Verify
        assert result is False
        self.mock_client.client.indices.exists.assert_called_once_with(index=index_name)

    def test_exists_missing_name(self):
        """Test validation error when index name is missing for exists check."""
        # Execute and Verify
        with pytest.raises(ValidationError) as excinfo:
            self.index_manager.exists(name="")

        assert "Index name is required" in str(excinfo.value)
        self.mock_client.client.indices.exists.assert_not_called()

    def test_exists_client_error(self):
        """Test error handling when the client fails during exists check."""
        # Setup
        index_name = "test_index"
        self.mock_client.client.indices.exists.side_effect = Exception(
            "Connection refused"
        )

        # Execute and Verify
        with pytest.raises(IndexError) as excinfo:
            self.index_manager.exists(index_name)

        assert f"Failed to check if index '{index_name}' exists" in str(excinfo.value)
        self.mock_client.client.indices.exists.assert_called_once()

    def test_get_existing_index(self):
        """Test getting information for an existing index."""
        # Setup
        index_name = "test_index"
        expected_response = {
            "test_index": {
                "settings": {"index": {"number_of_shards": "3"}},
                "mappings": {"properties": {"field1": {"type": "text"}}},
            }
        }

        # Mock the exists method to return True
        with patch.object(self.index_manager, "exists", return_value=True):
            self.mock_client.client.indices.get.return_value = expected_response

            # Execute
            response = self.index_manager.get(index_name)

            # Verify
            assert response == expected_response
            self.mock_client.client.indices.get.assert_called_once_with(
                index=index_name
            )

    def test_get_non_existing_index(self):
        """Test getting information for a non-existing index."""
        # Setup
        index_name = "test_index"

        # Mock the exists method to return False
        with patch.object(self.index_manager, "exists", return_value=False):
            # Execute and Verify
            with pytest.raises(IndexError) as excinfo:
                self.index_manager.get(index_name)

            assert f"Index '{index_name}' does not exist" in str(excinfo.value)
            self.mock_client.client.indices.get.assert_not_called()

    def test_get_missing_name(self):
        """Test validation error when index name is missing for get."""
        # Execute and Verify
        with pytest.raises(ValidationError) as excinfo:
            self.index_manager.get(name="")

        assert "Index name is required" in str(excinfo.value)
        self.mock_client.client.indices.get.assert_not_called()

    def test_get_client_error(self):
        """Test error handling when the client fails during get."""
        # Setup
        index_name = "test_index"

        # Mock the exists method to return True
        with patch.object(self.index_manager, "exists", return_value=True):
            self.mock_client.client.indices.get.side_effect = Exception(
                "Connection refused"
            )

            # Execute and Verify
            with pytest.raises(IndexError) as excinfo:
                self.index_manager.get(index_name)

            assert f"Failed to get index '{index_name}'" in str(excinfo.value)
            self.mock_client.client.indices.get.assert_called_once()

    def test_update_existing_index(self):
        """Test updating settings for an existing index."""
        # Setup
        index_name = "test_index"
        settings = {"index": {"number_of_replicas": 3}}
        expected_response = {"acknowledged": True}

        # Mock the exists method to return True
        with patch.object(self.index_manager, "exists", return_value=True):
            self.mock_client.client.indices.put_settings.return_value = (
                expected_response
            )

            # Execute
            response = self.index_manager.update(index_name, settings)

            # Verify
            assert response == expected_response
            self.mock_validator.validate_index_settings.assert_called_once_with(
                settings
            )
            self.mock_client.client.indices.put_settings.assert_called_once_with(
                index=index_name, body=settings
            )

    def test_update_non_existing_index(self):
        """Test updating settings for a non-existing index."""
        # Setup
        index_name = "test_index"
        settings = {"index": {"number_of_replicas": 3}}

        # Mock the exists method to return False
        with patch.object(self.index_manager, "exists", return_value=False):
            # Execute and Verify
            with pytest.raises(IndexError) as excinfo:
                self.index_manager.update(index_name, settings)

            assert f"Index '{index_name}' does not exist" in str(excinfo.value)
            self.mock_validator.validate_index_settings.assert_called_once_with(
                settings
            )
            self.mock_client.client.indices.put_settings.assert_not_called()

    def test_update_missing_name(self):
        """Test validation error when index name is missing for update."""
        # Setup
        settings = {"index": {"number_of_replicas": 3}}

        # Execute and Verify
        with pytest.raises(ValidationError) as excinfo:
            self.index_manager.update(name="", settings=settings)

        assert "Index name is required" in str(excinfo.value)
        self.mock_client.client.indices.put_settings.assert_not_called()

    def test_update_missing_settings(self):
        """Test validation error when settings are missing for update."""
        # Setup
        index_name = "test_index"

        # Execute and Verify
        with pytest.raises(ValidationError) as excinfo:
            self.index_manager.update(name=index_name, settings=None)

        assert "Settings are required for update" in str(excinfo.value)
        self.mock_client.client.indices.put_settings.assert_not_called()

    def test_update_invalid_settings(self):
        """Test validation error when settings are invalid for update."""
        # Setup
        index_name = "test_index"
        invalid_settings = {"invalid_setting": "value"}

        self.mock_validator.validate_index_settings.side_effect = ValidationError(
            "Invalid settings"
        )

        # Execute and Verify
        with pytest.raises(ValidationError) as excinfo:
            self.index_manager.update(name=index_name, settings=invalid_settings)

        assert "Invalid settings" in str(excinfo.value)
        self.mock_validator.validate_index_settings.assert_called_once_with(
            invalid_settings
        )
        self.mock_client.client.indices.put_settings.assert_not_called()

    def test_update_client_error(self):
        """Test error handling when the client fails during update."""
        # Setup
        index_name = "test_index"
        settings = {"index": {"number_of_replicas": 3}}

        # Mock the exists method to return True
        with patch.object(self.index_manager, "exists", return_value=True):
            self.mock_client.client.indices.put_settings.side_effect = Exception(
                "Connection refused"
            )

            # Execute and Verify
            with pytest.raises(IndexError) as excinfo:
                self.index_manager.update(index_name, settings)

            assert f"Failed to update index '{index_name}'" in str(excinfo.value)
            self.mock_validator.validate_index_settings.assert_called_once_with(
                settings
            )
            self.mock_client.client.indices.put_settings.assert_called_once()

    def test_delete_existing_index(self):
        """Test deleting an existing index."""
        # Setup
        index_name = "test_index"
        expected_response = {"acknowledged": True}

        # Mock the exists method to return True
        with patch.object(self.index_manager, "exists", return_value=True):
            self.mock_client.client.indices.delete.return_value = expected_response

            # Execute
            response = self.index_manager.delete(index_name)

            # Verify
            assert response == expected_response
            self.mock_client.client.indices.delete.assert_called_once_with(
                index=index_name
            )

    def test_delete_non_existing_index(self):
        """Test deleting a non-existing index."""
        # Setup
        index_name = "test_index"

        # Mock the exists method to return False
        with patch.object(self.index_manager, "exists", return_value=False):
            # Execute and Verify
            with pytest.raises(IndexError) as excinfo:
                self.index_manager.delete(index_name)

            assert f"Index '{index_name}' does not exist" in str(excinfo.value)
            self.mock_client.client.indices.delete.assert_not_called()

    def test_delete_missing_name(self):
        """Test validation error when index name is missing for delete."""
        # Execute and Verify
        with pytest.raises(ValidationError) as excinfo:
            self.index_manager.delete(name="")

        assert "Index name is required" in str(excinfo.value)
        self.mock_client.client.indices.delete.assert_not_called()

    def test_delete_client_error(self):
        """Test error handling when the client fails during delete."""
        # Setup
        index_name = "test_index"

        # Mock the exists method to return True
        with patch.object(self.index_manager, "exists", return_value=True):
            self.mock_client.client.indices.delete.side_effect = Exception(
                "Connection refused"
            )

            # Execute and Verify
            with pytest.raises(IndexError) as excinfo:
                self.index_manager.delete(index_name)

            assert f"Failed to delete index '{index_name}'" in str(excinfo.value)
            self.mock_client.client.indices.delete.assert_called_once()

    def test_open_existing_index(self):
        """Test opening an existing index."""
        # Setup
        index_name = "test_index"
        expected_response = {"acknowledged": True}

        # Mock the exists method to return True
        with patch.object(self.index_manager, "exists", return_value=True):
            self.mock_client.client.indices.open.return_value = expected_response

            # Execute
            response = self.index_manager.open(index_name)

            # Verify
            assert response == expected_response
            self.mock_client.client.indices.open.assert_called_once_with(
                index=index_name
            )

    def test_open_non_existing_index(self):
        """Test opening a non-existing index."""
        # Setup
        index_name = "test_index"

        # Mock the exists method to return False
        with patch.object(self.index_manager, "exists", return_value=False):
            # Execute and Verify
            with pytest.raises(IndexError) as excinfo:
                self.index_manager.open(index_name)

            assert f"Index '{index_name}' does not exist" in str(excinfo.value)
            self.mock_client.client.indices.open.assert_not_called()

    def test_open_missing_name(self):
        """Test validation error when index name is missing for open."""
        # Execute and Verify
        with pytest.raises(ValidationError) as excinfo:
            self.index_manager.open(name="")

        assert "Index name is required" in str(excinfo.value)
        self.mock_client.client.indices.open.assert_not_called()

    def test_open_client_error(self):
        """Test error handling when the client fails during open."""
        # Setup
        index_name = "test_index"

        # Mock the exists method to return True
        with patch.object(self.index_manager, "exists", return_value=True):
            self.mock_client.client.indices.open.side_effect = Exception(
                "Connection refused"
            )

            # Execute and Verify
            with pytest.raises(IndexError) as excinfo:
                self.index_manager.open(index_name)

            assert f"Failed to open index '{index_name}'" in str(excinfo.value)
            self.mock_client.client.indices.open.assert_called_once()

    def test_close_existing_index(self):
        """Test closing an existing index."""
        # Setup
        index_name = "test_index"
        expected_response = {"acknowledged": True}

        # Mock the exists method to return True
        with patch.object(self.index_manager, "exists", return_value=True):
            self.mock_client.client.indices.close.return_value = expected_response

            # Execute
            response = self.index_manager.close(index_name)

            # Verify
            assert response == expected_response
            self.mock_client.client.indices.close.assert_called_once_with(
                index=index_name
            )

    def test_close_non_existing_index(self):
        """Test closing a non-existing index."""
        # Setup
        index_name = "test_index"

        # Mock the exists method to return False
        with patch.object(self.index_manager, "exists", return_value=False):
            # Execute and Verify
            with pytest.raises(IndexError) as excinfo:
                self.index_manager.close(index_name)

            assert f"Index '{index_name}' does not exist" in str(excinfo.value)
            self.mock_client.client.indices.close.assert_not_called()

    def test_close_missing_name(self):
        """Test validation error when index name is missing for close."""
        # Execute and Verify
        with pytest.raises(ValidationError) as excinfo:
            self.index_manager.close(name="")

        assert "Index name is required" in str(excinfo.value)
        self.mock_client.client.indices.close.assert_not_called()

    def test_close_client_error(self):
        """Test error handling when the client fails during close."""
        # Setup
        index_name = "test_index"

        # Mock the exists method to return True
        with patch.object(self.index_manager, "exists", return_value=True):
            self.mock_client.client.indices.close.side_effect = Exception(
                "Connection refused"
            )

            # Execute and Verify
            with pytest.raises(IndexError) as excinfo:
                self.index_manager.close(index_name)

            assert f"Failed to close index '{index_name}'" in str(excinfo.value)
            self.mock_client.client.indices.close.assert_called_once()
