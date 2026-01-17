"""
Unit tests for the DatastreamManager class.
"""

import pytest
from unittest.mock import patch, MagicMock

from elastro.core.datastream import DatastreamManager
from elastro.core.client import ElasticsearchClient
from elastro.core.errors import DatastreamError, ValidationError


class TestDatastreamManager:
    """Tests for the DatastreamManager class."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        # Create a mock ElasticsearchClient
        self.mock_client = MagicMock(spec=ElasticsearchClient)
        self.mock_client.is_connected.return_value = True
        self.mock_client._client = MagicMock()

        # Create DatastreamManager with mock client
        self.datastream_manager = DatastreamManager(self.mock_client)

        # Mock validator
        self.datastream_manager.validator = MagicMock()

    def test_init(self):
        """Test initialization of DatastreamManager."""
        assert self.datastream_manager._client == self.mock_client
        assert self.datastream_manager.validator is not None

    def test_create_index_template_success(self):
        """Test successful creation of an index template."""
        # Setup mock response
        self.mock_client._client.indices.put_index_template.return_value = {
            "acknowledged": True
        }

        # Test data
        name = "test-template"
        pattern = "logs-*"
        settings = {
            "settings": {"number_of_shards": 1},
            "mappings": {"properties": {"field1": {"type": "keyword"}}},
        }

        # Call the method
        result = self.datastream_manager.create_index_template(name, pattern, settings)

        # Verify result
        assert result == {"acknowledged": True}

        # Verify mock calls
        self.mock_client.is_connected.assert_called_once()
        self.mock_client._client.indices.put_index_template.assert_called_once()

        # Verify template definition
        call_args = self.mock_client._client.indices.put_index_template.call_args[1]
        assert call_args["name"] == name
        assert call_args["body"]["index_patterns"] == [pattern]
        assert call_args["body"]["data_stream"] == {}
        assert call_args["body"]["priority"] == 500
        assert call_args["body"]["settings"] == settings["settings"]
        assert call_args["body"]["mappings"] == settings["mappings"]

        # Verify validator calls
        self.datastream_manager.validator.validate_index_mappings.assert_called_once_with(
            settings
        )
        self.datastream_manager.validator.validate_index_settings.assert_called_once_with(
            settings
        )

    def test_create_index_template_empty_name(self):
        """Test creation of index template with empty name."""
        with pytest.raises(ValidationError) as excinfo:
            self.datastream_manager.create_index_template("", "logs-*", {})

        assert "Template name cannot be empty" in str(excinfo.value)
        self.mock_client._client.indices.put_index_template.assert_not_called()

    def test_create_index_template_empty_pattern(self):
        """Test creation of index template with empty pattern."""
        with pytest.raises(ValidationError) as excinfo:
            self.datastream_manager.create_index_template("test-template", "", {})

        assert "Index pattern cannot be empty" in str(excinfo.value)
        self.mock_client._client.indices.put_index_template.assert_not_called()

    def test_create_index_template_connection_failure(self):
        """Test handling of connection failure during template creation."""
        # Setup mock response
        self.mock_client.is_connected.return_value = False
        self.mock_client.connect = MagicMock()

        # Test data
        name = "test-template"
        pattern = "logs-*"
        settings = {}

        # Call the method
        self.datastream_manager.create_index_template(name, pattern, settings)

        # Verify connect was called
        self.mock_client.connect.assert_called_once()

    def test_create_index_template_es_error(self):
        """Test handling of Elasticsearch error during template creation."""
        # Setup mock response
        self.mock_client._client.indices.put_index_template.side_effect = Exception(
            "ES error"
        )

        # Test data
        name = "test-template"
        pattern = "logs-*"
        settings = {}

        # Call the method
        with pytest.raises(DatastreamError) as excinfo:
            self.datastream_manager.create_index_template(name, pattern, settings)

        assert "Failed to create index template" in str(excinfo.value)
        assert "ES error" in str(excinfo.value)

    def test_create_datastream_success(self):
        """Test successful creation of a datastream."""
        # Setup mock response
        self.mock_client._client.indices.create_data_stream.return_value = {
            "acknowledged": True
        }

        # Call the method
        result = self.datastream_manager.create("test-datastream")

        # Verify result
        assert result == {"acknowledged": True}

        # Verify mock calls
        self.mock_client.is_connected.assert_called_once()
        self.mock_client._client.indices.create_data_stream.assert_called_once_with(
            name="test-datastream"
        )

    def test_create_datastream_with_description(self):
        """Test creation of datastream with description."""
        # Setup mock response
        self.mock_client._client.indices.create_data_stream.return_value = {
            "acknowledged": True
        }

        # Call the method
        result = self.datastream_manager.create(
            "test-datastream", description="Test description"
        )

        # Verify result
        assert result == {"acknowledged": True}

        # Verify mock calls
        call_args = self.mock_client._client.indices.create_data_stream.call_args[1]
        assert call_args["name"] == "test-datastream"
        assert "aliases" in call_args
        assert call_args["aliases"]["default"]["is_write_index"] is True

    def test_create_datastream_empty_name(self):
        """Test creation of datastream with empty name."""
        with pytest.raises(ValidationError) as excinfo:
            self.datastream_manager.create("")

        assert "Datastream name is required" in str(excinfo.value)
        self.mock_client._client.indices.create_data_stream.assert_not_called()

    def test_create_datastream_es_error(self):
        """Test handling of Elasticsearch error during datastream creation."""
        # Setup mock response
        self.mock_client._client.indices.create_data_stream.side_effect = Exception(
            "ES error"
        )

        # Call the method
        with pytest.raises(DatastreamError) as excinfo:
            self.datastream_manager.create("test-datastream")

        assert "Failed to create datastream" in str(excinfo.value)
        assert "ES error" in str(excinfo.value)

    def test_list_datastreams_success(self):
        """Test successful listing of datastreams."""
        # Setup mock response
        mock_response = {
            "data_streams": [
                {"name": "logs-app1", "timestamp_field": "@timestamp", "indices": []},
                {"name": "logs-app2", "timestamp_field": "@timestamp", "indices": []},
            ]
        }
        self.mock_client._client.indices.get_data_stream.return_value = mock_response

        # Call the method
        result = self.datastream_manager.list()

        # Verify result
        assert len(result) == 2
        assert result[0]["name"] == "logs-app1"
        assert result[1]["name"] == "logs-app2"

        # Verify mock calls
        self.mock_client.is_connected.assert_called_once()
        self.mock_client._client.indices.get_data_stream.assert_called_once_with(
            name="*"
        )

    def test_list_datastreams_with_pattern(self):
        """Test listing datastreams with a specific pattern."""
        # Setup mock response
        mock_response = {
            "data_streams": [
                {"name": "logs-app1", "timestamp_field": "@timestamp", "indices": []}
            ]
        }
        self.mock_client._client.indices.get_data_stream.return_value = mock_response

        # Call the method
        result = self.datastream_manager.list(pattern="logs-app1")

        # Verify result
        assert len(result) == 1

        # Verify mock calls
        self.mock_client._client.indices.get_data_stream.assert_called_once_with(
            name="logs-app1"
        )

    def test_list_datastreams_not_found(self):
        """Test listing datastreams when none are found."""
        # Setup mock response
        self.mock_client._client.indices.get_data_stream.side_effect = Exception(
            "index_not_found"
        )

        # Call the method
        result = self.datastream_manager.list()

        # Verify result
        assert result == []

    def test_list_datastreams_es_error(self):
        """Test handling of Elasticsearch error during datastreams listing."""
        # Setup mock response
        self.mock_client._client.indices.get_data_stream.side_effect = Exception(
            "ES error"
        )

        # Call the method
        with pytest.raises(DatastreamError) as excinfo:
            self.datastream_manager.list()

        assert "Failed to list datastreams" in str(excinfo.value)
        assert "ES error" in str(excinfo.value)

    def test_get_datastream_success(self):
        """Test successfully getting a datastream."""
        # Setup mock response
        mock_response = {
            "data_streams": [
                {
                    "name": "logs-app1",
                    "timestamp_field": "@timestamp",
                    "generation": 1,
                    "indices": [{"index": "logs-app1-000001"}],
                }
            ]
        }
        self.mock_client._client.indices.get_data_stream.return_value = mock_response

        # Call the method
        result = self.datastream_manager.get("logs-app1")

        # Verify result
        assert result["name"] == "logs-app1"
        assert result["generation"] == 1
        assert result["status"] == "GREEN"
        assert result["indices"] == [{"index": "logs-app1-000001"}]

        # Verify mock calls
        self.mock_client.is_connected.assert_called_once()
        self.mock_client._client.indices.get_data_stream.assert_called_once_with(
            name="logs-app1"
        )

    def test_get_datastream_empty_name(self):
        """Test getting a datastream with empty name."""
        with pytest.raises(ValidationError) as excinfo:
            self.datastream_manager.get("")

        assert "Datastream name cannot be empty" in str(excinfo.value)
        self.mock_client._client.indices.get_data_stream.assert_not_called()

    def test_get_datastream_not_found(self):
        """Test getting a datastream that doesn't exist."""
        # Setup mock response with empty data_streams
        self.mock_client._client.indices.get_data_stream.return_value = {
            "data_streams": []
        }

        # Call the method
        with pytest.raises(DatastreamError) as excinfo:
            self.datastream_manager.get("non-existent")

        assert "not found" in str(excinfo.value)

    def test_get_datastream_es_error(self):
        """Test handling of Elasticsearch error when getting a datastream."""
        # Setup mock response
        self.mock_client._client.indices.get_data_stream.side_effect = Exception(
            "ES error"
        )

        # Call the method
        with pytest.raises(DatastreamError) as excinfo:
            self.datastream_manager.get("logs-app1")

        assert "Failed to get datastream" in str(excinfo.value)
        assert "ES error" in str(excinfo.value)

    def test_exists_datastream_found(self):
        """Test checking if a datastream exists when it does."""
        # Setup mock response
        self.mock_client._client.indices.get_data_stream.return_value = {
            "data_streams": [{}]
        }

        # Call the method
        result = self.datastream_manager.exists("logs-app1")

        # Verify result
        assert result is True

        # Verify mock calls
        self.mock_client.is_connected.assert_called_once()
        self.mock_client._client.indices.get_data_stream.assert_called_once_with(
            name="logs-app1"
        )

    def test_exists_datastream_not_found(self):
        """Test checking if a datastream exists when it doesn't."""
        # Setup mock response
        self.mock_client._client.indices.get_data_stream.side_effect = Exception(
            "index_not_found"
        )

        # Call the method
        result = self.datastream_manager.exists("non-existent")

        # Verify result
        assert result is False

    def test_exists_datastream_empty_name(self):
        """Test checking if a datastream with empty name exists."""
        with pytest.raises(ValidationError) as excinfo:
            self.datastream_manager.exists("")

        assert "Datastream name cannot be empty" in str(excinfo.value)
        self.mock_client._client.indices.get_data_stream.assert_not_called()

    def test_exists_datastream_es_error(self):
        """Test handling of Elasticsearch error when checking if a datastream exists."""
        # Setup mock response with an error other than "index_not_found"
        self.mock_client._client.indices.get_data_stream.side_effect = Exception(
            "ES error"
        )

        # Call the method
        with pytest.raises(DatastreamError) as excinfo:
            self.datastream_manager.exists("logs-app1")

        assert "Failed to check if datastream" in str(excinfo.value)
        assert "ES error" in str(excinfo.value)

    def test_delete_datastream_success(self):
        """Test successful deletion of a datastream."""
        # Setup mock responses
        self.mock_client._client.indices.delete_data_stream.return_value = {
            "acknowledged": True
        }
        self.mock_client._client.indices.delete_index_template.return_value = {
            "acknowledged": True
        }

        # Call the method
        result = self.datastream_manager.delete("logs-app1")

        # Verify result
        assert result == {"acknowledged": True}

        # Verify mock calls
        self.mock_client.is_connected.assert_called_once()
        self.mock_client._client.indices.delete_data_stream.assert_called_once_with(
            name="logs-app1"
        )
        self.mock_client._client.indices.delete_index_template.assert_called_once_with(
            name="logs-app1-template"
        )

    def test_delete_datastream_template_not_found(self):
        """Test deletion of a datastream when its template doesn't exist."""
        # Setup mock responses
        self.mock_client._client.indices.delete_data_stream.return_value = {
            "acknowledged": True
        }
        self.mock_client._client.indices.delete_index_template.side_effect = Exception(
            "Not found"
        )

        # Call the method
        result = self.datastream_manager.delete("logs-app1")

        # Verify result - the operation should succeed even if template deletion fails
        assert result == {"acknowledged": True}

        # Verify mock calls
        self.mock_client._client.indices.delete_data_stream.assert_called_once_with(
            name="logs-app1"
        )
        self.mock_client._client.indices.delete_index_template.assert_called_once_with(
            name="logs-app1-template"
        )

    def test_delete_datastream_empty_name(self):
        """Test deletion of a datastream with empty name."""
        with pytest.raises(ValidationError) as excinfo:
            self.datastream_manager.delete("")

        assert "Datastream name cannot be empty" in str(excinfo.value)
        self.mock_client._client.indices.delete_data_stream.assert_not_called()

    def test_delete_datastream_es_error(self):
        """Test handling of Elasticsearch error during datastream deletion."""
        # Setup mock response
        self.mock_client._client.indices.delete_data_stream.side_effect = Exception(
            "ES error"
        )

        # Call the method
        with pytest.raises(DatastreamError) as excinfo:
            self.datastream_manager.delete("logs-app1")

        assert "Failed to delete datastream" in str(excinfo.value)
        assert "ES error" in str(excinfo.value)

    def test_rollover_datastream_success(self):
        """Test successful rollover of a datastream."""
        # Setup mock response
        self.mock_client._client.indices.rollover.return_value = {
            "acknowledged": True,
            "old_index": "logs-app1-000001",
            "new_index": "logs-app1-000002",
            "rolled_over": True,
        }

        # Call the method
        result = self.datastream_manager.rollover("logs-app1")

        # Verify result
        assert result["acknowledged"] is True
        assert result["rolled_over"] is True

        # Verify mock calls
        self.mock_client.is_connected.assert_called_once()
        self.mock_client._client.indices.rollover.assert_called_once_with(
            alias="logs-app1"
        )

    def test_rollover_datastream_with_conditions(self):
        """Test rollover of a datastream with conditions."""
        # Setup mock response
        self.mock_client._client.indices.rollover.return_value = {
            "acknowledged": True,
            "rolled_over": True,
        }

        # Test data
        conditions = {"max_age": "1d", "max_docs": 10000}

        # Call the method
        result = self.datastream_manager.rollover("logs-app1", conditions)

        # Verify result
        assert result["acknowledged"] is True

        # Verify mock calls
        call_args = self.mock_client._client.indices.rollover.call_args[1]
        assert call_args["alias"] == "logs-app1"
        assert call_args["body"]["conditions"] == conditions

    def test_rollover_datastream_empty_name(self):
        """Test rollover of a datastream with empty name."""
        with pytest.raises(ValidationError) as excinfo:
            self.datastream_manager.rollover("")

        assert "Datastream name cannot be empty" in str(excinfo.value)
        self.mock_client._client.indices.rollover.assert_not_called()

    def test_rollover_datastream_es_error(self):
        """Test handling of Elasticsearch error during datastream rollover."""
        # Setup mock response
        self.mock_client._client.indices.rollover.side_effect = Exception("ES error")

        # Call the method
        with pytest.raises(DatastreamError) as excinfo:
            self.datastream_manager.rollover("logs-app1")

        assert "Failed to rollover datastream" in str(excinfo.value)
        assert "ES error" in str(excinfo.value)
