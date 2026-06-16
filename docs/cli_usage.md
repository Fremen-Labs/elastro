# Elastro CLI Usage Guide

The Elastro package provides a powerful command-line interface (CLI) for managing Elasticsearch indices, documents, and datastreams. This guide explains how to use the CLI effectively.

## Installation

The CLI is automatically installed when you install the elastro package:

```bash
pip install elastro
```

## Getting Started

### 1. Initialize Configuration

Before using the CLI, you'll need to configure your Elasticsearch connection details.

```bash
elastro config init
```

This creates a default configuration file at `~/.elastic/config.yaml`.

### 2. Configure Authentication

Secure your connection by setting up authentication (e.g., Basic Auth):

```bash
elastro config set elasticsearch.auth '{"type": "basic", "username": "elastic", "password": "changeme"}'
elastro config set elasticsearch.hosts '["http://localhost:9200"]'
```

### 3. Verify Connection

Check if `elastro` can connect to your cluster:

```bash
elastro utils health
```

## Global Options

The following options can be used with any command:

- `--config, -c`: Path to configuration file
- `--profile, -p`: Configuration profile to use (default: "default")
- `--host, -h`: Elasticsearch host(s) (can be specified multiple times)
- `--output, -o`: Output format for results (json, yaml, table)
- `--verbose, -v`: Enable verbose output
- `--version`: Show version and exit
- `--help`: Show styled help message via rich-click

## Search Documents

The `doc search` command is the powerhouse of the CLI, supporting simple text searches, file-based queries, and complex boolean logic via flags.

```bash
elastro doc search INDEX_NAME [QUERY] [OPTIONS]
```

### Basic Search

```bash
# Simple query string search
elastro doc search my_index "error"

# Output as a formatted table
elastro --output table doc search my_index "error"
```

### Advanced Search (Top 10 Query Types)

Build complex boolean queries directly using these flags. All flags can be combined (AND logic by default).

| Flag | Description | Example |
|---|---|---|
| `--match` | Standard match query (analyzed) | `--match name=Laptop` |
| `--match-phrase` | Phrase match query | `--match-phrase title="Star Wars"` |
| `--term` | Exact term match (keyword) | `--term status=active` |
| `--terms` | Match ANY value in list | `--terms tags=env,prod` |
| `--range` | Numeric/Date range | `--range price=gt:10,lte:50` |
| `--prefix` | Prefix match | `--prefix sku=XY-` |
| `--wildcard` | Wildcard pattern match | `--wildcard user=jo*` |
| `--exists` | Field existence check | `--exists error_details` |
| `--ids` | Retrieve by Document ID | `--ids 101,102` |
| `--fuzzy` | Fuzzy matching | `--fuzzy name=elstastic` |
| `--exclude-term` | Must NOT match term | `--exclude-term status=deleted` |
| `--exclude-match` | Must NOT match text | `--exclude-match level=debug` |

### Search Examples

**1. Product Search**
Find explicit "Alienware" laptops over $1000, excluding tablets.

```bash
elastro --output table doc search products \
  --term brand.keyword=Alienware \
  --match name=Laptop \
  --range price=gt:1000 \
  --exclude-term category.keyword=Tablet
```

**2. Log Analysis**
Find logs with "error" status from a specific wildcard source, checking if "trace_id" exists.

```bash
elastro doc search logs-2024 \
  --term status=error \
  --wildcard source=service-a* \
  --exists trace_id
```

**3. Complex Query from File**
For deeply nested queries or aggregations, use a JSON file.

```bash
elastro doc search my_index --file query.json
```

## Index Management

### Create Index

```bash
elastro index create INDEX_NAME [OPTIONS]
```

Options:
- `--shards`: Number of shards (default: 1)
- `--replicas`: Number of replicas (default: 1)
- `--mapping`: Path to mapping file (JSON format)
- `--settings`: Path to settings file (JSON format)

### Get Index

```bash
elastro index get INDEX_NAME
```

### Check if Index Exists

```bash
elastro index exists INDEX_NAME
```

### Update Index

```bash
elastro index update INDEX_NAME --settings SETTINGS_FILE
```

### Delete Index

```bash
elastro index delete INDEX_NAME [--force]
```

The `--force` option skips the confirmation prompt.

### Open Index

```bash
elastro index open INDEX_NAME
```

### Close Index

```bash
elastro index close INDEX_NAME
```

## Document Management (General)

### Index a Document

```bash
elastro doc index INDEX_NAME [OPTIONS]
```

Options:
- `--id`: Document ID (optional)
- `--file`: Path to document file (JSON format)

If no file is provided, the document is read from stdin.

```bash
echo '{"name": "foo"}' | elastro doc index my_index
```

### Bulk Index Documents

```bash
elastro doc bulk INDEX_NAME --file DOCUMENTS_FILE
```

The file should contain a JSON array of documents.

### Get Document

```bash
elastro doc get INDEX_NAME DOCUMENT_ID
```

### Update Document

```bash
elastro doc update INDEX_NAME DOCUMENT_ID --file DOCUMENT_FILE [--partial]
```

The `--partial` flag enables partial document updates.

### Delete Document

