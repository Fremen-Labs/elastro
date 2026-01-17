"""Integration tests for ScrollHelper functionality."""

import pytest
import time
from elasticsearch import Elasticsearch

from elastro.advanced import ScrollHelper
from elastro.core.client import ElasticsearchClient


@pytest.fixture(scope="module")
def es_client():
    """Create an Elasticsearch client for testing."""
    # Create client with proper authentication
    client = ElasticsearchClient(
        hosts=["http://localhost:9200"],
        username="elastic",
        password="elastic_password",
        verify_certs=False,
    )

    # Connect to Elasticsearch
    client.connect()
    es = client.get_client()

    # Test index and documents
    index_name = "test-scroll-index"

    # Delete index if it exists
    if es.indices.exists(index=index_name):
        es.indices.delete(index=index_name)

    # Create index
    es.indices.create(index=index_name)

    # Create a large number of test documents
    docs = []
    for i in range(1, 201):  # 200 documents
        docs.append(
            {
                "id": i,
                "title": f"Document {i}",
                "category": f"Category {(i % 5) + 1}",
                "value": i * 10,
            }
        )

    # Bulk index documents
    bulk_body = []
    for doc in docs:
        bulk_body.append({"index": {"_index": index_name}})
        bulk_body.append(doc)

    es.bulk(operations=bulk_body, refresh=True)

    # Wait for indexing
    time.sleep(1)

    yield es, index_name

    # Cleanup after tests
    es.indices.delete(index=index_name)
    client.disconnect()


@pytest.mark.integration
def test_scroll_basic(es_client):
    """Test basic scrolling functionality."""
    client, index_name = es_client

    # Create a ScrollHelper
    scroll_helper = ScrollHelper(client)

    # Define a simple query to match all documents
    query = {"match_all": {}}

    # Use scroll method with small batch size to force multiple batches
    all_docs = []
    for batch in scroll_helper.scroll(index=index_name, query=query, size=50):
        all_docs.extend(batch)

    # Verify all 200 documents were retrieved
    assert len(all_docs) == 200

    # Verify document content
    doc_ids = sorted([doc["_source"]["id"] for doc in all_docs])
    assert doc_ids == list(range(1, 201))


@pytest.mark.integration
def test_scroll_with_filter(es_client):
    """Test scrolling with filtered query."""
    client, index_name = es_client

    # Create a ScrollHelper
    scroll_helper = ScrollHelper(client)

    # Define a filtered query to match only specific documents
    # Use match query format instead of term for better compatibility
    query = {"match": {"category.keyword": "Category 3"}}

    # Use scroll method
    all_docs = []
    for batch in scroll_helper.scroll(index=index_name, query=query):
        all_docs.extend(batch)

    # Verify only Category 3 documents were retrieved (40 docs)
    assert len(all_docs) == 40

    # Verify all documents are from Category 3
    for doc in all_docs:
        assert doc["_source"]["category"] == "Category 3"


@pytest.mark.integration
def test_scroll_with_source_fields(es_client):
    """Test scrolling with source field filtering."""
    client, index_name = es_client

    # Create a ScrollHelper
    scroll_helper = ScrollHelper(client)

    # Define query to match all documents
    query = {"match_all": {}}

    # Use scroll method with source fields filter
    all_docs = []
    for batch in scroll_helper.scroll(
        index=index_name, query=query, source_fields=["id", "title"]
    ):
        all_docs.extend(batch)

    # Verify all 200 documents were retrieved
    assert len(all_docs) == 200

    # Verify only specified fields were included
    for doc in all_docs:
        source = doc["_source"]
        assert "id" in source
        assert "title" in source
        assert "category" not in source
        assert "value" not in source


@pytest.mark.integration
def test_process_all(es_client):
    """Test process_all method."""
    client, index_name = es_client

    # Create a ScrollHelper
    scroll_helper = ScrollHelper(client)

    # Define query to match documents with value > 1500
    query = {"range": {"value": {"gt": 1500}}}

    # Create a processor function that collects documents
    processed_docs = []

    def processor(doc):
        processed_docs.append(doc["_source"]["id"])

    # Use process_all method
    total_processed = scroll_helper.process_all(
        index=index_name, query=query, processor=processor
    )

    # Verify correct number of documents processed
    assert total_processed == 50  # docs with id 151-200 have value > 1500
    assert len(processed_docs) == 50

    # Verify processed IDs
    assert sorted(processed_docs) == list(range(151, 201))


@pytest.mark.integration
def test_collect_all(es_client):
    """Test collect_all method."""
    client, index_name = es_client

    # Create a ScrollHelper
    scroll_helper = ScrollHelper(client)

    # Define query to match specific category
    # Use match query format instead of term for better compatibility
    query = {"match": {"category.keyword": "Category 2"}}

    # Use collect_all method
    collected_docs = scroll_helper.collect_all(index=index_name, query=query)

    # Verify correct documents collected
    assert len(collected_docs) == 40  # 40 docs in Category 2

    # Verify all documents are from Category 2
    for doc in collected_docs:
        assert doc["_source"]["category"] == "Category 2"


@pytest.mark.integration
def test_collect_all_with_max_documents(es_client):
    """Test collect_all method with max_documents limit."""
    client, index_name = es_client

    # Create a ScrollHelper
    scroll_helper = ScrollHelper(client)

    # Define query to match all documents
    query = {"match_all": {}}

    # Use collect_all method with limit
    collected_docs = scroll_helper.collect_all(
        index=index_name, query=query, max_documents=75
    )

    # Verify only requested number of documents collected
    assert len(collected_docs) == 75
