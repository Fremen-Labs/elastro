#!/usr/bin/env python3
"""
Elastro - Search Operations Example

This example demonstrates how to perform various search operations
using the DocumentManager and advanced search features.
"""

from elastro import ElasticsearchClient, IndexManager, DocumentManager
from elastro.advanced import QueryBuilder, AggregationBuilder


def create_client():
    """Create and connect an Elasticsearch client"""
    client = ElasticsearchClient()
    client.connect()
    return client


def setup_test_data(client):
    """Create test index and populate with sample data"""
    # Create index
    index_manager = IndexManager(client)
    index_name = "products"

    if index_manager.exists(index_name):
        index_manager.delete(index_name)

    print(f"Creating index '{index_name}'...")
    index_manager.create(
        name=index_name,
        settings={"number_of_shards": 1, "number_of_replicas": 0},
        mappings={
            "properties": {
                "name": {"type": "text"},
                "description": {"type": "text"},
                "price": {"type": "float"},
                "category": {"type": "keyword"},
                "subcategory": {"type": "keyword"},
                "brand": {"type": "keyword"},
                "tags": {"type": "keyword"},
                "in_stock": {"type": "boolean"},
                "stock_count": {"type": "integer"},
                "rating": {"type": "float"},
                "created": {"type": "date"},
            }
        },
    )

    # Add sample documents
    doc_manager = DocumentManager(client)

    products = [
        {
            "id": "1",
            "document": {
                "name": "Laptop Pro X",
                "description": "High-performance laptop with 32GB RAM and 1TB SSD",
                "price": 1499.99,
                "category": "electronics",
                "subcategory": "computers",
                "brand": "TechMaster",
                "tags": ["computer", "laptop", "high-performance"],
                "in_stock": True,
                "stock_count": 15,
                "rating": 4.8,
                "created": "2023-01-15T10:00:00",
            },
        },
        {
            "id": "2",
            "document": {
                "name": "Smartphone Ultra",
                "description": "Premium smartphone with high-res camera and 128GB storage",
                "price": 899.99,
                "category": "electronics",
                "subcategory": "phones",
                "brand": "Connectify",
                "tags": ["phone", "smartphone", "camera"],
                "in_stock": True,
                "stock_count": 28,
                "rating": 4.6,
                "created": "2023-02-20T14:30:00",
            },
        },
        {
            "id": "3",
            "document": {
                "name": "Wireless Headphones",
                "description": "Noise-cancelling wireless headphones with 30-hour battery",
                "price": 249.99,
                "category": "electronics",
                "subcategory": "audio",
                "brand": "SoundWave",
                "tags": ["audio", "wireless", "noise-cancelling"],
                "in_stock": True,
                "stock_count": 42,
                "rating": 4.7,
                "created": "2023-03-05T09:15:00",
            },
        },
        {
            "id": "4",
            "document": {
                "name": "Tablet Slim",
                "description": "Lightweight tablet with 10-inch display and 64GB storage",
                "price": 349.99,
                "category": "electronics",
                "subcategory": "computers",
                "brand": "TechMaster",
                "tags": ["tablet", "portable", "touchscreen"],
                "in_stock": False,
                "stock_count": 0,
                "rating": 4.5,
                "created": "2023-01-30T11:45:00",
            },
        },
        {
            "id": "5",
            "document": {
                "name": "Wireless Earbuds",
                "description": "True wireless earbuds with charging case",
                "price": 129.99,
                "category": "electronics",
                "subcategory": "audio",
                "brand": "SoundWave",
                "tags": ["audio", "wireless", "earbuds"],
                "in_stock": True,
                "stock_count": 50,
                "rating": 4.4,
                "created": "2023-04-10T13:20:00",
            },
        },
        {
            "id": "6",
            "document": {
                "name": "Smart Watch",
                "description": "Fitness tracker and smartwatch with heart rate monitoring",
                "price": 199.99,
                "category": "electronics",
                "subcategory": "wearables",
                "brand": "Connectify",
                "tags": ["watch", "fitness", "wearable"],
                "in_stock": True,
                "stock_count": 35,
                "rating": 4.3,
                "created": "2023-03-25T16:10:00",
            },
        },
        {
            "id": "7",
            "document": {
                "name": "Digital Camera",
                "description": "Professional DSLR camera with 24MP sensor",
                "price": 799.99,
                "category": "electronics",
                "subcategory": "cameras",
                "brand": "OptikPro",
                "tags": ["camera", "professional", "photography"],
                "in_stock": True,
                "stock_count": 12,
                "rating": 4.9,
                "created": "2023-02-05T08:30:00",
            },
        },
        {
            "id": "8",
            "document": {
                "name": "Bluetooth Speaker",
                "description": "Portable waterproof bluetooth speaker",
                "price": 79.99,
                "category": "electronics",
                "subcategory": "audio",
                "brand": "SoundWave",
                "tags": ["audio", "speaker", "portable", "waterproof"],
                "in_stock": True,
                "stock_count": 65,
                "rating": 4.2,
                "created": "2023-05-01T10:45:00",
            },
        },
    ]

    print(f"Indexing {len(products)} products...")
    doc_manager.bulk_index(index_name, products)
    print("Refreshing index to make documents searchable immediately...")
    client.rest_client.indices.refresh(index=index_name)

    return index_name