```bash
elastro doc delete INDEX_NAME DOCUMENT_ID
```

### Bulk Delete Documents

```bash
elastro doc bulk-delete INDEX_NAME --file IDS_FILE
```

The file should contain a JSON array of document IDs.

## Ingest Engine

The `ingest` command group provides client-side data preparation, processing, and multi-format import capabilities.

### Import Data

Stream data directly into Elasticsearch from various file formats (CSV, NDJSON, JSON, SQL):

```bash
elastro ingest import data.csv --index customers --format csv
```

**SQL Live Database Import:**
```bash
elastro ingest import --sql "SELECT * FROM users" --dsn postgresql://user:pass@localhost/db --index users
```

### Profile Data Quality

Analyze a dataset before importing it to identify field types, null rates, and PII (Personally Identifiable Information) risk:

```bash
elastro ingest profile data.csv --sample-size 1000
```

### Validate Documents

Perform a pre-flight schema validation against an active index's mapping to catch coercion errors before sending bulk requests:

```bash
elastro ingest validate data.ndjson --index my-index --strict
```

### Auto-Map Schema Inference

Infer optimal Elasticsearch index mappings automatically by sampling a local file (supports recursive nested object mapping):

```bash
elastro ingest auto-map data.json --sample-size 500
```

### Smart Grok Builder

Quickly construct and test Grok patterns interactively. Use `--sample` to supply a target log line:

```bash
elastro ingest grok-builder --sample "10.0.0.1 - - [12/May/2026:07:03:12] \"GET /api/v1/users HTTP/1.1\" 200 1234"
```

## Datastream Management

### Create Datastream

```bash
elastro datastream create DATASTREAM_NAME [--index-pattern INDEX_PATTERN]
```

### List Datastreams

```bash
elastro datastream list [--pattern PATTERN]
```

### Get Datastream

```bash
elastro datastream get DATASTREAM_NAME
```

### Delete Datastream

```bash
elastro datastream delete DATASTREAM_NAME
```

### Rollover Datastream

```bash
elastro datastream rollover DATASTREAM_NAME [--conditions CONDITIONS_FILE]
```

## Health Assessment

The `health` command group (v1.4+) provides scored assessments, findings, remediation, rollback, and optional audit/history indexing. See [Health Commands](./health_commands.md) for the complete reference.

### Run an assessment

```bash
# Table output (recommended)
elastro health assess -o table

# Disk indicator only
elastro health assess --feature disk -o json

# Preview fixes without applying
elastro health assess --fix --dry-run -o table

# Persist assessment to Elasticsearch history index
elastro health assess --history -o table
```

### Score and history

```bash
elastro health score
elastro health score --history --last 5 -o table
```

### Rollback a remediation

When a fix captures settings before applying, the result includes a `rollback_id`:

```bash
elastro health rollback --id rb-abc123 --dry-run
elastro health rollback --id rb-abc123
```

Snapshots are stored under `~/.elastic/health-rollbacks/`.

### Other health commands

```bash
elastro health status [--level cluster|indices|shards] [--wait green]
elastro health report
elastro health nodes --metric jvm,fs --hotspots
elastro health shards --analyze
elastro health hotspots --variance 25
```

### Health configuration

```bash
elastro config get health.assessment.history_index
elastro config get health.assessment.audit_index
```

Default indices: `elastro-health-assessments` (history) and `elastro-health-audit` (audit events).

---

## Utility Commands

### Cluster Health

> **Deprecation:** Prefer `elastro health status`. `utils health` remains for backward compatibility.

```bash
elastro health status [--level LEVEL] [--wait green|yellow|red]
elastro utils health [--level LEVEL] [--wait-for-status STATUS]
```

### Index Templates

```bash
elastro utils templates list [--pattern PATTERN]
elastro utils templates get TEMPLATE_NAME
```

### Aliases

```bash
elastro utils aliases list [--index INDEX]
```

## Configuration (Advanced)

### List Configuration

To view your current configuration:

```bash
elastro config list
```

### Get/Set Configuration Values

```bash
elastro config get elasticsearch.hosts
elastro config set elasticsearch.timeout 60
```

### Using Multiple Profiles

```bash
# Initialize production profile
elastro config init --profile production

# Set production configuration
elastro config set elasticsearch.hosts '["https://prod-es:9200"]' --profile production

# Use production profile for operations
elastro --profile production index list
```

## Troubleshooting

### Connection Issues

If you're having trouble connecting to Elasticsearch, verify your configuration:

```bash
elastro config list
```

Ensure that the hosts, username, and password are correct. Use `elastro utils health` to verify basic connectivity.

### Authenticated Environment

If your cluster requires authentication, ensure you have set the credentials correctly using `config set elasticsearch.auth ...`. 

### Permission Errors

Permission errors often occur when your user doesn't have the required permissions in Elasticsearch. Check your user's roles and permissions in Elasticsearch.

### Data Format Errors

When indexing or updating documents, ensure that your JSON is valid. You can validate your JSON with:

```bash
cat document.json | jq
```

## Additional Resources

- [Health Commands](./health_commands.md) — assessment, remediation, rollback, audit
- [API Reference](./api_reference.md) — Python API documentation
