# Elastro

```text
      .   *   .       .   *   .      .
    .   _   .   *   .    *    .   *
  _ __| | __ _ ___| |_ _ __ ___    .
  / _ \ |/ _` / __| __| '__/ _ \  *
 |  __/ | (_| \__ \ |_| | | (_) |  .
  \___|_|\__,_|___/\__|_|  \___/ .
      .    *     .      *    .   *
```

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)


A comprehensive Python module for managing Elasticsearch operations within pipeline processes.

## Overview

Elastro is a Python library designed to simplify interactions with Elasticsearch. It provides a clean, intuitive API for common Elasticsearch operations including:

- Index management (create, update, delete)
- Document operations (indexing, searching, updating)
- Datastream management
- Advanced query building and search functionality

The library offers both a programmatic API and a command-line interface for seamless integration with various workflows.

## Installation

```bash
pip install elastro
```

Or from source:

```bash
git clone https://github.com/Fremen-Labs/elastro.git
cd elastro
pip install -e .
```

## Basic Usage

### Client Connection

```python
from elastro import ElasticsearchClient

# Connect using API key
client = ElasticsearchClient(
    hosts=["https://elasticsearch:9200"],
    auth={"api_key": "your-api-key"}
)

# Or using basic auth
client = ElasticsearchClient(
    hosts=["https://elasticsearch:9200"],
    auth={"username": "elastic", "password": "password"}
)

# Connect to Elasticsearch
client.connect()
```

### Index Management

```python
from elastro import IndexManager

index_manager = IndexManager(client)

# Create an index
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
    print("Products index exists!")
    
# Delete an index
index_manager.delete("products")
```

### Document Operations

```python
from elastro import DocumentManager

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

# Search for documents
results = doc_manager.search(
    index="products",
    query={"match": {"name": "laptop"}}
)

print(results)
```

### CLI Usage

```bash
# Initialize configuration
elastro config init

# Create an index
elastro index create products --shards 3 --replicas 1

# Interactive Template Wizard
elastro template wizard

# Interactive ILM Policy Wizard
elastro ilm create my-policy

# List ILM Policies (Table View)
elastro ilm list

# Add a document
elastro doc index products --id 1 --file ./product.json

# Search documents
elastro doc search products --term category=laptop
```

### ILM (Index Lifecycle Management)

Elastro provides a powerful CLI for managing ILM policies, including an interactive wizard.

```bash
# List all policies (Table View)
elastro ilm list

# List with full JSON details (limited to first 2)
elastro ilm list --full

# Create a policy using the Interactive Wizard (Recommended)
elastro ilm create my-policy
# Follow the prompts to configure Hot, Warm, Cold, and Delete phases.

# Create a policy from a file
elastro ilm create my-policy --file ./policy.json

# Explain lifecycle status for an index (includes step info for debugging)
elastro ilm explain my-index
```

### Snapshot & Restore

Manage backup repositories and snapshots with ease.

**Repositories:**
```bash
# List all repositories
elastro snapshot repo list

# Create a filesystem repository
elastro snapshot repo create my_backup fs --setting location=/tmp/backups

# Create an S3 repository
elastro snapshot repo create my_s3_backup s3 --setting bucket=my-bucket --setting region=us-east-1
```

**Snapshots:**
```bash
# List snapshots in a repository
elastro snapshot list my_backup

# Create a snapshot (async default)
elastro snapshot create my_backup snapshot_1

# Create and wait for completion
elastro snapshot create my_backup snapshot_2 --wait --indices "logs-*,metrics-*"

# Restore a snapshot (Interactive Wizard)
elastro snapshot restore
# Launches a wizard to select repo -> snapshot -> indices -> rename pattern

# Restore specific indices from CLI
elastro snapshot restore my_backup snapshot_1 --indices "logs-*"
```

- [Getting Started](https://github.com/Fremen-Labs/elastro/blob/main/docs/getting_started.md)
- [API Reference](https://github.com/Fremen-Labs/elastro/blob/main/docs/api_reference.md)
- [CLI Usage](https://github.com/Fremen-Labs/elastro/blob/main/docs/cli_usage.md)
- [Advanced Features](https://github.com/Fremen-Labs/elastro/blob/main/docs/advanced_features.md)
- [Troubleshooting](https://github.com/Fremen-Labs/elastro/blob/main/docs/troubleshooting.md)

## Examples

Check out the [examples](https://github.com/Fremen-Labs/elastro/tree/main/examples) directory for more usage examples:

- [Client Connection](https://github.com/Fremen-Labs/elastro/blob/main/examples/client.py)
- [Index Management](https://github.com/Fremen-Labs/elastro/blob/main/examples/index_management.py)
- [Document Operations](https://github.com/Fremen-Labs/elastro/blob/main/examples/document_operations.py)
- [Search Operations](https://github.com/Fremen-Labs/elastro/blob/main/examples/search.py)
- [Datastream Management](https://github.com/Fremen-Labs/elastro/blob/main/examples/datastreams.py)

## Contributing

We welcome contributions to Elastro! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to get started, code standards, and submission processes.


## License

MIT 