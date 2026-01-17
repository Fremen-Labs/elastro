"""Unit tests for index template management utilities."""

import pytest
from unittest.mock import MagicMock, patch

from elastro.core.client import ElasticsearchClient
from elastro.core.errors import OperationError
from elastro.utils.templates import TemplateManager, TemplateDefinition


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
def template_manager(es_client):
    """Return a TemplateManager instance with a mocked client."""
    return TemplateManager(es_client)


class TestTemplateDefinition:
    """Test suite for TemplateDefinition model."""

    def test_minimal_template(self):
        """Test initializing a minimal template definition."""
        template = TemplateDefinition(name="test-template", index_patterns=["test-*"])
        assert template.name == "test-template"
        assert template.index_patterns == ["test-*"]
        assert template.template == {}
        assert template.version is None
        assert template.priority is None
        assert template.composed_of == []
        assert template.meta is None

    def test_complete_template(self):
        """Test initializing a complete template definition."""
        template_data = {
            "name": "test-template",
            "index_patterns": ["test-*", "sample-*"],
            "template": {
                "settings": {"number_of_shards": 1},
                "mappings": {"properties": {"field1": {"type": "keyword"}}},
            },
            "version": 1,
            "priority": 100,
            "composed_of": ["component1", "component2"],
            "meta": {"description": "Test template"},
        }

        template = TemplateDefinition(**template_data)

        assert template.name == template_data["name"]
        assert template.index_patterns == template_data["index_patterns"]
        assert template.template == template_data["template"]
        assert template.version == template_data["version"]
        assert template.priority == template_data["priority"]
        assert template.composed_of == template_data["composed_of"]
        assert template.meta == template_data["meta"]


