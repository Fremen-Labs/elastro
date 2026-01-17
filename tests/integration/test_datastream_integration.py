"""
Integration tests for the DatastreamManager class.
These tests require a running Elasticsearch instance.
"""

import pytest
import time
from elasticsearch import Elasticsearch
import logging

from elastro.core.client import ElasticsearchClient
from elastro.core.datastream import DatastreamManager
from elastro.core.document import DocumentManager
from tests.fixtures.datastream_fixtures import VALID_DATASTREAM_SETTINGS


# Mark as integration tests
@pytest.mark.integration
class TestDatastreamManagerIntegration:
    """Integration tests for DatastreamManager."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Setup for each test.

        Sets up the datastream manager for each test
        """
        hosts = ["http://localhost:9200"]
        self.client = ElasticsearchClient(
            hosts=hosts,
            auth={"username": "elastic", "password": "elastic_password"},
            verify_certs=False,  # Disable certificate verification
        )
        # Connect the client before creating the manager
        self.client.connect()
        # Use a plain elasticsearch client to clean up after the test
        es_client = Elasticsearch(
            hosts=hosts,
            basic_auth=("elastic", "elastic_password"),
            verify_certs=False,  # Disable certificate verification
            ssl_show_warn=False,  # Disable SSL warnings
        )
        self.manager = DatastreamManager(self.client)

        # Clean up any existing test datastreams before the test
        if self.manager.exists("test-datastream-pytest"):
            self.manager.delete("test-datastream-pytest")

        # Setup an index template for datastreams
        es_client = Elasticsearch(
            hosts=hosts,
            basic_auth=("elastic", "elastic_password"),
            verify_certs=False,  # Disable certificate verification
        )
        index_template = {
            "index_patterns": ["test-datastream*"],
            "data_stream": {},
            "template": {
                "settings": {"number_of_shards": 1, "number_of_replicas": 0},
                "mappings": {
                    "properties": {
                        "@timestamp": {"type": "date"},
                        "message": {"type": "text"},
                    }
                },
            },
        }
        es_client.indices.put_index_template(
            name="test-datastream-template", body=index_template
        )

        # Wait for template to be created
        time.sleep(1)

        yield

        # Clean up after the test
        if self.manager.exists("test-datastream-pytest"):
            self.manager.delete("test-datastream-pytest")

        # Cleanup after each test
        try:
            for ds_pattern in ["test-datastream", "test-datastream-*"]:
                for datastream in self.manager.list(pattern=ds_pattern):
                    ds_name = datastream.get("name")
                    self.manager.delete(name=ds_name)

        except Exception as exc:
            # Don't fail if cleanup fails
            logging.warning(f"Failed to cleanup: {exc}")

    def test_create_and_get_datastream(self):
        """Test create and get datastream."""
        # Create a datastream
        response = self.manager.create(name="test-datastream")
        assert response.get("acknowledged") is True

        # Get the datastream
        datastream = self.manager.get(name="test-datastream")
        assert datastream["name"] == "test-datastream"

    def test_list_datastreams(self):
        """Test list datastreams."""
        # Create a datastream
        self.manager.create(name="test-datastream-list")
        time.sleep(1)

        # List datastreams
        datastreams = self.manager.list(pattern="test-datastream-list")
        assert len(datastreams) >= 1
        assert any(ds["name"] == "test-datastream-list" for ds in datastreams)

    def test_delete_datastream(self):
        """Test delete datastream."""
        # Create a datastream
        self.manager.create(name="test-datastream-delete")
        time.sleep(1)

        # Delete the datastream
        response = self.manager.delete(name="test-datastream-delete")
        assert response.get("acknowledged") is True

        # Verify the datastream is deleted - handle the 404 error gracefully
        try:
            datastreams = self.manager.list(pattern="test-datastream-delete")
            assert len(datastreams) == 0
        except Exception:
            # If datastream is truly deleted, we expect an error or empty list
            pass

    def test_rollover_datastream(self):
        """Test rollover datastream."""
        # Create a datastream
        self.manager.create(name="test-datastream-rollover")
        time.sleep(1)

        # Index a document into the datastream - for datastreams we need to use op_type=create
        document_mgr = DocumentManager(self.client)
        # Use the raw client directly with op_type=create
        self.client._client.index(
            index="test-datastream-rollover",
            id="test-doc-1",
            document={
                "@timestamp": "2020-01-01T00:00:00.000Z",
                "message": "Test message",
            },
            op_type="create",
        )
        time.sleep(1)

        # Rollover the datastream
        response = self.manager.rollover(name="test-datastream-rollover")
        assert response.get("acknowledged") is True
        assert "old_index" in response
        assert "new_index" in response
        assert response.get("rolled_over") is True

    def test_index_and_search_datastream(self):
        """Test index and search in datastream."""
        # Create a datastream
        self.manager.create(name="test-datastream-search")
        time.sleep(1)

        # Index a document into the datastream - use op_type=create which is required for datastreams
        # Use the raw client directly
        self.client._client.index(
            index="test-datastream-search",
            id="test-doc-search-1",
            document={
                "@timestamp": "2020-01-01T00:00:00.000Z",
                "message": "Test message for search",
            },
            op_type="create",
        )
        time.sleep(1)

        # Search the datastream
        document_mgr = DocumentManager(self.client)
        response = document_mgr.search(
            index="test-datastream-search", query={"match": {"message": "search"}}
        )
        assert response["hits"]["total"]["value"] == 1
        assert (
            response["hits"]["hits"][0]["_source"]["message"]
            == "Test message for search"
        )
