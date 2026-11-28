# Elastro CLI Commands Reference

The Elastro CLI provides a robust feature set for managing your Elasticsearch cluster operations safely and efficiently. This guide details each primary command group, its associated subcommands, what they do, and why they are important for your workflow.

---

## 1. `config`
**Purpose**: Manage local configuration and connection profiles.
**Why it's important**: Centralizing connection strings, credentials, and API keys ensures you don't accidentally leak secrets or push them to version control. It also enables rapid context-switching between dev, staging, and production environments.

- **`profile`**: Switch or define which configuration profile is actively used by Elastro.
- **`set`**: Set individual configuration values securely within the active profile.

---

## 2. `gui`
**Purpose**: Launch the Elastro Local Web GUI.
**Why it's important**: Sometimes the CLI isn't enough to visualize complex index metrics or health statuses. The fully autonomous local GUI acts as a single pane of glass, allowing you to quickly spot cluster degradation (yellow/red indices) and manage your instances without deploying heavy Kibana stacks.

- **`elastro gui`**: Starts a secure, detached background server and immediately opens the web dashboard in your browser with a unique, one-time authentication token.

---

## 3. `index`
**Purpose**: Manage Elasticsearch indices.
**Why it's important**: Indices are the foundational storage mechanism of Elasticsearch. Proper index management ensures that your data is correctly sharded, optimally routed, and easily purged.

- **`wizard`**: Interactive wizard for creating indices using "Certified Engineer" optimized recipes (highly recommended).
- **`list`** / **`find`**: Filter and list indices, displaying vital statistics like size, document counts, and health status.
- **`create`** / **`delete`**: Safely deploy mapped index schemas or purge indices entirely.
- **`get`** / **`exists`**: Query the exact structure, mappings, and existence of a target index.
- **`update`**: Inject dynamic settings updates into live indices.
- **`close`** / **`open`**: Freeze indices to save cluster memory footprint, and thaw them later for searching.

---

## 4. `doc`
**Purpose**: Manage Elasticsearch documents.
**Why it's important**: While indexing logs via beats is common, debugging mapping errors or orchestrating CRUD operations manually is a critical administrative function. The `doc` commands let you easily ingest, query, and mutate specific records directly from the terminal.

- **`bulk`**: Perform high-throughput bulk insertion of documents from NDJSON payloads.
- **`search`**: Execute direct search queries against your indexes for ad-hoc debugging.
- **`index`**: Insert a new specific document or overwrite an existing one.
- **`get`**: Retrieve a document by its ID to examine its exact structured payload.
- **`update`**: Perform partial updates to an existing document without full replacement.
- **`delete`**: Remove an individual document.

---

## 5. `datastream`
**Purpose**: Manage Elasticsearch datastreams.
**Why it's important**: Data streams are the modern, scalable approach to handling time-series data (like logs and metrics). Elastro abstracts the complexities of backing indices so you can manage the continuous stream elegantly.

- **`create`**: Establish a new datastream (requires a matching index template).
- **`list`** / **`get`** / **`exists`**: Discover and inspect streaming channels.
- **`stats`**: Retrieve detailed volumetric and performance statistics about your streams.
- **`delete`**: Teardown deprecated datastreams.

---

## 6. `template`
**Purpose**: Manage index and component templates.
**Why it's important**: Templates guarantee that newly generated rolling indices (or datastreams) automatically inherit the correct shards, replicas, mappings, and lifecycles dynamically, avoiding manual intervention at runtime.

- **`wizard`**: An interactive wizard that makes assembling advanced index schemas from reusable component templates easy.
- **`create`**: Apply a template JSON manifest to the cluster.
- **`list`** / **`get`**: Inspect currently active templates.
- **`delete`**: Purge outdated templates.

---

## 7. `ilm`
**Purpose**: Manage Index Lifecycle Management (ILM) policies.
**Why it's important**: Managing the cost of compute versus storage requires aging out data. ILM policies automate the transition of indices through Hot, Warm, Cold, and Delete phases automatically, saving enormous amounts of hardware resources.

- **`wizard`**: Interactively define retention durations, rollover sizes, and phase transitions to build robust lifecycle policies without writing complex JSON.
- **`create`**: Upload a customized JSON ILM policy.
- **`list`** / **`get`**: Inspect the policies currently governing your cluster data.
- **`delete`**: Remove an ILM policy.
- **`start`** / **`stop`**: Enable or disable ILM on the cluster (`--yes` or `--dry-run` required for mutations).

