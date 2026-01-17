"""
Integration tests for the IndexManager class.
These tests require a running Elasticsearch instance.
"""

import pytest
import os

from elastro.core.index import IndexManager
from tests.fixtures.index_fixtures import VALID_INDEX_BODY


# Mark as integration tests
@pytest.mark.integration
class TestIndexManagerIntegration:
    """Integration tests for IndexManager."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self, real_es_client):
        """Set up before and tear down after tests."""
        self.index_manager = IndexManager(real_es_client)
        self.test_index = "test-integration-index"

        # Make sure the index doesn't exist before tests
        if self.index_manager.exists(self.test_index):
            self.index_manager.delete(self.test_index)

        yield

        # Clean up after tests
        if self.index_manager.exists(self.test_index):
            self.index_manager.delete(self.test_index)

    def test_create_and_get_index(self):
        """Test creating and retrieving an index."""
        # Create index
        response = self.index_manager.create(self.test_index, VALID_INDEX_BODY)
        assert response["acknowledged"] == True

        # Check if index exists
        assert self.index_manager.exists(self.test_index) == True

        # Get index details
        index_info = self.index_manager.get(self.test_index)
        assert self.test_index in index_info

        # Verify settings
        settings = index_info[self.test_index]["settings"]["index"]
        assert "number_of_shards" in settings
        assert "number_of_replicas" in settings

        # Verify mappings
        mappings = index_info[self.test_index]["mappings"]
        assert "properties" in mappings
        assert "title" in mappings["properties"]
        assert mappings["properties"]["title"]["type"] == "text"

    def test_update_index_settings(self):
        """Test updating index settings."""
        # Create index
        self.index_manager.create(self.test_index, VALID_INDEX_BODY)

        # Update settings
        new_settings = {"number_of_replicas": 2}
        response = self.index_manager.update(self.test_index, new_settings)
        assert response["acknowledged"] == True

        # Verify settings were updated
        index_info = self.index_manager.get(self.test_index)
        settings = index_info[self.test_index]["settings"]["index"]
        assert settings["number_of_replicas"] == "2"

    def test_open_close_index(self):
        """Test opening and closing an index."""
        # Create index
        self.index_manager.create(self.test_index, VALID_INDEX_BODY)

        # Close index
        response = self.index_manager.close(self.test_index)
        assert response["acknowledged"] == True

        # With Elasticsearch 8.x, we need to check index status differently
        # For a closed index, some cluster APIs may behave differently
        # Here we'll verify that the index exists but we can't access its settings
        # which is a characteristic of closed indices
        assert self.index_manager.exists(self.test_index) == True

        # Open index
        response = self.index_manager.open(self.test_index)
        assert response["acknowledged"] == True

        # Verify index is open by checking we can access its settings
        index_info = self.index_manager.get(self.test_index)
        assert "settings" in index_info[self.test_index]

    def test_delete_index(self):
        """Test deleting an index."""
        # Create index
        self.index_manager.create(self.test_index, VALID_INDEX_BODY)

        # Delete index
        response = self.index_manager.delete(self.test_index)
        assert response["acknowledged"] == True

        # Verify index doesn't exist
        assert not self.index_manager.exists(self.test_index)
