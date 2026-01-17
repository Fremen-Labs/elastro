"""
Integration tests for complex workflows that use multiple components.
These tests require a running Elasticsearch instance.
"""

import pytest
import time
import uuid
from datetime import datetime

from elastro.core.client import ElasticsearchClient
from elastro.core.index import IndexManager
from elastro.core.document import DocumentManager
from elastro.core.datastream import DatastreamManager


# Mark as integration tests
@pytest.mark.integration
class TestWorkflowIntegration:
    """Integration tests for complex workflows."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self, real_es_client):
        """Set up before and tear down after tests."""
        self.client = real_es_client
        self.index_manager = IndexManager(self.client)
        self.document_manager = DocumentManager(self.client)
        self.datastream_manager = DatastreamManager(self.client)

        # Generate unique test names to avoid conflicts
        self.test_prefix = f"test-{uuid.uuid4().hex[:8]}"
        self.test_index = f"{self.test_prefix}-index"
        self.test_template = f"{self.test_prefix}-template"
        self.test_datastream = f"{self.test_prefix}-datastream"

        # Make sure resources don't exist before tests
        self._cleanup_resources()

        yield

        # Clean up after tests
        self._cleanup_resources()

    def _cleanup_resources(self):
        """Clean up all test resources."""
        # Delete index if exists
        if self.index_manager.exists(self.test_index):
            self.index_manager.delete(self.test_index)

        # Delete datastream if exists
        try:
            self.datastream_manager._client._client.options(
                ignore_status=[404]
            ).indices.delete_data_stream(name=self.test_datastream)
        except Exception:
            pass  # Ignore any errors

    def test_complete_workflow(self):
        """Test a complete workflow using multiple components."""
        # 1. Create an index with custom mappings and settings
        index_body = {
            "settings": {"number_of_shards": 1, "number_of_replicas": 0},
            "mappings": {
                "properties": {
                    "title": {"type": "text"},
                    "description": {"type": "text"},
                    "created_at": {"type": "date"},
                    "priority": {"type": "keyword"},
                    "count": {"type": "integer"},
                }
            },
        }

        create_response = self.index_manager.create(self.test_index, index_body)
        assert create_response["acknowledged"] is True

        # 2. Index documents into the index - fix format to not include _source
        documents = [
            {
                "_id": "doc1",
                "title": "First Document",
                "description": "This is the first test document",
                "created_at": "2023-05-15T10:00:00.000Z",
                "priority": "high",
                "count": 5,
            },
            {
                "_id": "doc2",
                "title": "Second Document",
                "description": "This is the second test document with different priority",
                "created_at": "2023-05-15T11:30:00.000Z",
                "priority": "medium",
                "count": 3,
            },
            {
                "_id": "doc3",
                "title": "Third Document",
                "description": "This is the third test document with low priority",
                "created_at": "2023-05-15T12:45:00.000Z",
                "priority": "low",
                "count": 1,
            },
        ]

        bulk_response = self.document_manager.bulk_index(self.test_index, documents)
        assert not bulk_response.get("errors", False)
        assert len(bulk_response["items"]) == 3

        # Make sure documents are available for search
        self.client._client.indices.refresh(index=self.test_index)

        # 3. Update a document
        update_doc = {"count": 10, "priority": "critical"}
        update_response = self.document_manager.update(
            self.test_index, "doc1", document=update_doc, partial=True
        )
        assert update_response["result"] == "updated"

        # Refresh the index
        self.client._client.indices.refresh(index=self.test_index)

        # 4. Search for documents with different queries
        # a. Search by match query
        match_query = {"match": {"description": "test document"}}

        match_results = self.document_manager.search(self.test_index, match_query)
        assert match_results["hits"]["total"]["value"] == 3

        # b. Search by term query
        term_query = {"term": {"priority": "critical"}}

        term_results = self.document_manager.search(self.test_index, term_query)
        assert term_results["hits"]["total"]["value"] == 1
        assert term_results["hits"]["hits"][0]["_id"] == "doc1"

        # c. Search with range query
        range_query = {"range": {"count": {"gt": 2}}}

        range_results = self.document_manager.search(self.test_index, range_query)
        assert range_results["hits"]["total"]["value"] == 2

        # 5. Create a datastream and index documents to it
        datastream_template = {
            "settings": {"number_of_shards": 1, "number_of_replicas": 0},
            "mappings": {
                "properties": {
                    "@timestamp": {"type": "date"},
                    "event": {"type": "keyword"},
                    "message": {"type": "text"},
                    "source": {"type": "keyword"},
                }
            },
        }

        # Create index template for datastream (required before creating the datastream)
        template_name = f"{self.test_datastream}-template"
        index_template = {
            "index_patterns": [f"{self.test_datastream}*"],
            "data_stream": {},
            "template": datastream_template,
        }

        # Create the template using the raw client
        template_response = self.client._client.indices.put_index_template(
            name=template_name, body=index_template
        )
        assert template_response.get("acknowledged") is True

        # Wait for template to be created
        time.sleep(1)

        # Create datastream
        ds_create_response = self.datastream_manager.create(name=self.test_datastream)
        assert ds_create_response.get("acknowledged") is True

        # Index documents to datastream
        now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        ds_document = {
            "@timestamp": now,
            "event": "test_event",
            "message": "Test message for datastream",
            "source": "integration_test",
        }

        # Use the raw client to index to datastream
        index_response = self.client._client.index(
            index=self.test_datastream,
            document=ds_document,
            id="test-ds-doc-1",
            op_type="create",  # Required for datastreams
        )
        assert index_response["result"] == "created"

        # Refresh datastream
        self.client._client.indices.refresh(index=self.test_datastream)

        # Search in datastream
        ds_query = {"match": {"event": "test_event"}}

        ds_results = self.client._client.search(
            index=self.test_datastream, query=ds_query
        )

        assert ds_results["hits"]["total"]["value"] == 1
        assert ds_results["hits"]["hits"][0]["_source"]["source"] == "integration_test"

        # 6. Rollover the datastream
        rollover_response = self.datastream_manager.rollover(
            name=self.test_datastream, conditions={"max_docs": 1}
        )
        assert rollover_response.get("acknowledged") is True

        # 7. Get datastream info and verify generation is incremented
        ds_info = self.datastream_manager.get(self.test_datastream)
        assert (
            ds_info["generation"] > 1
        )  # Generation should be incremented after rollover

        # 8. Delete a document from the index
        delete_response = self.document_manager.delete(self.test_index, "doc3")
        assert delete_response["result"] == "deleted"

        # Refresh the index
        self.client._client.indices.refresh(index=self.test_index)

        # 9. Verify document count
        count_query = {"match_all": {}}
        count_results = self.document_manager.search(self.test_index, count_query)
        assert count_results["hits"]["total"]["value"] == 2

        # 10. Close and open the index
        close_response = self.index_manager.close(self.test_index)
        assert close_response["acknowledged"] is True

        open_response = self.index_manager.open(self.test_index)
        assert open_response["acknowledged"] is True

        # Refresh the index
        self.client._client.indices.refresh(index=self.test_index)

        # 11. Verify we can still search after reopening
        final_query = {"match_all": {}}
        final_results = self.document_manager.search(self.test_index, final_query)
        assert final_results["hits"]["total"]["value"] == 2