---

## 8. `snapshot`
**Purpose**: Manage Snapshots and Repositories.
**Why it's important**: Hardware failures, ransomware, or unexpected deletions happen. Standardized cluster snapshotting is the only reliable path to disaster recovery (DR). 

- **`repo`**: Manage the snapshot storage backends (e.g., S3, Azure Blob, or local FS).
- **`create`**: Trigger a manual snapshot of the cluster or specific indices.
- **`list`**: View all historical snapshots held in a repository.
- **`restore`**: Recover your cluster state and data instantly from a previously saved snapshot.
- **`delete`**: Prune old snapshots to reclaim storage space.

---

## 9. `utils`
**Purpose**: Miscellaneous utility commands.
**Why it's important**: Fast access to high-level cluster metrics and organizational operations for general system administration.

- **`health`**: Get a quick snapshot of the cluster's pulse (Green, Yellow, Red) and node availability.
- **`aliases`**: Inspect index aliases, showing how applications transparently route to underlying indices.
- **`templates`**: Manage legacy index templates (if supporting older Elasticsearch 7.x clusters).

---

## 10. `health`
**Purpose**: Cluster health assessment, scoring, diagnostics, and safe remediation.
**Why it's important**: Elasticsearch exposes rich health signals via `_health_report`, node stats, and shard allocation, but they are scattered across APIs. The `health` group combines these into a single scored assessment with actionable findings, optional remediation, rollback, and audit trails—without requiring Kibana or Elastic Cloud.

See [Health Commands](./health_commands.md) for full option reference.

- **`assess`**: Run a full health assessment (score 0–100, findings table). Supports `--fix`, `--dry-run`, and `--history` to index reports to `elastro-health-assessments`.
- **`score`**: Print the current score quickly, or `--history --last N` to read past assessments from the history index.
- **`rollback`**: Restore index settings from a saved remediation snapshot (`--id rb-...`, optional `--dry-run`).
- **`status`**: Cluster/indices/shard health check with optional `--wait` (replaces `utils health`).
- **`report`**: Formatted `_health_report` passthrough.
- **`nodes`**: Per-node JVM, disk, and breaker metrics; `--hotspots` for variance detection.
- **`shards`**: Shard allocation view; `--analyze` for oversharding/undersharding detection.
- **`hotspots`**: Shortcut for node hotspot variance analysis.
- **`lint`**: Best-practice linter for index settings, mapping field counts, and shard layout (`--category settings|mappings|shards`).

---

## 11. `coverage`
**Purpose**: Elasticsearch-side APM and Beats coverage — ILM/index templates, data-arrival checks, and a combined readiness report.
**Why it's important**: After instrumenting applications, you need a fast, automatable answer to “is data showing up, and is the cluster ready to keep it?” Coverage stays on the Elasticsearch/Kibana side (no SSH, Ansible, or agent deploy).

See [Coverage & Readiness](./coverage.md) for the full command and Python API reference.

- **`templates list` / `templates apply`**: Ship and apply opinionated ILM + index templates (`apm-traces`, `apm-metrics`, `filebeat-logs`, `metricbeat-metrics`). `--dry-run` prints planned bodies; apply requires `--yes` (or an interactive confirm). On a shared cluster, override with `--policy-name`, `--template-name`, and `--index-pattern elastro-scratch-*` so production `traces-apm*` is not overwritten.
- **`check`**: Validate document counts, freshness, stream presence, and basic field presence (`--service`, `--pattern`, or `--all`). `--all` is a full APM+Beats AND-gate. `--skip-absent` skips patterns with no matching streams. Failed checks exit `2` for CI.
- **`report`**: Combined readiness report (template apply status + coverage checks + APM/Beats health findings). Supports `--skip-absent`.
- **`fleet status` / `fleet agents`**: Optional read-only Fleet helpers (Kibana API, or `ELASTRO_FLEET_*` env). JSON/YAML when disabled: `{enabled: false}` exit 0. The API key is never logged.

Global `-o json|yaml|table` belongs on the root group: `elastro -o json coverage check --all`.

---