class TestTemplateManager:
    """Test suite for TemplateManager class."""

    def test_init(self, es_client):
        """Test initializing TemplateManager."""
        manager = TemplateManager(es_client)
        assert manager._client == es_client
        assert manager._es == es_client.client

    def test_create_success_with_dict(self, template_manager, mock_elasticsearch):
        """Test creating a template with dict definition successfully."""
        # Setup mock response
        mock_elasticsearch.indices.put_index_template.return_value = {
            "acknowledged": True
        }

        # Template definition as a dict
        template_dict = {
            "name": "test-template",
            "index_patterns": ["test-*"],
            "template": {"settings": {"number_of_shards": 1}},
        }

        # Test creation
        result = template_manager.create(template_dict)
        assert result is True

        mock_elasticsearch.indices.put_index_template.assert_called_once()
        call_args = mock_elasticsearch.indices.put_index_template.call_args[1]
        assert call_args["name"] == "test-template"
        assert call_args["body"]["index_patterns"] == ["test-*"]
        assert call_args["body"]["template"]["settings"]["number_of_shards"] == 1

    def test_create_success_with_model(self, template_manager, mock_elasticsearch):
        """Test creating a template with TemplateDefinition model successfully."""
        # Setup mock response
        mock_elasticsearch.indices.put_index_template.return_value = {
            "acknowledged": True
        }

        # Template definition as a model
        template = TemplateDefinition(
            name="test-template",
            index_patterns=["test-*"],
            template={"settings": {"number_of_shards": 1}},
            version=2,
            priority=50,
        )

        # Test creation
        result = template_manager.create(template)
        assert result is True

        mock_elasticsearch.indices.put_index_template.assert_called_once()
        call_args = mock_elasticsearch.indices.put_index_template.call_args[1]
        assert call_args["name"] == "test-template"
        assert call_args["body"]["index_patterns"] == ["test-*"]
        assert call_args["body"]["template"]["settings"]["number_of_shards"] == 1
        assert call_args["body"]["version"] == 2
        assert call_args["body"]["priority"] == 50

    def test_create_error(self, template_manager, mock_elasticsearch):
        """Test error handling when creating a template."""
        # Setup mock to raise an exception
        mock_elasticsearch.indices.put_index_template.side_effect = Exception(
            "Test error"
        )

        # Template definition
        template = TemplateDefinition(name="test-template", index_patterns=["test-*"])

        # Test error handling
        with pytest.raises(
            OperationError, match="Failed to create template test-template: Test error"
        ):
            template_manager.create(template)

    def test_get_success(self, template_manager, mock_elasticsearch):
        """Test getting a template by name."""
        # Setup mock response
        mock_response = {
            "index_templates": [
                {
                    "name": "test-template",
                    "index_template": {
                        "index_patterns": ["test-*"],
                        "template": {"settings": {"number_of_shards": 1}},
                    },
                }
            ]
        }
        mock_elasticsearch.indices.get_index_template.return_value = mock_response

        # Test getting template
        result = template_manager.get("test-template")
        assert result == mock_response["index_templates"][0]
        mock_elasticsearch.indices.get_index_template.assert_called_once_with(
            name="test-template"
        )

    def test_get_empty_result(self, template_manager, mock_elasticsearch):
        """Test getting a template that doesn't exist."""
        # Setup mock response with no templates
        mock_elasticsearch.indices.get_index_template.return_value = {
            "index_templates": []
        }

        # Test getting non-existent template
        result = template_manager.get("non-existent")
        assert result == {}
        mock_elasticsearch.indices.get_index_template.assert_called_once_with(
            name="non-existent"
        )

    def test_get_error(self, template_manager, mock_elasticsearch):
        """Test error handling when getting a template."""
        # Setup mock to raise an exception
        mock_elasticsearch.indices.get_index_template.side_effect = Exception(
            "Test error"
        )

        # Test error handling
        with pytest.raises(
            OperationError, match="Failed to get template test-template: Test error"
        ):
            template_manager.get("test-template")

    def test_exists_true(self, template_manager, mock_elasticsearch):
        """Test checking if a template exists and it does."""
        # Setup mock response
        mock_elasticsearch.indices.exists_index_template.return_value = True

        # Test checking if template exists
        result = template_manager.exists("test-template")
        assert result is True
        mock_elasticsearch.indices.exists_index_template.assert_called_once_with(
            name="test-template"
        )

    def test_exists_false(self, template_manager, mock_elasticsearch):
        """Test checking if a template exists and it doesn't."""
        # Setup mock response
        mock_elasticsearch.indices.exists_index_template.return_value = False

        # Test checking if template doesn't exist
        result = template_manager.exists("non-existent")
        assert result is False
        mock_elasticsearch.indices.exists_index_template.assert_called_once_with(
            name="non-existent"
        )

    def test_exists_with_exception(self, template_manager, mock_elasticsearch):
        """Test handling exceptions when checking if a template exists."""
        # Setup mock to raise an exception
        mock_elasticsearch.indices.exists_index_template.side_effect = Exception(
            "Test error"
        )

        # Test exception handling returns False
        result = template_manager.exists("test-template")
        assert result is False
        mock_elasticsearch.indices.exists_index_template.assert_called_once_with(
            name="test-template"
        )

    def test_delete_success(self, template_manager, mock_elasticsearch):
        """Test deleting a template successfully."""
        # Setup mock response
        mock_elasticsearch.indices.delete_index_template.return_value = {
            "acknowledged": True
        }

        # Test deletion
        result = template_manager.delete("test-template")
        assert result is True
        mock_elasticsearch.indices.delete_index_template.assert_called_once_with(
            name="test-template"
        )

    def test_delete_error(self, template_manager, mock_elasticsearch):
        """Test error handling when deleting a template."""
        # Setup mock to raise an exception
        mock_elasticsearch.indices.delete_index_template.side_effect = Exception(
            "Test error"
        )

        # Test error handling
        with pytest.raises(
            OperationError, match="Failed to delete template test-template: Test error"
        ):
            template_manager.delete("test-template")

    def test_list_success(self, template_manager, mock_elasticsearch):
        """Test listing all templates successfully."""
        # Setup mock response
        mock_response = {
            "index_templates": [
                {"name": "template1", "index_template": {}},
                {"name": "template2", "index_template": {}},
            ]
        }
        mock_elasticsearch.indices.get_index_template.return_value = mock_response

        # Test listing templates
        result = template_manager.list()
        assert result == ["template1", "template2"]
        mock_elasticsearch.indices.get_index_template.assert_called_once()

    def test_list_empty(self, template_manager, mock_elasticsearch):
        """Test listing templates when none exist."""
        # Setup mock response with no templates
        mock_elasticsearch.indices.get_index_template.return_value = {
            "index_templates": []
        }

        # Test listing with no templates
        result = template_manager.list()
        assert result == []
        mock_elasticsearch.indices.get_index_template.assert_called_once()

    def test_list_error(self, template_manager, mock_elasticsearch):
        """Test error handling when listing templates."""
        # Setup mock to raise an exception
        mock_elasticsearch.indices.get_index_template.side_effect = Exception(
            "Test error"
        )

        # Test error handling
        with pytest.raises(
            OperationError, match="Failed to list templates: Test error"
        ):
            template_manager.list()
