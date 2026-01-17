"""Unit tests for alias management utilities."""

import pytest
from unittest.mock import MagicMock, patch

from elastro.core.client import ElasticsearchClient
from elastro.core.errors import OperationError
from elastro.utils.aliases import AliasManager, AliasAction


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
def alias_manager(es_client):
    """Return an AliasManager instance with a mocked client."""
    return AliasManager(es_client)


class TestAliasAction:
    """Test suite for AliasAction model."""

    def test_init_with_add(self):
        """Test initializing AliasAction with add action."""
        add_action = {"index": "my-index", "alias": "my-alias"}
        action = AliasAction(add=add_action)
        assert action.add == add_action
        assert action.remove is None

    def test_init_with_remove(self):
        """Test initializing AliasAction with remove action."""
        remove_action = {"index": "my-index", "alias": "my-alias"}
        action = AliasAction(remove=remove_action)
        assert action.remove == remove_action
        assert action.add is None

    def test_init_with_both(self):
        """Test initializing AliasAction with both add and remove actions."""
        add_action = {"index": "my-index", "alias": "my-alias"}
        remove_action = {"index": "old-index", "alias": "my-alias"}
        action = AliasAction(add=add_action, remove=remove_action)
        assert action.add == add_action
        assert action.remove == remove_action


