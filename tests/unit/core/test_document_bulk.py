"""
Unit tests for the document bulk operations module.
"""

import pytest
from unittest.mock import MagicMock, patch
from elastro.core.document_bulk import BulkDocumentManager
from elastro.core.errors import DocumentError, ValidationError
from elastro.core.client import ElasticsearchClient


@pytest.fixture
def mock_es_client():
    """
    Fixture that provides a mock Elasticsearch client.
    """
    client = MagicMock(spec=ElasticsearchClient)
    client.client = MagicMock()
    return client


class TestBulkDocumentManager:
    """Tests for the BulkDocumentManager class."""

    def test_init(self, mock_es_client):
        """Test initialization of BulkDocumentManager."""
        manager = BulkDocumentManager(mock_es_client)
        assert manager.client == mock_es_client
        assert hasattr(manager, "validator")

    @pytest.mark.parametrize(
        "index,documents,refresh",
        [
            ("test-index", [{"field": "value"}], False),
            ("test-index", [{"field": "value"}], True),
            ("test-index", [{"_id": "doc1", "field": "value"}], False),
            (
                "test-index",
                [{"_id": "doc1", "field": "value"}, {"_id": "doc2", "field": "value2"}],
                False,
            ),
        ],
    )
    def test_bulk_index_success(self, mock_es_client, index, documents, refresh):
        """Test successful bulk index operation."""
        expected_response = {"items": [], "took": 5, "errors": False}
        mock_es_client.client.bulk.return_value = expected_response

        manager = BulkDocumentManager(mock_es_client)
        response = manager.bulk_index(index, documents, refresh)

        assert response == expected_response

        # Verify correct operations structure
        _, kwargs = mock_es_client.client.bulk.call_args
        operations = kwargs.get("operations", [])

        # Each document should generate 2 items in operations list
        assert len(operations) == len(documents) * 2

        # Check refresh parameter
        assert kwargs.get("refresh") == ("true" if refresh else "false")

        # Verify structure of operations
        for i in range(0, len(operations), 2):
            assert "index" in operations[i]
            assert operations[i]["index"]["_index"] == index

            # If original document had _id, it should be in the action
            original_doc = documents[i // 2]
            if "_id" in original_doc:
                doc_id = original_doc["_id"]
                assert operations[i]["index"]["_id"] == doc_id
                # And should not be in the document body
                assert "_id" not in operations[i + 1]

    def test_bulk_index_empty_index(self, mock_es_client):
        """Test bulk index with empty index name."""
        manager = BulkDocumentManager(mock_es_client)

        with pytest.raises(ValidationError, match="Index name cannot be empty"):
            manager.bulk_index("", [{"field": "value"}])

    def test_bulk_index_empty_documents(self, mock_es_client):
        """Test bulk index with empty documents list."""
        manager = BulkDocumentManager(mock_es_client)

        with pytest.raises(ValidationError, match="Documents must be a non-empty list"):
            manager.bulk_index("test-index", [])

    def test_bulk_index_invalid_documents(self, mock_es_client):
        """Test bulk index with invalid documents."""
        manager = BulkDocumentManager(mock_es_client)

        with pytest.raises(ValidationError, match="All documents must be dictionaries"):
            manager.bulk_index("test-index", ["not-a-dict"])

    def test_bulk_index_client_error(self, mock_es_client):
        """Test bulk index with client error."""
        mock_es_client.client.bulk.side_effect = Exception("Connection error")

        manager = BulkDocumentManager(mock_es_client)

        with pytest.raises(DocumentError, match="Failed to bulk index documents"):
            manager.bulk_index("test-index", [{"field": "value"}])

    @pytest.mark.parametrize(
        "index,ids,refresh",
        [
            ("test-index", ["doc1"], False),
            ("test-index", ["doc1"], True),
            ("test-index", ["doc1", "doc2", "doc3"], False),
        ],
    )
    def test_bulk_delete_success(self, mock_es_client, index, ids, refresh):
        """Test successful bulk delete operation."""
        expected_response = {"items": [], "took": 5, "errors": False}
        mock_es_client.client.bulk.return_value = expected_response

        manager = BulkDocumentManager(mock_es_client)
        response = manager.bulk_delete(index, ids, refresh)

        assert response == expected_response

        # Verify correct operations structure
        _, kwargs = mock_es_client.client.bulk.call_args
        operations = kwargs.get("operations", [])

        # Each ID should generate 1 delete operation
        assert len(operations) == len(ids)

        # Check refresh parameter
        assert kwargs.get("refresh") == ("true" if refresh else "false")

        # Verify structure of operations
        for i, op in enumerate(operations):
            assert "delete" in op
            assert op["delete"]["_index"] == index
            assert op["delete"]["_id"] == ids[i]

    def test_bulk_delete_empty_index(self, mock_es_client):
        """Test bulk delete with empty index name."""
        manager = BulkDocumentManager(mock_es_client)

        with pytest.raises(ValidationError, match="Index name cannot be empty"):
            manager.bulk_delete("", ["doc1"])

    def test_bulk_delete_empty_ids(self, mock_es_client):
        """Test bulk delete with empty IDs list."""
        manager = BulkDocumentManager(mock_es_client)

        with pytest.raises(ValidationError, match="IDs must be a non-empty list"):
            manager.bulk_delete("test-index", [])

    def test_bulk_delete_client_error(self, mock_es_client):
        """Test bulk delete with client error."""
        mock_es_client.client.bulk.side_effect = Exception("Connection error")

        manager = BulkDocumentManager(mock_es_client)

        with pytest.raises(DocumentError, match="Failed to bulk delete documents"):
            manager.bulk_delete("test-index", ["doc1"])
