"""
Integration tests for the DocumentManager class.
These tests require a running Elasticsearch instance.
"""

import pytest

from elastro.core.document import DocumentManager
from elastro.core.index import IndexManager
from tests.fixtures.document_fixtures import VALID_DOCUMENT, VALID_DOCUMENT_2


# Mark as integration tests
@pytest.mark.integration
class TestDocumentManagerIntegration:
    """Integration tests for DocumentManager."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self, real_es_client):
        """Set up before and tear down after tests."""
        self.document_manager = DocumentManager(real_es_client)
        self.index_manager = IndexManager(real_es_client)
        self.test_index = "test-integration-docs"
        self.test_document_id = "test-doc-1"

        # Make sure the index doesn't exist before tests
        if self.index_manager.exists(self.test_index):
            self.index_manager.delete(self.test_index)

        # Create the index
        self.index_manager.create(self.test_index)

        yield

        # Clean up after tests
        if self.index_manager.exists(self.test_index):
            self.index_manager.delete(self.test_index)

    def test_index_and_get_document(self):
        """Test indexing and retrieving a document."""
        # Index document
        response = self.document_manager.index(
            index=self.test_index, document=VALID_DOCUMENT, id=self.test_document_id
        )
        assert response["_id"] == self.test_document_id
        assert response["result"] in ["created", "updated"]

        # Refresh the index to make the document available for search
        self.index_manager._client._client.indices.refresh(index=self.test_index)

        # Get document
        document = self.document_manager.get(
            index=self.test_index, id=self.test_document_id
        )

        assert document["_id"] == self.test_document_id
        assert document["found"] is True
        assert document["_source"] == VALID_DOCUMENT

    def test_update_document(self):
        """Test updating a document."""
        # Index document
        self.document_manager.index(
            index=self.test_index, document=VALID_DOCUMENT, id=self.test_document_id
        )

        # Refresh the index
        self.index_manager._client._client.indices.refresh(index=self.test_index)

        # Update document
        updated_fields = {"views": 100, "tags": ["test", "updated"]}
        response = self.document_manager.update(
            index=self.test_index,
            id=self.test_document_id,
            document=updated_fields,
            partial=True,
        )

        assert response["result"] == "updated"

        # Refresh the index
        self.index_manager._client._client.indices.refresh(index=self.test_index)

        # Get updated document
        document = self.document_manager.get(
            index=self.test_index, id=self.test_document_id
        )

        assert document["_source"]["views"] == 100
        assert document["_source"]["tags"] == ["test", "updated"]
        # Other fields should remain unchanged
        assert document["_source"]["title"] == VALID_DOCUMENT["title"]

    def test_delete_document(self):
        """Test deleting a document."""
        # Index document
        self.document_manager.index(
            index=self.test_index, document=VALID_DOCUMENT, id=self.test_document_id
        )

        # Refresh the index
        self.index_manager._client._client.indices.refresh(index=self.test_index)

        # Delete document
        response = self.document_manager.delete(
            index=self.test_index, id=self.test_document_id
        )

        assert response["result"] == "deleted"

        # Refresh the index
        self.index_manager._client._client.indices.refresh(index=self.test_index)

        # Try to get deleted document
        try:
            self.document_manager.get(index=self.test_index, id=self.test_document_id)
            assert False, "Expected document not found error"
        except Exception as e:
            assert "Failed to get document" in str(e) or "not_found" in str(e)

    def test_bulk_index_and_search(self):
        """Test bulk indexing documents and searching."""
        # Prepare documents for bulk indexing - fix format to not include _source
        docs = [
            {
                "_id": "bulk-1",
                "title": VALID_DOCUMENT["title"],
                "content": VALID_DOCUMENT["content"],
                "date": VALID_DOCUMENT["date"],
                "tags": VALID_DOCUMENT["tags"],
                "views": VALID_DOCUMENT["views"],
            },
            {
                "_id": "bulk-2",
                "title": VALID_DOCUMENT_2["title"],
                "content": VALID_DOCUMENT_2["content"],
                "date": VALID_DOCUMENT_2["date"],
                "tags": VALID_DOCUMENT_2["tags"],
                "views": VALID_DOCUMENT_2["views"],
            },
        ]

        # Bulk index
        response = self.document_manager.bulk_index(
            index=self.test_index, documents=docs
        )

        assert not response.get("errors", False)
        assert len(response["items"]) == 2

        # Refresh the index
        self.index_manager._client._client.indices.refresh(index=self.test_index)

        # Search for documents
        search_query = {"match": {"tags": "test"}}

        results = self.document_manager.search(
            index=self.test_index, query=search_query
        )

        assert results["hits"]["total"]["value"] == 2

        # Search with term query
        term_query = {"term": {"tags": "bulk"}}

        results = self.document_manager.search(index=self.test_index, query=term_query)

        assert results["hits"]["total"]["value"] == 1
        assert (
            results["hits"]["hits"][0]["_source"]["title"] == VALID_DOCUMENT_2["title"]
        )