def simple_search(doc_manager, index_name):
    """Perform a simple match search"""
    print("\n=== Simple Match Search ===")
    query = {"match": {"name": "laptop"}}

    print(f"Searching for 'laptop' in name field...")
    results = doc_manager.search(index_name, query)

    print(f"Found {results['hits']['total']['value']} matches:")
    for hit in results["hits"]["hits"]:
        print(f"  {hit['_source']['name']} (score: {hit['_score']})")

    return results


def term_search(doc_manager, index_name):
    """Perform an exact term search on a keyword field"""
    print("\n=== Term Search ===")
    query = {"term": {"brand": "TechMaster"}}

    print(f"Searching for exact brand 'TechMaster'...")
    results = doc_manager.search(index_name, query)

    print(f"Found {results['hits']['total']['value']} matches:")
    for hit in results["hits"]["hits"]:
        print(f"  {hit['_source']['name']} (brand: {hit['_source']['brand']})")

    return results


def boolean_search(doc_manager, index_name):
    """Perform a boolean search with multiple conditions"""
    print("\n=== Boolean Search ===")
    query = {
        "bool": {
            "must": [
                {"match": {"category": "electronics"}},
                {"match": {"subcategory": "audio"}},
            ],
            "must_not": [{"term": {"in_stock": False}}],
            "should": [{"range": {"price": {"lte": 200}}}],
        }
    }

    print("Searching for in-stock audio products, preferably under $200...")
    results = doc_manager.search(index_name, query)

    print(f"Found {results['hits']['total']['value']} matches:")
    for hit in results["hits"]["hits"]:
        print(
            f"  {hit['_source']['name']} - ${hit['_source']['price']} "
            + f"(subcategory: {hit['_source']['subcategory']})"
        )

    return results


def range_search(doc_manager, index_name):
    """Perform a range search"""
    print("\n=== Range Search ===")
    query = {"range": {"price": {"gte": 200, "lte": 500}}}

    print("Searching for products with price between $200 and $500...")
    results = doc_manager.search(index_name, query, {"sort": [{"price": "asc"}]})

    print(f"Found {results['hits']['total']['value']} matches:")
    for hit in results["hits"]["hits"]:
        print(f"  {hit['_source']['name']} - ${hit['_source']['price']}")

    return results


def fuzzy_search(doc_manager, index_name):
    """Perform a fuzzy search to handle typos"""
    print("\n=== Fuzzy Search ===")
    query = {
        "match": {"name": {"query": "lapton", "fuzziness": "AUTO"}}  # Intentional typo
    }

    print("Searching for 'lapton' (typo for laptop) with fuzzy matching...")
    results = doc_manager.search(index_name, query)

    print(f"Found {results['hits']['total']['value']} matches:")
    for hit in results["hits"]["hits"]:
        print(f"  {hit['_source']['name']} (score: {hit['_score']})")

    return results