class TestAliasManager:
    """Test suite for AliasManager class."""

    def test_init(self, es_client):
        """Test initializing AliasManager."""
        manager = AliasManager(es_client)
        assert manager._client == es_client
        assert manager._es == es_client.client

    def test_create_success(self, alias_manager, mock_elasticsearch):
        """Test creating an alias successfully."""
        # Setup mock response
        mock_elasticsearch.indices.put_alias.return_value = {"acknowledged": True}

        # Test basic creation
        result = alias_manager.create(name="test-alias", index="test-index")
        assert result is True
        mock_elasticsearch.indices.put_alias.assert_called_once_with(
            index="test-index", name="test-alias", body={}
        )

        # Reset mock
        mock_elasticsearch.indices.put_alias.reset_mock()

        # Test with filter query
        filter_query = {"term": {"user": "john"}}
        result = alias_manager.create(
            name="filtered-alias", index="test-index", filter_query=filter_query
        )
        assert result is True
        mock_elasticsearch.indices.put_alias.assert_called_once_with(
            index="test-index", name="filtered-alias", body={"filter": filter_query}
        )

        # Reset mock
        mock_elasticsearch.indices.put_alias.reset_mock()

        # Test with routing
        result = alias_manager.create(
            name="routed-alias", index="test-index", routing="1"
        )
        assert result is True
        mock_elasticsearch.indices.put_alias.assert_called_once_with(
            index="test-index", name="routed-alias", body={"routing": "1"}
        )

    def test_create_error(self, alias_manager, mock_elasticsearch):
        """Test error handling when creating an alias."""
        # Setup mock to raise an exception
        mock_elasticsearch.indices.put_alias.side_effect = Exception("Test error")

        # Test error handling
        with pytest.raises(
            OperationError, match="Failed to create alias test-alias: Test error"
        ):
            alias_manager.create(name="test-alias", index="test-index")

    def test_get_all_aliases(self, alias_manager, mock_elasticsearch):
        """Test getting all aliases."""
        # Setup mock response
        mock_response = {
            "index1": {"aliases": {"alias1": {}, "alias2": {}}},
            "index2": {"aliases": {"alias3": {}}},
        }
        mock_elasticsearch.indices.get_alias.return_value = mock_response

        # Test getting all aliases
        result = alias_manager.get()
        assert result == mock_response
        mock_elasticsearch.indices.get_alias.assert_called_once_with()

    def test_get_alias_by_name(self, alias_manager, mock_elasticsearch):
        """Test getting aliases by name."""
        # Setup mock response
        mock_response = {
            "index1": {"aliases": {"alias1": {}}},
            "index2": {"aliases": {"alias1": {}}},
        }
        mock_elasticsearch.indices.get_alias.return_value = mock_response

        # Test getting aliases by name
        result = alias_manager.get(name="alias1")
        assert result == mock_response
        mock_elasticsearch.indices.get_alias.assert_called_once_with(name="alias1")

    def test_get_alias_by_index(self, alias_manager, mock_elasticsearch):
        """Test getting aliases by index."""
        # Setup mock response
        mock_response = {"index1": {"aliases": {"alias1": {}, "alias2": {}}}}
        mock_elasticsearch.indices.get_alias.return_value = mock_response

        # Test getting aliases by index
        result = alias_manager.get(index="index1")
        assert result == mock_response
        mock_elasticsearch.indices.get_alias.assert_called_once_with(index="index1")

    def test_get_alias_by_name_and_index(self, alias_manager, mock_elasticsearch):
        """Test getting aliases by both name and index."""
        # Setup mock response
        mock_response = {"index1": {"aliases": {"alias1": {}}}}
        mock_elasticsearch.indices.get_alias.return_value = mock_response

        # Test getting aliases by name and index
        result = alias_manager.get(name="alias1", index="index1")
        assert result == mock_response
        mock_elasticsearch.indices.get_alias.assert_called_once_with(
            name="alias1", index="index1"
        )

    def test_get_alias_error(self, alias_manager, mock_elasticsearch):
        """Test error handling when getting aliases."""
        # Setup mock to raise an exception
        mock_elasticsearch.indices.get_alias.side_effect = Exception("Test error")

        # Test error handling
        with pytest.raises(
            OperationError, match="Failed to get alias information: Test error"
        ):
            alias_manager.get()

    def test_exists_true(self, alias_manager, mock_elasticsearch):
        """Test checking if an alias exists and it does."""
        # Setup mock response
        mock_elasticsearch.indices.exists_alias.return_value = True

        # Test checking if alias exists
        result = alias_manager.exists(name="test-alias")
        assert result is True
        mock_elasticsearch.indices.exists_alias.assert_called_once_with(
            name="test-alias"
        )

    def test_exists_with_index(self, alias_manager, mock_elasticsearch):
        """Test checking if an alias exists for a specific index."""
        # Setup mock response
        mock_elasticsearch.indices.exists_alias.return_value = True

        # Test checking if alias exists for index
        result = alias_manager.exists(name="test-alias", index="test-index")
        assert result is True
        mock_elasticsearch.indices.exists_alias.assert_called_once_with(
            name="test-alias", index="test-index"
        )

    def test_exists_false(self, alias_manager, mock_elasticsearch):
        """Test checking if an alias exists and it doesn't."""
        # Setup mock response
        mock_elasticsearch.indices.exists_alias.return_value = False

        # Test checking if alias exists
        result = alias_manager.exists(name="nonexistent-alias")
        assert result is False
        mock_elasticsearch.indices.exists_alias.assert_called_once_with(
            name="nonexistent-alias"
        )

    def test_exists_error(self, alias_manager, mock_elasticsearch):
        """Test error handling when checking if an alias exists."""
        # Setup mock to raise an exception
        mock_elasticsearch.indices.exists_alias.side_effect = Exception("Test error")

        # Test error handling - should return False
        result = alias_manager.exists(name="test-alias")
        assert result is False
        mock_elasticsearch.indices.exists_alias.assert_called_once_with(
            name="test-alias"
        )

    def test_delete_success(self, alias_manager, mock_elasticsearch):
        """Test deleting an alias successfully."""
        # Setup mock response
        mock_elasticsearch.indices.delete_alias.return_value = {"acknowledged": True}

        # Test deleting an alias
        result = alias_manager.delete(name="test-alias")
        assert result is True
        mock_elasticsearch.indices.delete_alias.assert_called_once_with(
            name="test-alias", index="*"
        )

    def test_delete_with_index(self, alias_manager, mock_elasticsearch):
        """Test deleting an alias from a specific index."""
        # Setup mock response
        mock_elasticsearch.indices.delete_alias.return_value = {"acknowledged": True}

        # Test deleting an alias from a specific index
        result = alias_manager.delete(name="test-alias", index="test-index")
        assert result is True
        mock_elasticsearch.indices.delete_alias.assert_called_once_with(
            name="test-alias", index="test-index"
        )

    def test_delete_error(self, alias_manager, mock_elasticsearch):
        """Test error handling when deleting an alias."""
        # Setup mock to raise an exception
        mock_elasticsearch.indices.delete_alias.side_effect = Exception("Test error")

        # Test error handling
        with pytest.raises(
            OperationError, match="Failed to delete alias test-alias: Test error"
        ):
            alias_manager.delete(name="test-alias")

    def test_update_success(self, alias_manager, mock_elasticsearch):
        """Test updating aliases successfully."""
        # Setup mock response
        mock_elasticsearch.indices.update_aliases.return_value = {"acknowledged": True}

        # Setup actions
        actions = [
            {"add": {"index": "index1", "alias": "alias1"}},
            {"remove": {"index": "index2", "alias": "alias2"}},
        ]

        # Test updating aliases
        result = alias_manager.update(actions=actions)
        assert result is True
        mock_elasticsearch.indices.update_aliases.assert_called_once_with(
            body={"actions": actions}
        )

    def test_update_with_alias_action_objects(self, alias_manager, mock_elasticsearch):
        """Test updating aliases with AliasAction objects."""
        # Setup mock response
        mock_elasticsearch.indices.update_aliases.return_value = {"acknowledged": True}

        # Setup actions
        actions = [
            AliasAction(add={"index": "index1", "alias": "alias1"}),
            AliasAction(remove={"index": "index2", "alias": "alias2"}),
        ]

        # Expected result to be passed to ES client
        expected_actions = [
            {"add": {"index": "index1", "alias": "alias1"}},
            {"remove": {"index": "index2", "alias": "alias2"}},
        ]

        # Test updating aliases
        result = alias_manager.update(actions=actions)
        assert result is True
        mock_elasticsearch.indices.update_aliases.assert_called_once_with(
            body={"actions": expected_actions}
        )

    def test_update_error(self, alias_manager, mock_elasticsearch):
        """Test error handling when updating aliases."""
        # Setup mock to raise an exception
        mock_elasticsearch.indices.update_aliases.side_effect = Exception("Test error")

        # Setup actions
        actions = [
            {"add": {"index": "index1", "alias": "alias1"}},
            {"remove": {"index": "index2", "alias": "alias2"}},
        ]

        # Test error handling
        with pytest.raises(
            OperationError, match="Failed to update aliases: Test error"
        ):
            alias_manager.update(actions=actions)

    def test_list_all_aliases(self, alias_manager, mock_elasticsearch):
        """Test listing all aliases."""
        # Setup mock response
        mock_response = {
            "index1": {"aliases": {"alias1": {}, "alias2": {}}},
            "index2": {"aliases": {"alias3": {}}},
        }
        mock_elasticsearch.indices.get_alias.return_value = mock_response

        # Test listing all aliases
        result = alias_manager.list()
        assert set(result) == {"alias1", "alias2", "alias3"}
        mock_elasticsearch.indices.get_alias.assert_called_once_with()

    def test_list_aliases_for_index(self, alias_manager, mock_elasticsearch):
        """Test listing aliases for a specific index."""
        # Setup mock response
        mock_response = {"index1": {"aliases": {"alias1": {}, "alias2": {}}}}
        mock_elasticsearch.indices.get_alias.return_value = mock_response

        # Test listing aliases for a specific index
        result = alias_manager.list(index="index1")
        assert set(result) == {"alias1", "alias2"}
        mock_elasticsearch.indices.get_alias.assert_called_once_with(index="index1")

    def test_list_aliases_error(self, alias_manager, mock_elasticsearch):
        """Test error handling when listing aliases."""
        # Setup mock to raise an exception
        mock_elasticsearch.indices.get_alias.side_effect = Exception("Test error")

        # Test error handling
        with pytest.raises(OperationError, match="Failed to list aliases: Test error"):
            alias_manager.list()
