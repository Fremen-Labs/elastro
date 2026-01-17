"""Integration tests for AggregationBuilder functionality."""

import pytest
import time
from datetime import datetime, timedelta
from elasticsearch import Elasticsearch

from elastro.advanced import AggregationBuilder
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
    index_name = "test-aggregations-index"

    # Delete index if it exists
    if es.indices.exists(index=index_name):
        es.indices.delete(index=index_name)

    # Create index with mapping
    es.indices.create(
        index=index_name,
        body={
            "mappings": {
                "properties": {
                    "category": {"type": "keyword"},
                    "subcategory": {"type": "keyword"},
                    "price": {"type": "float"},
                    "quantity": {"type": "integer"},
                    "is_available": {"type": "boolean"},
                    "tags": {"type": "keyword"},
                    "created_date": {"type": "date", "format": "yyyy-MM-dd"},
                }
            }
        },
    )

    # Create base date for test data
    base_date = datetime(2023, 1, 1)

    # Index test documents
    docs = []
    categories = ["electronics", "clothing", "books", "food", "toys"]
    subcategories = {
        "electronics": ["phones", "laptops", "tablets"],
        "clothing": ["shirts", "pants", "shoes"],
        "books": ["fiction", "non-fiction", "educational"],
        "food": ["fresh", "canned", "frozen"],
        "toys": ["board games", "outdoor", "electronic"],
    }

    # Generate 100 test documents
    for i in range(100):
        category_idx = i % 5
        category = categories[category_idx]
        subcategory_idx = i % len(subcategories[category])
        subcategory = subcategories[category][subcategory_idx]

        # Create document with varied properties
        doc = {
            "category": category,
            "subcategory": subcategory,
            "price": 10.0 + (i % 10) * 5.5,
            "quantity": i % 20,
            "is_available": i % 4 != 0,  # 75% available
            "tags": ["tag1", "tag2"] if i % 2 == 0 else ["tag3", "tag4", "tag5"],
            "created_date": (base_date + timedelta(days=i % 30)).strftime("%Y-%m-%d"),
        }
        docs.append(doc)

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
def test_terms_aggregation(es_client):
    """Test terms aggregation against real Elasticsearch."""
    client, index_name = es_client

    # Create a terms aggregation
    agg_builder = AggregationBuilder().terms(
        name="category_count", field="category", size=10
    )

    # Execute search with aggregation
    result = client.search(
        index=index_name, body={"size": 0, "aggs": agg_builder.to_dict()}
    )

    # Verify aggregation results
    aggs = result["aggregations"]["category_count"]["buckets"]
    assert len(aggs) == 5  # 5 categories

    # Verify each category has 20 documents
    for agg in aggs:
        assert agg["doc_count"] == 20


@pytest.mark.integration
def test_date_histogram_aggregation(es_client):
    """Test date_histogram aggregation against real Elasticsearch."""
    client, index_name = es_client

    # Create a date histogram aggregation
    # Update to use fixed_interval instead of interval for ES 7+
    agg_builder = AggregationBuilder()
    date_agg = {
        "date_histogram": {
            "field": "created_date",
            "fixed_interval": "7d",  # Using 7 days for a week
            "format": "yyyy-MM-dd",
        }
    }
    agg_builder._aggregations["date_histogram"] = date_agg

    # Execute search with aggregation
    result = client.search(
        index=index_name, body={"size": 0, "aggs": agg_builder.to_dict()}
    )

    # Verify aggregation results
    aggs = result["aggregations"]["date_histogram"]["buckets"]
    assert len(aggs) > 0  # Multiple weeks in the data

    # Verify each bucket has a valid key_as_string date
    for agg in aggs:
        assert "key_as_string" in agg
        assert "doc_count" in agg


