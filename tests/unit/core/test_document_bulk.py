"""
Unit tests for the document bulk operations module.

Tests both the deprecated BulkDocumentManager shim and the new
DocumentManager.bulk_index_sync() / bulk_delete_sync() methods.
"""

import warnings
import pytest
from unittest.mock import MagicMock, PropertyMock
from elastro.core.document_bulk import BulkDocumentManager
from elastro.core.document import DocumentManager
from elastro.core.errors import DocumentError, ValidationError
from elastro.core.client import ElasticsearchClient


@pytest.fixture
def mock_es_client():
    """
    Fixture that provides a mock Elasticsearch client compatible with
    BaseManager's _ensure_connected() and _handle_response() patterns.
    """
    client = MagicMock(spec=ElasticsearchClient)
    # BaseManager uses get_client() — not .client directly
    mock_raw = MagicMock()
    client.get_client.return_value = mock_raw
    # Also support direct .client access for backward-compat assertions
    type(client).client = PropertyMock(return_value=mock_raw)
    return client


class TestDocumentManagerBulkSync:
    """Tests for the new DocumentManager sync bulk methods."""

    @pytest.mark.parametrize(
        "index,documents,refresh",
        [
            ("test-index", [{"field": "value"}], False),
            ("test-index", [{"field": "value"}], True),
            ("test-index", [{"_id": "doc1", "field": "value"}], False),
            (
                "test-index",
                [
                    {"_id": "doc1", "field": "value"},
                    {"_id": "doc2", "field": "value2"},
                ],
                False,
            ),
        ],
    )
    def test_bulk_index_sync_success(self, mock_es_client, index, documents, refresh):
        """Test successful synchronous bulk index operation."""
        expected_response = {"items": [], "took": 5, "errors": False}
        mock_es_client.get_client().bulk.return_value = expected_response

        manager = DocumentManager(mock_es_client)
        response = manager.bulk_index_sync(index, documents, refresh)

        # _handle_response wraps the raw response
        assert response == expected_response

        _, kwargs = mock_es_client.get_client().bulk.call_args
        operations = kwargs.get("operations", [])

        # Each document should generate 2 items in operations list
        assert len(operations) == len(documents) * 2

        # Check refresh parameter
        assert kwargs.get("refresh") == ("true" if refresh else "false")

        # Verify structure of operations
        for i in range(0, len(operations), 2):
            assert "index" in operations[i]
            assert operations[i]["index"]["_index"] == index

    def test_bulk_index_sync_does_not_mutate_input(self, mock_es_client):
        """The _id key must NOT be removed from the caller's original documents."""
        expected_response = {"items": [], "took": 5, "errors": False}
        mock_es_client.get_client().bulk.return_value = expected_response

        docs = [{"_id": "doc1", "field": "value"}]
        manager = DocumentManager(mock_es_client)
        manager.bulk_index_sync("test-index", docs)

        # Caller's original document must still have _id
        assert "_id" in docs[0]

    def test_bulk_index_sync_empty_index(self, mock_es_client):
        """Test bulk index with empty index name."""
        manager = DocumentManager(mock_es_client)
        with pytest.raises(ValidationError, match="Index name cannot be empty"):
            manager.bulk_index_sync("", [{"field": "value"}])

    def test_bulk_index_sync_empty_documents(self, mock_es_client):
        """Test bulk index with empty documents list."""
        manager = DocumentManager(mock_es_client)
        with pytest.raises(ValidationError, match="Documents must be a non-empty list"):
            manager.bulk_index_sync("test-index", [])

    def test_bulk_index_sync_invalid_documents(self, mock_es_client):
        """Test bulk index with invalid documents."""
        manager = DocumentManager(mock_es_client)
        with pytest.raises(ValidationError, match="All documents must be dictionaries"):
            manager.bulk_index_sync("test-index", ["not-a-dict"])

    def test_bulk_index_sync_client_error(self, mock_es_client):
        """Test bulk index with client error."""
        mock_es_client.get_client().bulk.side_effect = Exception("Connection error")

        manager = DocumentManager(mock_es_client)
        with pytest.raises(DocumentError, match="Failed to bulk index documents"):
            manager.bulk_index_sync("test-index", [{"field": "value"}])

    @pytest.mark.parametrize(
        "index,ids,refresh",
        [
            ("test-index", ["doc1"], False),
            ("test-index", ["doc1"], True),
            ("test-index", ["doc1", "doc2", "doc3"], False),
        ],
    )
    def test_bulk_delete_sync_success(self, mock_es_client, index, ids, refresh):
        """Test successful synchronous bulk delete operation."""
        expected_response = {"items": [], "took": 5, "errors": False}
        mock_es_client.get_client().bulk.return_value = expected_response

        manager = DocumentManager(mock_es_client)
        response = manager.bulk_delete_sync(index, ids, refresh)

        assert response == expected_response

        _, kwargs = mock_es_client.get_client().bulk.call_args
        operations = kwargs.get("operations", [])

        # Each ID should generate 1 delete operation
        assert len(operations) == len(ids)

        assert kwargs.get("refresh") == ("true" if refresh else "false")

        for i, op in enumerate(operations):
            assert "delete" in op
            assert op["delete"]["_index"] == index
            assert op["delete"]["_id"] == ids[i]

    def test_bulk_delete_sync_empty_index(self, mock_es_client):
        manager = DocumentManager(mock_es_client)
        with pytest.raises(ValidationError, match="Index name cannot be empty"):
            manager.bulk_delete_sync("", ["doc1"])

    def test_bulk_delete_sync_empty_ids(self, mock_es_client):
        manager = DocumentManager(mock_es_client)
        with pytest.raises(ValidationError, match="IDs must be a non-empty list"):
            manager.bulk_delete_sync("test-index", [])

    def test_bulk_delete_sync_client_error(self, mock_es_client):
        mock_es_client.get_client().bulk.side_effect = Exception("Connection error")

        manager = DocumentManager(mock_es_client)
        with pytest.raises(DocumentError, match="Failed to bulk delete documents"):
            manager.bulk_delete_sync("test-index", ["doc1"])


class TestBulkDocumentManagerDeprecation:
    """Tests that the deprecated shim still works and emits warnings."""

    def test_deprecation_warning(self, mock_es_client):
        """BulkDocumentManager should emit a DeprecationWarning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            BulkDocumentManager(mock_es_client)
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message).lower()

    def test_shim_delegates_bulk_index(self, mock_es_client):
        """Shim bulk_index should delegate to DocumentManager.bulk_index_sync."""
        expected_response = {"items": [], "took": 5, "errors": False}
        mock_es_client.get_client().bulk.return_value = expected_response

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            manager = BulkDocumentManager(mock_es_client)
            response = manager.bulk_index("test-index", [{"field": "value"}])

        assert response == expected_response

    def test_shim_delegates_bulk_delete(self, mock_es_client):
        """Shim bulk_delete should delegate to DocumentManager.bulk_delete_sync."""
        expected_response = {"items": [], "took": 5, "errors": False}
        mock_es_client.get_client().bulk.return_value = expected_response

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            manager = BulkDocumentManager(mock_es_client)
            response = manager.bulk_delete("test-index", ["doc1"])

        assert response == expected_response
