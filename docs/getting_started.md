# Getting Started with Elastro

This guide will help you get started with Elastro for managing Elasticsearch operations.

## Prerequisites

- Python 3.8 or higher
- An Elasticsearch cluster (version 8.x recommended)
- Access credentials for your Elasticsearch cluster

## Installation

You can install Elastro using pip:

```bash
pip install elastro
```

Or install from source:

```bash
git clone https://github.com/Fremen-Labs/elastro.git
cd elastro
pip install -e .
```

## Configuration

Elastro can be configured in multiple ways:

### Configuration File

Create a file named `elastic.yaml` in your project directory:

```yaml
# elastic.yaml
default:
  hosts:
    - https://elasticsearch:9200
  auth:
    api_key: your-api-key
  timeout: 30
  retry_on_timeout: true
  max_retries: 3
  
# You can define multiple profiles
production:
  hosts:
    - https://prod-es-01:9200
    - https://prod-es-02:9200
  auth:
    username: elastic
    password: password
```

Or use JSON format (`elastic.json`):

```json
{
  "default": {
    "hosts": ["https://elasticsearch:9200"],
    "auth": {
      "api_key": "your-api-key"
    },
    "timeout": 30,
    "retry_on_timeout": true,
    "max_retries": 3
  }
}
```

### Environment Variables

You can also configure the client using environment variables:

```bash
export ELASTIC_HOSTS=https://elasticsearch:9200
export ELASTIC_API_KEY=your-api-key
```

### Programmatic Configuration

You can configure the client directly in your code:

```python
from elastro import ElasticsearchClient

client = ElasticsearchClient(
    hosts=["https://elasticsearch:9200"],
    auth={"api_key": "your-api-key"},
    timeout=30,
    retry_on_timeout=True,
    max_retries=3
)
```

## Basic Usage

### Connecting to Elasticsearch

```python
from elastro import ElasticsearchClient

# Initialize client with configuration
client = ElasticsearchClient()

# Explicitly connect
client.connect()

# Check connection and cluster health
health = client.health()
print(f"Cluster status: {health['status']}")
```

### Creating and Managing Indices

```python
from elastro import IndexManager

# Initialize the index manager with our client
index_manager = IndexManager(client)

# Create a simple index
index_manager.create("simple-index")

# Create an index with custom settings and mappings
index_manager.create(
    name="products",
    settings={
        "number_of_shards": 3,
        "number_of_replicas": 1
    },
    mappings={
        "properties": {
            "name": {"type": "text"},
            "price": {"type": "float"},
            "description": {"type": "text"},
            "created": {"type": "date"}
        }
    }
)

# Check if an index exists
if index_manager.exists("products"):
    # Get index details
    index_info = index_manager.get("products")
    print(index_info)
    
    # Update index settings
    index_manager.update("products", {
        "index": {
            "number_of_replicas": 2
        }
    })
```

### Working with Documents

```python
from elastro import DocumentManager

# Initialize the document manager with our client
doc_manager = DocumentManager(client)

# Index a document
doc_manager.index(
    index="products",
    id="1",
    document={
        "name": "Laptop",
        "price": 999.99,
        "description": "High-performance laptop",
        "created": "2023-05-01T12:00:00"
    }
)

# Bulk index multiple documents
documents = [
    {"id": "2", "document": {"name": "Smartphone", "price": 699.99}},
    {"id": "3", "document": {"name": "Tablet", "price": 499.99}}
]
doc_manager.bulk_index("products", documents)

# Get a document by ID
product = doc_manager.get("products", "1")
print(product)

# Update a document
doc_manager.update(
    index="products",
    id="1",
    document={"price": 899.99},
    partial=True
)

# Delete a document
doc_manager.delete("products", "3")
```

### Searching for Documents

```python
from elastro import DocumentManager

doc_manager = DocumentManager(client)

# Basic search
results = doc_manager.search(
    index="products",
    query={"match": {"name": "laptop"}}
)

# More complex search
results = doc_manager.search(
    index="products",
    query={
        "bool": {
            "must": [
                {"match": {"name": "laptop"}},
                {"range": {"price": {"lte": 1000}}}
            ]
        }
    },
    options={
        "size": 10,
        "from": 0,
        "sort": [{"price": "asc"}]
    }
)

for hit in results["hits"]["hits"]:
    print(f"Product: {hit['_source']['name']}, Price: {hit['_source']['price']}")
```

### Using the CLI

Elastro provides a command-line interface for common operations:

```bash
# Initialize configuration
elastic-cli config init

# List available indices
elastic-cli index list

# Create an index
elastic-cli index create products --shards 3 --replicas 1

# Add a document
elastic-cli doc index products --id 1 --data '{"name": "Laptop", "price": 999.99}'

# Or from a file
elastic-cli doc index products --id 2 --file ./product.json

# Search for documents
elastic-cli doc search products --query 'name:laptop'

# Get index details in YAML format
elastic-cli index get products --format yaml
```

## Next Steps

- Run a scored health assessment: `elastro health assess -o table` — see [Health Commands](./health_commands.md)
- Read the [API Reference](https://github.com/Fremen-Labs/elastro/blob/main/docs/api_reference.md) for detailed information about all available methods
- Explore [Advanced Features](https://github.com/Fremen-Labs/elastro/blob/main/docs/advanced_features.md) for more complex operations
- Check the [Examples](https://github.com/Fremen-Labs/elastro/tree/main/examples) directory for more code samples