## 12. `ingest`
**Purpose**: Client-side data preparation, formatting, and AI-driven pipeline operations.
**Why it's important**: Elasticsearch ingest pipelines are powerful but run server-side. The `ingest` commands let you process, sanitize, validate, and format data (like CSV, SQL, Parquet, or NDJSON) locally *before* it reaches your cluster, and provides smart AI tools to rapidly author complex ingest logic.

- **`import`**: Multi-format streaming data import (CSV, NDJSON, JSON array, SQL). Automatically parses inputs without loading entire files into memory. SQL (`--sql` / `--dsn`) requires `pip install "elastro-client[ingest-sql]"`.
- **`profile`**: Analyze a local data source to generate a pre-ingest data quality report, identifying PII risk, uniqueness, and null rates.
- **`validate`**: Dry-run document validation against an Elasticsearch index mapping with strict type coercion enforcement.
- **`auto-map`**: Sample a dataset to infer optimal Elasticsearch field mappings (including nested objects) automatically.
- **`grok-builder`**: A dual-mode (Deterministic and AI-Assisted) builder to rapidly construct and test Grok patterns against the ES Simulate API.
- **`pipelines`**: List and inspect currently active server-side Elasticsearch ingest pipelines.
- **`simulate`**: Test an existing pipeline against a sample document or file to verify its transformations.

---

## 13. `cluster`
**Purpose**: Cluster-level allocation and routing.
**Why it's important**: Unassigned shards and routing blocks are the usual reasons a cluster sits yellow/red. These commands explain allocation and toggle routing without raw `_cluster` JSON.

- **`allocation`**: Explain unassigned shards (empty success when none are unassigned).
- **`settings`**: Show or update allocation routing (`--enable-routing` requires `--yes`).

---

## 14. `security`
**Purpose**: Inspect Elasticsearch native users and roles.
**Why it's important**: Fast RBAC inventory without opening Kibana.

- **`users`**: List native users (optional username filter).
- **`roles`**: List roles (optional name filter).

---

## 15. `tasks`
**Purpose**: List and cancel cluster tasks.
**Why it's important**: Long reindexes and bulk jobs show up here; cancel requires `--yes`.

- **`list`**: List tasks (`--action` filter).
- **`cancel`**: Cancel a task by id (confirm gate).

---

## 16. `script`
**Purpose**: Stored script CRUD and execute.
**Why it's important**: Shared Painless/Mustache scripts live in the cluster script store.

- **`list`** / **`get`** / **`create`** / **`delete`**: Manage stored scripts (`delete` requires `--yes`).
- **`execute`**: Run a stored or inline script.

---

## 17. `painless`
**Purpose**: Scaffold and test Painless locally.
**Why it's important**: `scaffold` is TTY-only (exit 2 without a TTY). `test` executes against mock or cluster context.

- **`scaffold`**: Interactive boilerplate (non-TTY exits 2, no ES).
- **`test`**: Execute a script file.

---

## 18. `esql`
**Purpose**: Run ES|QL and build queries.
**Why it's important**: Ad-hoc analytics without writing Query DSL.

- **`query`**: Run an ES|QL string against the cluster.
- **`build`**: Fluent builder (`-s`, `-w`, `--stats`, `--by`, `--limit`).

---

## 19. `daemon`
**Purpose**: Optional local fast-path process for `doc search`.
**Why it's important**: Repeated `elastro doc search` from scripts can skip full CLI startup when the daemon is up.

- **`start`** / **`status`**: Start or check the local XML-RPC helper.

---

## 20. `memory` / `tools` / `telemetry`
**Purpose**: Agent memory, tool registry, and telemetry ingest helpers.
**Why it's important**: Optional agent features. Missing indices return empty results and exit 0 (no 404 stack traces).

- **`memory search` / `ingest` / `prune` / `wake`**: Memory index helpers (`prune` has `--dry-run` / `--yes`).
- **`tools search` / `register`**: Tool catalog.
- **`telemetry ingest`**: Ingest telemetry payloads.

---

## 21. `ml` / `rag`
**Purpose**: Anomaly-detection job init and repo RAG ingest.
**Why it's important**: Optional ML/RAG workflows. `ml init-job` is TTY-only.

- **`ml init-job`**: Interactive ML job scaffold.
- **`rag ingest-repo` / `update-file`**: Index a repo or file for RAG.
