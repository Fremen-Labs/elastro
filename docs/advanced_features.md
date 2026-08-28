# Advanced Features

This document outlines the advanced features provided by the `elastro` package for working with Elasticsearch.

## Query Builder

The `QueryBuilder` class provides a fluent interface for building complex Elasticsearch queries without having to manually construct nested dictionaries.

### Basic Usage

```python
from elastro.advanced import QueryBuilder

# Create a simple match query
query = QueryBuilder().match("title", "elasticsearch", operator="and").to_dict()

# Create a match phrase query with slop
query = (
    QueryBuilder()
    .match_phrase("description", "powerful search engine", slop=1)
    .to_dict()
)

# Create a term query for exact matching
query = QueryBuilder().term("status", "active").to_dict()
```

### Available Query Types

- **match**: For full-text search with options like fuzziness
- **match_phrase**: For phrase matching with slop parameter
- **term**: For exact value matching
- **terms**: For matching multiple exact values
- **range**: For numeric/date range queries
- **exists**: To check if a field exists
- **wildcard**: For wildcard pattern matching

### Boolean Queries

The Boolean query builder allows combining multiple query clauses with different boolean logic:

```python
from elastro.advanced import QueryBuilder

# Create a complex bool query
query = (
    QueryBuilder()
    .bool()
    .must(QueryBuilder().match("title", "elasticsearch"))
    .must_not(QueryBuilder().term("status", "deleted"))
    .should(QueryBuilder().match("tags", "search"))
    .should(QueryBuilder().match("tags", "database"))
    .filter(QueryBuilder().range("published_date", gte="2023-01-01"))
    .minimum_should_match(1)
    .build()
    .to_dict()
)
```

The bool query supports:

- **must**: Documents must match these clauses (AND logic)
- **must_not**: Documents must not match these clauses (NOT logic)
- **should**: Documents should match these clauses (OR logic)
- **filter**: Documents must match, but without scoring
- **minimum_should_match**: Minimum number of should clauses that must match

## Aggregation Builder

The `AggregationBuilder` class provides a fluent interface for building Elasticsearch aggregations for data analysis and visualization.

### Basic Usage

```python
from elastro.advanced import AggregationBuilder

# Create a terms aggregation on a field
aggs = AggregationBuilder().terms("status_counts", "status", size=5).to_dict()

# Create a date histogram
aggs = (
    AggregationBuilder()
    .date_histogram(
        "documents_over_time", "created_at", interval="month", format="yyyy-MM"
    )
    .to_dict()
)
```

### Available Aggregation Types

- **terms**: For grouping documents by field values
- **date_histogram**: For time-based grouping
- **histogram**: For numeric range grouping
- **range**: For custom range buckets
- **avg/sum/min/max**: For numeric metrics
- **cardinality**: For counting unique values

### Nested Aggregations

You can create nested aggregations to perform sub-aggregations within each bucket:

```python
from elastro.advanced import AggregationBuilder

# Create parent aggregation
parent_aggs = AggregationBuilder().terms("status_counts", "status")

# Create child aggregation
child_aggs = AggregationBuilder().avg("avg_response_time", "response_time")

# Nest the child under the parent
result = parent_aggs.nested_agg("status_counts", child_aggs).to_dict()
```

## Scroll Helper

The `ScrollHelper` class simplifies working with Elasticsearch's scroll API, which is used to retrieve large result sets efficiently.

### Basic Usage

```python
from elastro.advanced import ScrollHelper
from elastro import ElasticsearchClient

# Initialize the client and scroll helper
client = ElasticsearchClient(hosts=["http://localhost:9200"])
scroll = ScrollHelper(client.native_client)

# Define your query
query = {"match_all": {}}

# Process batches of results
for batch in scroll.scroll(index="my_index", query=query, size=1000):
    for doc in batch:
        process_document(doc)
```

### Scroll Methods

The ScrollHelper provides three main methods:

1. **scroll**: A generator that yields batches of documents
    ```python
    for batch in scroll.scroll(index="my_index", query=query):
        # Process batch
    ```

2. **process_all**: Process all matching documents with a callback function
    ```python
    def process_doc(doc):
        # Process a single document
        print(doc["_id"])


    total = scroll.process_all(index="my_index", query=query, processor=process_doc)
    print(f"Processed {total} documents")
    ```

3. **collect_all**: Retrieve all matching documents into a single list (use carefully with large datasets)
    ```python
    # Limit to maximum 10,000 documents to avoid memory issues
    all_docs = scroll.collect_all(index="my_index", query=query, max_documents=10000)
    ```

### Configuration Options

- **scroll_timeout**: How long Elasticsearch should keep the scroll context alive between requests (default: "1m")
- **size**: Number of documents per batch (default: 1000)
- **source_fields**: List of fields to include in the results
- **max_documents**: Maximum number of documents to collect (for collect_all method)

## Combining Advanced Features

These advanced features can be combined to create powerful Elasticsearch interactions:

```python
from elastro.advanced import QueryBuilder, AggregationBuilder, ScrollHelper
from elastro import ElasticsearchClient

# Initialize the client
client = ElasticsearchClient(hosts=["http://localhost:9200"])

# Build a complex query
query = (
    QueryBuilder()
    .bool()
    .must(QueryBuilder().match("content", "elasticsearch"))
    .filter(QueryBuilder().range("date", gte="2023-01-01"))
    .build()
    .to_dict()
)

# Add aggregations
aggs = AggregationBuilder().terms("top_categories", "category", size=10)

# Execute search with aggregations
results = client.search(
    index="documents", body={"query": query, "aggs": aggs.to_dict()}
)

# Process large result sets with scroll
scroll = ScrollHelper(client.native_client)
for batch in scroll.scroll(index="documents", query=query):
    # Process batch
    pass
```

## Best Practices

- Use the QueryBuilder for complex queries to improve readability and maintainability
- For large result sets, always use the ScrollHelper instead of increasing the size parameter
- Be cautious with memory usage when using collect_all() method
- Use source_fields to limit the fields returned for better performance
- Set appropriate scroll_timeout values based on processing time needed
- Consider using process_all() with a callback for memory-efficient processing
