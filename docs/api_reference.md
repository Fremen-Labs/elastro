# API Reference

This document provides detailed documentation for Elastro's core components and their methods.

## Table of Contents

- [ElasticsearchClient](#elasticsearchclient)
- [IndexManager](#indexmanager)
- [DocumentManager](#documentmanager)
- [IngestEngine](#ingestengine)
- [DatastreamManager](#datastreammanager)
- [Health Assessment](#health-assessment)
- [Advanced Components](#advanced-components)
  - [QueryBuilder](#querybuilder)
  - [AggregationBuilder](#aggregationbuilder)
  - [ScrollHelper](#scrollhelper)

## ElasticsearchClient

The `ElasticsearchClient` class is the primary entry point for connecting to Elasticsearch.

### Constructor

```python
client = ElasticsearchClient(
    hosts=None,  # List of Elasticsearch hostnames/IPs
    auth=None,   # Authentication details
    timeout=30,  # Connection timeout in seconds
    retry_on_timeout=True,  # Whether to retry on timeout
    max_retries=3,  # Maximum number of retries
    profile=None  # Configuration profile to use
)
```

### Methods

#### `connect()`

Establishes a connection to the Elasticsearch cluster.

```python
client.connect()
```

#### `health()`

Retrieves health information about the Elasticsearch cluster.

```python
health = client.health()
# Returns: Dict with cluster health status
```

#### `indices()`

Lists all indices in the cluster.

```python
indices = client.indices()
# Returns: List of index names
```

## IndexManager

The `IndexManager` class handles operations related to Elasticsearch indices.

### Constructor

```python
index_manager = IndexManager(client)
```

### Methods

#### `create(name, settings=None, mappings=None)`

Creates a new index with optional settings and mappings.

```python
result = index_manager.create(
    name="my-index",
    settings={
        "number_of_shards": 3,
        "number_of_replicas": 1
    },
    mappings={
        "properties": {
            "field1": {"type": "text"},
            "field2": {"type": "keyword"}
        }
    }
)
# Returns: Dict with creation result
```

#### `get(name)`

Retrieves information about an index.

```python
info = index_manager.get("my-index")
# Returns: Dict with index information
```

#### `exists(name)`

Checks if an index exists.

```python
exists = index_manager.exists("my-index")
# Returns: Boolean
```

#### `update(name, settings)`

Updates settings for an existing index.

```python
result = index_manager.update(
    "my-index",
    {"index": {"number_of_replicas": 2}}
)
# Returns: Dict with update result
```

#### `delete(name)`

Deletes an index.

```python
result = index_manager.delete("my-index")
# Returns: Dict with deletion result
```

#### `open(name)`

Opens a closed index.

```python
result = index_manager.open("my-index")
# Returns: Dict with operation result
```

#### `close(name)`

Closes an open index.

```python
result = index_manager.close("my-index")
# Returns: Dict with operation result
```

## DocumentManager

The `DocumentManager` class handles document operations.

### Constructor

```python
doc_manager = DocumentManager(client)
```

### Methods

#### `index(index, id, document)`

Indexes a document with the given ID.

```python
result = doc_manager.index(
    index="my-index",
    id="doc-1",
    document={"field1": "value1", "field2": "value2"}
)
# Returns: Dict with indexing result
```

#### `bulk_index(index, documents)`

Indexes multiple documents in a single operation.

```python
documents = [
    {"id": "doc-1", "document": {"field1": "value1"}},
    {"id": "doc-2", "document": {"field1": "value2"}}
]
result = doc_manager.bulk_index("my-index", documents)
# Returns: Dict with bulk indexing result
```

#### `get(index, id)`

Retrieves a document by ID.

```python
document = doc_manager.get("my-index", "doc-1")
# Returns: Dict with document
```

## IngestEngine

The `IngestEngine` class handles client-side data streaming, pre-flight validation, type coercion, and bulk importing.

### Constructor

```python
from elastro import IngestEngine

ingest_engine = IngestEngine(client)
```

### Methods

#### `ingest(source, index, ...)`

Ingests data from a file source into an Elasticsearch index.

```python
result = ingest_engine.ingest(
    source="data.csv",
    index="my-index",
    format="csv",
    batch_size=2000,
    dlq_path="failed.ndjson",
    progress_callback=lambda read, indexed, failed: print(f"{indexed} indexed")
)
# Returns: IngestResult with operation statistics (total_read, total_indexed, total_failed)
```

## Health Assessment

Health assessment components live in `elastro.health`. See [Health Commands](./health_commands.md) for CLI usage.

### HealthAssessor

Orchestrates collectors and rules to produce an `AssessmentReport`.

```python
from elastro import ElasticsearchClient
from elastro.health.assessor import HealthAssessor

client = ElasticsearchClient()
client.connect()
report = HealthAssessor(client).run(
    enable_history=True,  # index to elastro-health-assessments
)
print(report.overall_score, report.overall_status)
```

### RemediationExecutor

Executes catalog remediations with dry-run, confirmation, rollback snapshots, and audit hooks.

```python
from elastro.health.remediation.executor import RemediationExecutor

executor = RemediationExecutor(client, dry_run=False, interactive=False)
result = executor.execute_action("reduce_replicas", "logs-2024")
print(result.rollback_id)  # set when settings were snapshotted

# Restore prior settings
executor.rollback(result.rollback_id)
```

### HealthAuditLogger

Emits assess/fix/rollback events to logs and optionally to the `elastro-health-audit` index.

```python
from elastro.health.audit import HealthAuditLogger

audit = HealthAuditLogger(client, profile="default", host="http://localhost:9200")
audit.log_assess(report)
```

---

## Advanced Components

### QueryBuilder

The `QueryBuilder` class helps to construct complex Elasticsearch queries.

```python
from elastro.advanced import QueryBuilder

// ... existing code ...
```

### AggregationBuilder

The `AggregationBuilder` class helps to construct Elasticsearch aggregations.

```python
from elastro.advanced import AggregationBuilder

// ... existing code ...
```

### ScrollHelper

The `ScrollHelper` class helps with scrolling through large result sets.

```python
from elastro.advanced import ScrollHelper
from elastro import ElasticsearchClient

// ... existing code ...
```