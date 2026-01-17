"""Integration tests for QueryBuilder functionality."""

import pytest
import time
from elasticsearch import Elasticsearch

from elastro.advanced import QueryBuilder
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
    index_name = "test-query-builder-index"

    # Delete index if it exists
    if es.indices.exists(index=index_name):
        es.indices.delete(index=index_name)

    # Create index with mapping
    es.indices.create(
        index=index_name,
        body={
            "mappings": {
                "properties": {
                    "title": {"type": "text"},
                    "description": {"type": "text"},
                    "tags": {"type": "keyword"},
                    "created_at": {"type": "date"},
                    "quantity": {"type": "integer"},
                    "price": {"type": "float"},
                    "is_active": {"type": "boolean"},
                }
            }
        },
    )

    # Index test documents
    docs = [
        {
            "title": "Test document 1",
            "description": "This is a test document for query builder",
            "tags": ["test", "integration", "elastic"],
            "created_at": "2023-01-01T00:00:00",
            "quantity": 10,
            "price": 99.99,
            "is_active": True,
        },
        {
            "title": "Another test document",
            "description": "This is another test document with different content",
            "tags": ["test", "document"],
            "created_at": "2023-01-02T00:00:00",
            "quantity": 5,
            "price": 49.99,
            "is_active": True,
        },
        {
            "title": "Inactive document",
            "description": "This document is not active",
            "tags": ["test", "inactive"],
            "created_at": "2023-01-03T00:00:00",
            "quantity": 0,
            "price": 199.99,
            "is_active": False,
        },
        {
            "title": "Expensive document",
            "description": "This document has a high price",
            "tags": ["test", "expensive"],
            "created_at": "2023-01-04T00:00:00",
            "quantity": 1,
            "price": 999.99,
            "is_active": True,
        },
    ]

    for doc in docs:
        es.index(index=index_name, document=doc, refresh=True)

    # Wait for indexing
    time.sleep(1)

    yield es, index_name

    # Cleanup after tests
    es.indices.delete(index=index_name)
    client.disconnect()


@pytest.mark.integration
def test_match_query(es_client):
    """Test match query against real Elasticsearch."""
    client, index_name = es_client

    # Create a match query using QueryBuilder
    query = QueryBuilder().match("title", "test document").to_dict()

    # Execute search
    result = client.search(index=index_name, query=query)

    # Verify results
    assert result["hits"]["total"]["value"] >= 2
    titles = [hit["_source"]["title"] for hit in result["hits"]["hits"]]
    assert "Test document 1" in titles


@pytest.mark.integration
def test_term_query(es_client):
    """Test term query against real Elasticsearch."""
    client, index_name = es_client

    # Create a term query using QueryBuilder
    query = QueryBuilder().term("tags", "expensive").to_dict()

    # Execute search
    result = client.search(index=index_name, query=query)

    # Verify results
    assert result["hits"]["total"]["value"] == 1
    assert result["hits"]["hits"][0]["_source"]["tags"] == ["test", "expensive"]


@pytest.mark.integration
def test_range_query(es_client):
    """Test range query against real Elasticsearch."""
    client, index_name = es_client

    # Create a range query using QueryBuilder
    query = QueryBuilder().range("price", gte=100.0, lt=1000.0).to_dict()

    # Execute search
    result = client.search(index=index_name, query=query)

    # Verify results
    assert result["hits"]["total"]["value"] == 2

    # Verify the documents match our criteria
    for hit in result["hits"]["hits"]:
        price = hit["_source"]["price"]
        assert price >= 100.0 and price < 1000.0


@pytest.mark.integration
def test_exists_query(es_client):
    """Test exists query against real Elasticsearch."""
    client, index_name = es_client

    # Create an exists query using QueryBuilder
    query = QueryBuilder().exists("quantity").to_dict()

    # Execute search
    result = client.search(index=index_name, query=query)

    # Verify results
    assert result["hits"]["total"]["value"] == 4


@pytest.mark.integration
def test_bool_query(es_client):
    """Test bool query against real Elasticsearch."""
    client, index_name = es_client

    # Create a bool query using QueryBuilder
    query_builder = QueryBuilder()
    bool_query = query_builder.bool()

    # Must be active
    bool_query.must(QueryBuilder().term("is_active", True))

    # Should have high price or high quantity
    bool_query.should(QueryBuilder().range("price", gte=500.0))
    bool_query.should(QueryBuilder().range("quantity", gte=10))

    # Set minimum should match
    bool_query.minimum_should_match(1)

    # Build final query
    query = bool_query.build().to_dict()

    # Execute search
    result = client.search(index=index_name, query=query)

    # Verify results
    assert result["hits"]["total"]["value"] == 2

    # Check that all returned documents match our criteria
    for hit in result["hits"]["hits"]:
        doc = hit["_source"]
        assert doc["is_active"] is True
        assert doc["price"] >= 500.0 or doc["quantity"] >= 10


@pytest.mark.integration
def test_wildcard_query(es_client):
    """Test wildcard query against real Elasticsearch."""
    client, index_name = es_client

    # Create a wildcard query using QueryBuilder
    query = QueryBuilder().wildcard("title", "*document*").to_dict()

    # Execute search
    result = client.search(index=index_name, query=query)

    # Verify results
    assert result["hits"]["total"]["value"] >= 3
