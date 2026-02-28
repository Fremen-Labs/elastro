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
