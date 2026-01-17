"""
Unit tests for DocumentManager class.
"""

import pytest
from unittest.mock import MagicMock, patch
from elasticsearch import NotFoundError

from elastro.core.document import DocumentManager
from elastro.core.errors import DocumentError, ValidationError, OperationError


class TestDocumentManager:
    """Tests for the DocumentManager class."""

    def test_init(self, es_client):
        """Test that DocumentManager initializes correctly."""
        doc_manager = DocumentManager(es_client)
        assert doc_manager.client == es_client
        assert doc_manager._client == es_client
        assert hasattr(doc_manager, "validator")

    def test_index_success(self, document_manager):
        """Test indexing a document successfully."""
        # Configure the mock
        document_manager.client.client.index.return_value = {
            "result": "created",
            "_id": "test_id",
            "_index": "test_index",
        }

        # Call the method
        document = {"field1": "value1", "field2": "value2"}
        result = document_manager.index(
            index="test_index", id="test_id", document=document, refresh=True
        )

        # Verify the result
        assert result["result"] == "created"
        assert result["_id"] == "test_id"

        # Verify the mock was called with correct parameters
        document_manager.client.client.index.assert_called_once_with(
            index="test_index", id="test_id", document=document, refresh="true"
        )

    def test_index_without_id(self, document_manager):
        """Test indexing a document without specifying an ID."""
        # Configure the mock
        document_manager.client.client.index.return_value = {
            "result": "created",
            "_id": "auto_generated_id",
            "_index": "test_index",
        }

        # Call the method
        document = {"field1": "value1", "field2": "value2"}
        result = document_manager.index(index="test_index", id=None, document=document)

        # Verify the result
        assert result["result"] == "created"

        # Verify the mock was called with correct parameters (no id)
        document_manager.client.client.index.assert_called_once_with(
            index="test_index", document=document, refresh="false"
        )

    def test_index_validation_error_empty_index(self, document_manager):
        """Test index validation with empty index name."""
        with pytest.raises(ValidationError, match="Index name cannot be empty"):
            document_manager.index(index="", id="test_id", document={"field": "value"})

    def test_index_validation_error_invalid_document(self, document_manager):
        """Test index validation with invalid document."""
        with pytest.raises(
            ValidationError, match="Document must be a non-empty dictionary"
        ):
            document_manager.index(index="test_index", id="test_id", document=None)

        with pytest.raises(
            ValidationError, match="Document must be a non-empty dictionary"
        ):
            document_manager.index(index="test_index", id="test_id", document=[])

    def test_index_document_error(self, document_manager):
        """Test handling of document error during indexing."""
        # Configure the mock to raise an exception
        document_manager.client.client.index.side_effect = Exception("Index error")

        # Call the method and expect exception
        with pytest.raises(
            DocumentError, match="Failed to index document: Index error"
        ):
            document_manager.index(
                index="test_index", id="test_id", document={"field": "value"}
            )

    def test_bulk_index_success(self, document_manager):
        """Test bulk indexing documents successfully."""
        # Configure the mock
        document_manager.client.client.bulk.return_value = {
            "took": 30,
            "errors": False,
            "items": [
                {"index": {"_id": "1", "status": 201}},
                {"index": {"_id": "2", "status": 201}},
            ],
        }

        # Call the method
        documents = [{"_id": "1", "field1": "value1"}, {"_id": "2", "field1": "value2"}]
        result = document_manager.bulk_index(
            index="test_index", documents=documents, refresh=True
        )

        # Verify the result
        assert result["errors"] is False
        assert len(result["items"]) == 2

        # Verify the mock was called with correct parameters
        # The operations list should have index operations and documents alternating
        expected_operations = [
            {"index": {"_index": "test_index", "_id": "1"}},
            {"field1": "value1"},
            {"index": {"_index": "test_index", "_id": "2"}},
            {"field1": "value2"},
        ]

        document_manager.client.client.bulk.assert_called_once_with(
            operations=expected_operations, refresh="true"
        )

    def test_bulk_index_without_document_ids(self, document_manager):
        """Test bulk indexing documents without IDs."""
        # Configure the mock
        document_manager.client.client.bulk.return_value = {
            "took": 30,
            "errors": False,
            "items": [
                {"index": {"_id": "auto_1", "status": 201}},
                {"index": {"_id": "auto_2", "status": 201}},
            ],
        }

        # Call the method
        documents = [{"field1": "value1"}, {"field1": "value2"}]
        result = document_manager.bulk_index(index="test_index", documents=documents)

        # Verify the result
        assert result["errors"] is False

        # Verify the mock was called with correct parameters
        expected_operations = [
            {"index": {"_index": "test_index"}},
            {"field1": "value1"},
            {"index": {"_index": "test_index"}},
            {"field1": "value2"},
        ]

        document_manager.client.client.bulk.assert_called_once_with(
            operations=expected_operations, refresh="false"
        )

    def test_bulk_index_validation_errors(self, document_manager):
        """Test bulk index validation errors."""
        # Test empty index name
        with pytest.raises(ValidationError, match="Index name cannot be empty"):
            document_manager.bulk_index(index="", documents=[{"field": "value"}])

        # Test empty documents list
        with pytest.raises(ValidationError, match="Documents must be a non-empty list"):
            document_manager.bulk_index(index="test_index", documents=[])

        # Test invalid documents type
        with pytest.raises(ValidationError, match="Documents must be a non-empty list"):
            document_manager.bulk_index(index="test_index", documents={"not": "a list"})

    def test_bulk_index_error(self, document_manager):
        """Test handling of errors during bulk indexing."""
        # Configure the mock to raise an exception
        document_manager.client.client.bulk.side_effect = Exception("Bulk error")

        # Call the method and expect exception
        with pytest.raises(
            OperationError, match="Failed to bulk index documents: Bulk error"
        ):
            document_manager.bulk_index(
                index="test_index", documents=[{"field": "value"}]
            )

    def test_get_success(self, document_manager):
        """Test getting a document successfully."""
        # Configure the mock
        document_manager.client.client.get.return_value = {
            "_id": "test_id",
            "_index": "test_index",
            "_source": {"field1": "value1", "field2": "value2"},
        }

        # Call the method
        result = document_manager.get(index="test_index", id="test_id")

        # Verify the result
        assert result["_id"] == "test_id"
        assert result["_source"]["field1"] == "value1"

        # Verify the mock was called with correct parameters
        document_manager.client.client.get.assert_called_once_with(
            index="test_index", id="test_id"
        )

    def test_get_validation_errors(self, document_manager):
        """Test get validation errors."""
        # Test empty index name
        with pytest.raises(ValidationError, match="Index name cannot be empty"):
            document_manager.get(index="", id="test_id")

        # Test empty document ID
        with pytest.raises(ValidationError, match="Document ID cannot be empty"):
            document_manager.get(index="test_index", id="")

    def test_get_document_error(self, document_manager):
        """Test handling of errors during get operation."""
        # Configure the mock to raise an exception
        document_manager.client.client.get.side_effect = Exception("Get error")

        # Call the method and expect exception
        with pytest.raises(DocumentError, match="Failed to get document: Get error"):
            document_manager.get(index="test_index", id="test_id")

    def test_update_partial_success(self, document_manager):
        """Test partially updating a document successfully."""
        # Configure the mock
        document_manager.client.client.update.return_value = {
            "result": "updated",
            "_id": "test_id",
            "_index": "test_index",
        }

        # Call the method
        update_doc = {"field1": "updated_value"}
        result = document_manager.update(
            index="test_index",
            id="test_id",
            document=update_doc,
            partial=True,
            refresh=True,
        )

        # Verify the result
        assert result["result"] == "updated"

        # Verify the mock was called with correct parameters
        document_manager.client.client.update.assert_called_once_with(
            index="test_index", id="test_id", body={"doc": update_doc}, refresh="true"
        )

    def test_update_full_success(self, document_manager):
        """Test fully updating a document successfully."""
        # Configure the mocks
        document_manager.index = MagicMock()
        document_manager.index.return_value = {
            "result": "updated",
            "_id": "test_id",
            "_index": "test_index",
        }

        # Call the method
        full_doc = {"field1": "value1", "field2": "value2"}
        result = document_manager.update(
            index="test_index",
            id="test_id",
            document=full_doc,
            partial=False,
            refresh=True,
        )

        # Verify the result
        assert result["result"] == "updated"

        # Verify index was called with correct parameters
        document_manager.index.assert_called_once_with(
            index="test_index", id="test_id", document=full_doc, refresh=True
        )

    def test_update_validation_errors(self, document_manager):
        """Test update validation errors."""
        # Test empty index name
        with pytest.raises(ValidationError, match="Index name cannot be empty"):
            document_manager.update(index="", id="test_id", document={"field": "value"})

        # Test empty document ID
        with pytest.raises(ValidationError, match="Document ID cannot be empty"):
            document_manager.update(
                index="test_index", id="", document={"field": "value"}
            )

        # Test invalid document
        with pytest.raises(
            ValidationError, match="Document must be a non-empty dictionary"
        ):
            document_manager.update(index="test_index", id="test_id", document=None)

    def test_update_document_error(self, document_manager):
        """Test handling of errors during update operation."""
        # Configure the mock to raise an exception
        document_manager.client.client.update.side_effect = Exception("Update error")

        # Call the method and expect exception
        with pytest.raises(
            DocumentError, match="Failed to update document: Update error"
        ):
            document_manager.update(
                index="test_index",
                id="test_id",
                document={"field": "value"},
                partial=True,
            )

    def test_delete_success(self, document_manager):
        """Test deleting a document successfully."""
        # Configure the mock
        document_manager.client.client.delete.return_value = {
            "result": "deleted",
            "_id": "test_id",
            "_index": "test_index",
        }

        # Call the method
        result = document_manager.delete(index="test_index", id="test_id", refresh=True)

        # Verify the result
        assert result["result"] == "deleted"

        # Verify the mock was called with correct parameters
        document_manager.client.client.delete.assert_called_once_with(
            index="test_index", id="test_id", refresh="true"
        )

    def test_delete_validation_errors(self, document_manager):
        """Test delete validation errors."""
        # Test empty index name
        with pytest.raises(ValidationError, match="Index name cannot be empty"):
            document_manager.delete(index="", id="test_id")

        # Test empty document ID
        with pytest.raises(ValidationError, match="Document ID cannot be empty"):
            document_manager.delete(index="test_index", id="")

    def test_delete_document_error(self, document_manager):
        """Test handling of errors during delete operation."""
        # Configure the mock to raise an exception
        document_manager.client.client.delete.side_effect = Exception("Delete error")

        # Call the method and expect exception
        with pytest.raises(
            DocumentError, match="Failed to delete document: Delete error"
        ):
            document_manager.delete(index="test_index", id="test_id")

    def test_bulk_delete_success(self, document_manager):
        """Test bulk deleting documents successfully."""
        # Configure the mock
        document_manager.client.client.bulk.return_value = {
            "took": 30,
            "errors": False,
            "items": [
                {"delete": {"_id": "1", "status": 200}},
                {"delete": {"_id": "2", "status": 200}},
            ],
        }

        # Call the method
        ids = ["1", "2"]
        result = document_manager.bulk_delete(index="test_index", ids=ids, refresh=True)

        # Verify the result
        assert result["errors"] is False

        # Verify the mock was called with correct parameters
        expected_operations = [
            {"delete": {"_index": "test_index", "_id": "1"}},
            {"delete": {"_index": "test_index", "_id": "2"}},
        ]

        document_manager.client.client.bulk.assert_called_once_with(
            operations=expected_operations, refresh="true"
        )

    def test_bulk_delete_validation_errors(self, document_manager):
        """Test bulk delete validation errors."""
        # Test empty index name
        with pytest.raises(ValidationError, match="Index name cannot be empty"):
            document_manager.bulk_delete(index="", ids=["1", "2"])

        # Test empty ids list
        with pytest.raises(ValidationError, match="IDs must be a non-empty list"):
            document_manager.bulk_delete(index="test_index", ids=[])

        # Test invalid ids type
        with pytest.raises(ValidationError, match="IDs must be a non-empty list"):
            document_manager.bulk_delete(index="test_index", ids="not_a_list")

    def test_bulk_delete_error(self, document_manager):
        """Test handling of errors during bulk delete operation."""
        # Configure the mock to raise an exception
        document_manager.client.client.bulk.side_effect = Exception("Bulk delete error")

        # Call the method and expect exception
        with pytest.raises(
            OperationError, match="Failed to bulk delete documents: Bulk delete error"
        ):
            document_manager.bulk_delete(index="test_index", ids=["1", "2"])

    def test_search_success(self, document_manager):
        """Test searching documents successfully."""
        # Configure the mock
        document_manager.client.client.search.return_value = {
            "took": 30,
            "hits": {
                "total": {"value": 2, "relation": "eq"},
                "hits": [
                    {"_id": "1", "_source": {"field1": "value1"}},
                    {"_id": "2", "_source": {"field1": "value2"}},
                ],
            },
        }

        # Call the method
        query = {"match": {"field1": "value"}}
        options = {"size": 10, "from": 0}
        result = document_manager.search(
            index="test_index", query=query, options=options
        )

        # Verify the result
        assert result["hits"]["total"]["value"] == 2
        assert len(result["hits"]["hits"]) == 2

        # Verify the mock was called with correct parameters
        expected_body = {"query": query, "size": 10, "from": 0}

        document_manager.client.client.search.assert_called_once_with(
            index="test_index", body=expected_body
        )

    def test_search_with_source_filter(self, document_manager):
        """Test searching with _source filtering."""
        # Configure the mock
        document_manager.client.client.search.return_value = {
            "took": 30,
            "hits": {
                "total": {"value": 2, "relation": "eq"},
                "hits": [
                    {"_id": "1", "_source": {"field1": "value1"}},
                    {"_id": "2", "_source": {"field1": "value2"}},
                ],
            },
        }

        # Call the method
        query = {"match": {"field1": "value"}}
        options = {"_source": ["field1"], "size": 10}
        result = document_manager.search(
            index="test_index", query=query, options=options
        )

        # Verify the result
        assert result["hits"]["total"]["value"] == 2

        # Verify the mock was called with correct parameters
        expected_body = {"query": query, "_source": ["field1"], "size": 10}

        document_manager.client.client.search.assert_called_once_with(
            index="test_index", body=expected_body
        )

    def test_search_with_aggregations(self, document_manager):
        """Test searching with aggregations."""
        # Configure the mock
        document_manager.client.client.search.return_value = {
            "took": 30,
            "hits": {"total": {"value": 2, "relation": "eq"}},
            "aggregations": {"avg_field": {"value": 25.5}},
        }

        # Call the method
        query = {"match_all": {}}
        options = {
            "size": 0,
            "aggs": {"avg_field": {"avg": {"field": "numeric_field"}}},
        }
        result = document_manager.search(
            index="test_index", query=query, options=options
        )

        # Verify the result
        assert "aggregations" in result
        assert result["aggregations"]["avg_field"]["value"] == 25.5

        # Verify the mock was called with correct parameters
        expected_body = {
            "query": query,
            "size": 0,
            "aggs": {"avg_field": {"avg": {"field": "numeric_field"}}},
        }

        document_manager.client.client.search.assert_called_once_with(
            index="test_index", body=expected_body
        )

    def test_search_validation_errors(self, document_manager):
        """Test search validation errors."""
        # Test empty index name
        with pytest.raises(ValidationError, match="Index name cannot be empty"):
            document_manager.search(index="", query={"match_all": {}})

        # Test empty query
        with pytest.raises(ValidationError, match="Query cannot be empty"):
            document_manager.search(index="test_index", query={})

    def test_search_document_error(self, document_manager):
        """Test handling of errors during search operation."""
        # Configure the mock to raise an exception
        document_manager.client.client.search.side_effect = Exception("Search error")

        # Call the method and expect exception
        with pytest.raises(
            DocumentError, match="Failed to search documents: Search error"
        ):
            document_manager.search(index="test_index", query={"match_all": {}})