def aggregation_search(doc_manager, index_name):
    """Perform a search with aggregations"""
    print("\n=== Aggregation Search ===")

    # Define aggregations
    aggregations = {
        "categories": {"terms": {"field": "subcategory"}},
        "avg_price": {"avg": {"field": "price"}},
        "price_ranges": {
            "range": {
                "field": "price",
                "ranges": [
                    {"to": 100},
                    {"from": 100, "to": 300},
                    {"from": 300, "to": 500},
                    {"from": 500},
                ],
            }
        },
    }

    # Search with minimal query but with aggregations
    query = {"match_all": {}}
    print(
        "Searching with aggregations for categories, average price, and price ranges..."
    )
    results = doc_manager.search(index_name, query, {"size": 0, "aggs": aggregations})

    # Display aggregation results
    print("\nSubcategory Distribution:")
    for bucket in results["aggregations"]["categories"]["buckets"]:
        print(f"  {bucket['key']}: {bucket['doc_count']} products")

    print(f"\nAverage Price: ${results['aggregations']['avg_price']['value']:.2f}")

    print("\nPrice Ranges:")
    for bucket in results["aggregations"]["price_ranges"]["buckets"]:
        from_val = bucket.get("from", "0")
        to_val = bucket.get("to", "∞")
        print(f"  ${from_val} to ${to_val}: {bucket['doc_count']} products")

    return results


def query_builder_search(doc_manager, index_name):
    """Use the QueryBuilder to construct a complex query"""
    print("\n=== QueryBuilder Search ===")

    # Use QueryBuilder to create a complex query
    query_builder = QueryBuilder()

    # Start with a boolean query
    query_builder.bool_query()

    # Must conditions
    query_builder.must().match("category", "electronics")
    query_builder.must().range("rating", gte=4.5)

    # Should conditions (boosts relevance but doesn't exclude)
    query_builder.should().match("tags", "wireless")
    query_builder.should().term("in_stock", True)

    # Get the constructed query
    query = query_builder.build()

    print("Searching for high-rated electronics, preferably wireless and in stock...")
    results = doc_manager.search(index_name, query, {"sort": [{"rating": "desc"}]})

    print(f"Found {results['hits']['total']['value']} matches:")
    for hit in results["hits"]["hits"]:
        tags = ", ".join(hit["_source"]["tags"])
        print(
            f"  {hit['_source']['name']} - Rating: {hit['_source']['rating']} "
            + f"(Tags: {tags}, In Stock: {hit['_source']['in_stock']})"
        )

    return results


def aggregation_builder_search(doc_manager, index_name):
    """Use the AggregationBuilder to construct aggregations"""
    print("\n=== AggregationBuilder Search ===")

    # Use AggregationBuilder to create aggregations
    agg_builder = AggregationBuilder()

    # Add aggregations
    agg_builder.terms("brands", "brand")
    agg_builder.avg("avg_rating", "rating")
    agg_builder.min("min_price", "price")
    agg_builder.max("max_price", "price")

    # Add nested aggregation (brands -> avg price per brand)
    agg_builder.get("brands").avg("avg_price", "price")

    # Get the constructed aggregations
    aggregations = agg_builder.build()

    print("Searching with aggregations built using AggregationBuilder...")
    query = {"match_all": {}}
    results = doc_manager.search(index_name, query, {"size": 0, "aggs": aggregations})

    # Display aggregation results
    print("\nBrands:")
    for bucket in results["aggregations"]["brands"]["buckets"]:
        print(
            f"  {bucket['key']}: {bucket['doc_count']} products, "
            + f"avg price: ${bucket['avg_price']['value']:.2f}"
        )

    print(f"\nOverall Statistics:")
    print(f"  Average Rating: {results['aggregations']['avg_rating']['value']:.2f}")
    print(
        f"  Price Range: ${results['aggregations']['min_price']['value']:.2f} to "
        + f"${results['aggregations']['max_price']['value']:.2f}"
    )

    return results


def cleanup(client, index_name):
    """Clean up test data"""
    index_manager = IndexManager(client)
    if index_manager.exists(index_name):
        print(f"\nCleaning up: deleting index '{index_name}'...")
        index_manager.delete(index_name)
        print(f"Index '{index_name}' deleted.")


def main():
    """Main function demonstrating search operations"""
    try:
        # Create a client and document manager
        client = create_client()
        doc_manager = DocumentManager(client)

        # Set up test data
        index_name = setup_test_data(client)

        # Perform various search operations
        simple_search(doc_manager, index_name)
        term_search(doc_manager, index_name)
        boolean_search(doc_manager, index_name)
        range_search(doc_manager, index_name)
        fuzzy_search(doc_manager, index_name)
        aggregation_search(doc_manager, index_name)
        query_builder_search(doc_manager, index_name)
        aggregation_builder_search(doc_manager, index_name)

        # Clean up
        cleanup(client, index_name)

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