@pytest.mark.integration
def test_range_aggregation(es_client):
    """Test range aggregation against real Elasticsearch."""
    client, index_name = es_client

    # Create a range aggregation
    ranges = [{"to": 20}, {"from": 20, "to": 40}, {"from": 40, "to": 60}, {"from": 60}]

    agg_builder = AggregationBuilder().range(
        name="price_ranges", field="price", ranges=ranges
    )

    # Execute search with aggregation
    result = client.search(
        index=index_name, body={"size": 0, "aggs": agg_builder.to_dict()}
    )

    # Verify aggregation results
    aggs = result["aggregations"]["price_ranges"]["buckets"]
    assert len(aggs) == 4  # 4 ranges defined

    # Verify each range has some documents
    for agg in aggs:
        assert "doc_count" in agg


@pytest.mark.integration
def test_nested_aggregation(es_client):
    """Test nested aggregations against real Elasticsearch."""
    client, index_name = es_client

    # Create a terms aggregation for categories
    parent_agg = AggregationBuilder().terms(name="categories", field="category")

    # Create a child aggregation for subcategories
    child_agg = AggregationBuilder().terms(name="subcategories", field="subcategory")

    # Nest the child aggregation under the parent
    parent_agg.nested_agg("categories", child_agg)

    # Execute search with aggregation
    result = client.search(
        index=index_name, body={"size": 0, "aggs": parent_agg.to_dict()}
    )

    # Verify parent aggregation results
    categories = result["aggregations"]["categories"]["buckets"]
    assert len(categories) == 5  # 5 categories

    # Verify child aggregations for each parent
    for category in categories:
        subcategories = category["subcategories"]["buckets"]
        assert len(subcategories) > 0  # Each category has subcategories


@pytest.mark.integration
def test_metric_aggregations(es_client):
    """Test metric aggregations against real Elasticsearch."""
    client, index_name = es_client

    # Create multiple metric aggregations
    agg_builder = AggregationBuilder()
    agg_builder.avg(name="avg_price", field="price")
    agg_builder.min(name="min_price", field="price")
    agg_builder.max(name="max_price", field="price")
    agg_builder.sum(name="sum_quantity", field="quantity")
    agg_builder.cardinality(name="unique_categories", field="category")

    # Execute search with aggregations
    result = client.search(
        index=index_name, body={"size": 0, "aggs": agg_builder.to_dict()}
    )

    # Verify aggregation results
    aggs = result["aggregations"]

    assert "avg_price" in aggs
    assert aggs["avg_price"]["value"] > 0

    assert "min_price" in aggs
    assert aggs["min_price"]["value"] > 0

    assert "max_price" in aggs
    assert aggs["max_price"]["value"] > aggs["min_price"]["value"]

    assert "sum_quantity" in aggs
    assert aggs["sum_quantity"]["value"] > 0

    assert "unique_categories" in aggs
    assert aggs["unique_categories"]["value"] == 5  # 5 unique categories


@pytest.mark.integration
def test_combined_aggregations(es_client):
    """Test combining multiple aggregation types in one query."""
    client, index_name = es_client

    # Create a terms aggregation
    agg_builder = AggregationBuilder().terms(name="category_stats", field="category")

    # Create metric aggregations as sub-aggregations
    metrics_agg = AggregationBuilder()
    metrics_agg.avg(name="avg_price", field="price")
    metrics_agg.avg(name="avg_quantity", field="quantity")
    metrics_agg.cardinality(name="subcategory_count", field="subcategory")

    # Add metrics as nested aggregations
    agg_builder.nested_agg("category_stats", metrics_agg)

    # Execute search with aggregations
    result = client.search(
        index=index_name, body={"size": 0, "aggs": agg_builder.to_dict()}
    )

    # Verify aggregation results
    categories = result["aggregations"]["category_stats"]["buckets"]

    for category in categories:
        # Each category should have metric sub-aggregations
        assert "avg_price" in category
        assert category["avg_price"]["value"] > 0

        assert "avg_quantity" in category
        assert "subcategory_count" in category
