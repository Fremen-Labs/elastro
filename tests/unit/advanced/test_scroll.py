"""Unit tests for the scroll helper module."""

import pytest
from unittest.mock import MagicMock, call

from elastro.advanced.scroll import ScrollHelper


@pytest.fixture
def mock_es_client():
    """Return a mock Elasticsearch client."""
    mock_client = MagicMock()
    return mock_client


@pytest.fixture
def scroll_helper(mock_es_client):
    """Return a ScrollHelper instance with a mocked ES client."""
    return ScrollHelper(mock_es_client)


class TestScrollHelper:
    """Tests for the ScrollHelper class."""

    def test_scroll_initialization(self, scroll_helper, mock_es_client):
        """Test that the ScrollHelper correctly initializes."""
        assert scroll_helper._client == mock_es_client

    def test_scroll_single_batch(self, scroll_helper, mock_es_client):
        """Test scroll method with a single batch of results."""
        # Mock search response with a single batch
        mock_es_client.search.return_value = {
            "_scroll_id": "test_scroll_id",
            "hits": {"hits": [{"_id": "1", "field": "value"}]},
        }

        # Mock scroll response with empty results to end scrolling
        mock_es_client.scroll.return_value = {
            "_scroll_id": "test_scroll_id",
            "hits": {"hits": []},
        }

        # Execute scroll
        results = list(scroll_helper.scroll("test-index", {"match_all": {}}))

        # Assertions
        assert len(results) == 1
        assert results[0] == [{"_id": "1", "field": "value"}]
        mock_es_client.search.assert_called_once()
        mock_es_client.scroll.assert_called_once()
        mock_es_client.clear_scroll.assert_called_once_with(scroll_id="test_scroll_id")

    def test_scroll_multiple_batches(self, scroll_helper, mock_es_client):
        """Test scroll method with multiple batches of results."""
        # Mock search response
        mock_es_client.search.return_value = {
            "_scroll_id": "test_scroll_id_1",
            "hits": {"hits": [{"_id": "1", "field": "value1"}]},
        }

        # Mock scroll responses
        mock_es_client.scroll.side_effect = [
            {
                "_scroll_id": "test_scroll_id_2",
                "hits": {"hits": [{"_id": "2", "field": "value2"}]},
            },
            {"_scroll_id": "test_scroll_id_3", "hits": {"hits": []}},
        ]

        # Execute scroll
        results = list(scroll_helper.scroll("test-index", {"match_all": {}}))

        # Assertions
        assert len(results) == 2
        assert results[0] == [{"_id": "1", "field": "value1"}]
        assert results[1] == [{"_id": "2", "field": "value2"}]
        mock_es_client.search.assert_called_once()
        assert mock_es_client.scroll.call_count == 2
        mock_es_client.clear_scroll.assert_called_once()

    def test_scroll_with_source_fields(self, scroll_helper, mock_es_client):
        """Test scroll method with specified source fields."""
        # Mock search response
        mock_es_client.search.return_value = {
            "_scroll_id": "test_scroll_id",
            "hits": {"hits": [{"_id": "1", "_source": {"field": "value"}}]},
        }

        # Mock scroll response with empty results to end scrolling
        mock_es_client.scroll.return_value = {
            "_scroll_id": "test_scroll_id",
            "hits": {"hits": []},
        }

        # Execute scroll with source fields
        results = list(
            scroll_helper.scroll(
                "test-index", {"match_all": {}}, source_fields=["field"]
            )
        )

        # Verify the source fields were passed in the request
        mock_es_client.search.assert_called_once()
        call_args = mock_es_client.search.call_args[1]
        assert call_args["body"]["_source"] == ["field"]

    def test_scroll_clears_on_exception(self, scroll_helper, mock_es_client):
        """Test that scroll context is cleared when an exception occurs."""
        # Mock search response
        mock_es_client.search.return_value = {
            "_scroll_id": "test_scroll_id",
            "hits": {"hits": [{"_id": "1"}]},
        }

        # Make scroll raise an exception
        mock_es_client.scroll.side_effect = Exception("Test exception")

        # Execute scroll with an expected exception
        with pytest.raises(Exception, match="Test exception"):
            list(scroll_helper.scroll("test-index", {"match_all": {}}))

        # Verify clear_scroll was called despite the exception
        mock_es_client.clear_scroll.assert_called_once_with(scroll_id="test_scroll_id")

    def test_process_all(self, scroll_helper, mock_es_client):
        """Test process_all method."""
        # Mock scroll response data
        mock_es_client.search.return_value = {
            "_scroll_id": "test_scroll_id",
            "hits": {"hits": [{"_id": "1"}, {"_id": "2"}]},
        }

        mock_es_client.scroll.return_value = {
            "_scroll_id": "test_scroll_id",
            "hits": {"hits": []},
        }

        # Create a processor function
        processor = MagicMock()

        # Call process_all
        count = scroll_helper.process_all("test-index", {"match_all": {}}, processor)

        # Assertions
        assert count == 2
        assert processor.call_count == 2
        assert processor.call_args_list == [call({"_id": "1"}), call({"_id": "2"})]

    def test_collect_all(self, scroll_helper, mock_es_client):
        """Test collect_all method."""
        # Mock scroll response data
        mock_es_client.search.return_value = {
            "_scroll_id": "test_scroll_id",
            "hits": {"hits": [{"_id": "1"}, {"_id": "2"}]},
        }

        mock_es_client.scroll.return_value = {
            "_scroll_id": "test_scroll_id",
            "hits": {"hits": [{"_id": "3"}]},
        }

        # Second scroll call returns empty results to end scrolling
        mock_es_client.scroll.side_effect = [
            {"_scroll_id": "test_scroll_id", "hits": {"hits": [{"_id": "3"}]}},
            {"_scroll_id": "test_scroll_id", "hits": {"hits": []}},
        ]

        # Call collect_all
        docs = scroll_helper.collect_all("test-index", {"match_all": {}})

        # Assertions
        assert len(docs) == 3
        assert docs == [{"_id": "1"}, {"_id": "2"}, {"_id": "3"}]

    def test_collect_all_with_max_documents(self, scroll_helper, mock_es_client):
        """Test collect_all method with max_documents limit."""
        # Mock search response
        mock_es_client.search.return_value = {
            "_scroll_id": "test_scroll_id",
            "hits": {"hits": [{"_id": "1"}, {"_id": "2"}, {"_id": "3"}]},
        }

        # We shouldn't need to scroll since we hit our limit in the first batch
        mock_es_client.scroll.return_value = {
            "_scroll_id": "test_scroll_id",
            "hits": {"hits": [{"_id": "4"}]},
        }

        # Call collect_all with max_documents=2
        docs = scroll_helper.collect_all(
            "test-index", {"match_all": {}}, max_documents=2
        )

        # Assertions
        assert len(docs) == 2
        assert docs == [{"_id": "1"}, {"_id": "2"}]
        # Scroll should not be called because we already hit our limit
        mock_es_client.scroll.assert_not_called()

    def test_collect_all_with_max_documents_spanning_batches(
        self, scroll_helper, mock_es_client
    ):
        """Test collect_all with max_documents spanning multiple batches."""
        # Mock search response
        mock_es_client.search.return_value = {
            "_scroll_id": "test_scroll_id_1",
            "hits": {"hits": [{"_id": "1"}, {"_id": "2"}]},
        }

        # Mock scroll response
        mock_es_client.scroll.return_value = {
            "_scroll_id": "test_scroll_id_2",
            "hits": {"hits": [{"_id": "3"}, {"_id": "4"}]},
        }

        # Call collect_all with max_documents=3
        docs = scroll_helper.collect_all(
            "test-index", {"match_all": {}}, max_documents=3
        )

        # Assertions
        assert len(docs) == 3
        assert docs == [{"_id": "1"}, {"_id": "2"}, {"_id": "3"}]
        mock_es_client.scroll.assert_called_once()
