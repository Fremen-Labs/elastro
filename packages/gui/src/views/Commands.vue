<script setup lang="ts">
</script>

<template>
  <div class="docs animate-fade-in">
    <header class="page-header">
      <h1>CLI Commands Reference</h1>
      <p>A comprehensive guide to the Elastro CLI capabilities and subcommands.</p>
    </header>

    <div class="card doc-content">
      <div class="doc-section">
        <h2>1. <code>config</code></h2>
        <p><strong>Purpose</strong>: Manage local configuration and connection profiles.</p>
        <p><strong>Why it's important</strong>: Centralizing connection strings, credentials, and API keys ensures you don't accidentally leak secrets or push them to version control. It also enables rapid context-switching between dev, staging, and production environments.</p>
        <ul>
          <li><strong><code>profile</code></strong>: Switch or define which configuration profile is actively used by Elastro.</li>
          <li><strong><code>set</code></strong>: Set individual configuration values securely within the active profile.</li>
        </ul>
      </div>

      <hr class="doc-divider" />

      <div class="doc-section">
        <h2>2. <code>gui</code></h2>
        <p><strong>Purpose</strong>: Launch the Elastro Local Web GUI.</p>
        <p><strong>Why it's important</strong>: Sometimes the CLI isn't enough to visualize complex index metrics or health statuses. The fully autonomous local GUI acts as a single pane of glass, allowing you to quickly spot cluster degradation (yellow/red indices) and manage your instances without deploying heavy Kibana stacks.</p>
        <ul>
          <li><strong><code>elastro gui</code></strong>: Starts a secure, detached background server and immediately opens the web dashboard in your browser with a unique, one-time authentication token.</li>
        </ul>
      </div>

      <hr class="doc-divider" />

      <div class="doc-section">
        <h2>3. <code>index</code></h2>
        <p><strong>Purpose</strong>: Manage Elasticsearch indices.</p>
        <p><strong>Why it's important</strong>: Indices are the foundational storage mechanism of Elasticsearch. Proper index management ensures that your data is correctly sharded, optimally routed, and easily purged.</p>
        <ul>
          <li><strong><code>wizard</code></strong>: Interactive wizard for creating indices using "Certified Engineer" optimized recipes (highly recommended).</li>
          <li><strong><code>list</code></strong> / <strong><code>find</code></strong>: Filter and list indices, displaying vital statistics like size, document counts, and health status.</li>
          <li><strong><code>create</code></strong> / <strong><code>delete</code></strong>: Safely deploy mapped index schemas or purge indices entirely.</li>
          <li><strong><code>get</code></strong> / <strong><code>exists</code></strong>: Query the exact structure, mappings, and existence of a target index.</li>
          <li><strong><code>update</code></strong>: Inject dynamic settings updates into live indices.</li>
          <li><strong><code>close</code></strong> / <strong><code>open</code></strong>: Freeze indices to save cluster memory footprint, and thaw them later for searching.</li>
        </ul>
      </div>

      <hr class="doc-divider" />

      <div class="doc-section">
        <h2>4. <code>doc</code></h2>
        <p><strong>Purpose</strong>: Manage Elasticsearch documents.</p>
        <p><strong>Why it's important</strong>: While indexing logs via beats is common, debugging mapping errors or orchestrating CRUD operations manually is a critical administrative function. The <code>doc</code> commands let you easily ingest, query, and mutate specific records directly from the terminal.</p>
        <ul>
          <li><strong><code>bulk</code></strong>: Perform high-throughput bulk insertion of documents from NDJSON payloads.</li>
          <li><strong><code>search</code></strong>: Execute direct search queries against your indexes for ad-hoc debugging.</li>
          <li><strong><code>index</code></strong>: Insert a new specific document or overwrite an existing one.</li>
          <li><strong><code>get</code></strong>: Retrieve a document by its ID to examine its exact structured payload.</li>
          <li><strong><code>update</code></strong>: Perform partial updates to an existing document without full replacement.</li>
          <li><strong><code>delete</code></strong>: Remove an individual document.</li>
        </ul>
      </div>

      <hr class="doc-divider" />

      <div class="doc-section">
        <h2>5. <code>datastream</code></h2>
        <p><strong>Purpose</strong>: Manage Elasticsearch datastreams.</p>
        <p><strong>Why it's important</strong>: Data streams are the modern, scalable approach to handling time-series data (like logs and metrics). Elastro abstracts the complexities of backing indices so you can manage the continuous stream elegantly.</p>
        <ul>
          <li><strong><code>create</code></strong>: Establish a new datastream (requires a matching index template).</li>
          <li><strong><code>list</code></strong> / <strong><code>get</code></strong> / <strong><code>exists</code></strong>: Discover and inspect streaming channels.</li>
          <li><strong><code>stats</code></strong>: Retrieve detailed volumetric and performance statistics about your streams.</li>
          <li><strong><code>delete</code></strong>: Teardown deprecated datastreams.</li>
        </ul>
      </div>

      <hr class="doc-divider" />

      <div class="doc-section">
        <h2>6. <code>template</code></h2>
        <p><strong>Purpose</strong>: Manage index and component templates.</p>
        <p><strong>Why it's important</strong>: Templates guarantee that newly generated rolling indices (or datastreams) automatically inherit the correct shards, replicas, mappings, and lifecycles dynamically, avoiding manual intervention at runtime.</p>
        <ul>
          <li><strong><code>wizard</code></strong>: An interactive wizard that makes assembling advanced index schemas from reusable component templates easy.</li>
          <li><strong><code>create</code></strong>: Apply a template JSON manifest to the cluster.</li>
          <li><strong><code>list</code></strong> / <strong><code>get</code></strong>: Inspect currently active templates.</li>
          <li><strong><code>delete</code></strong>: Purge outdated templates.</li>
        </ul>
      </div>

      <hr class="doc-divider" />

      <div class="doc-section">
        <h2>7. <code>ilm</code></h2>
        <p><strong>Purpose</strong>: Manage Index Lifecycle Management (ILM) policies.</p>
        <p><strong>Why it's important</strong>: Managing the cost of compute versus storage requires aging out data. ILM policies automate the transition of indices through Hot, Warm, Cold, and Delete phases automatically, saving enormous amounts of hardware resources.</p>
        <ul>
          <li><strong><code>wizard</code></strong>: Interactively define retention durations, rollover sizes, and phase transitions to build robust lifecycle policies without writing complex JSON.</li>
          <li><strong><code>create</code></strong>: Upload a customized JSON ILM policy.</li>
          <li><strong><code>list</code></strong> / <strong><code>get</code></strong>: Inspect the policies currently governing your cluster data.</li>
          <li><strong><code>delete</code></strong>: Remove an ILM policy.</li>
        </ul>
      </div>

      <hr class="doc-divider" />

      <div class="doc-section">
        <h2>8. <code>snapshot</code></h2>
        <p><strong>Purpose</strong>: Manage Snapshots and Repositories.</p>
        <p><strong>Why it's important</strong>: Hardware failures, ransomware, or unexpected deletions happen. Standardized cluster snapshotting is the only reliable path to disaster recovery (DR).</p>
        <ul>
          <li><strong><code>repo</code></strong>: Manage the snapshot storage backends (e.g., S3, Azure Blob, or local FS).</li>
          <li><strong><code>create</code></strong>: Trigger a manual snapshot of the cluster or specific indices.</li>
          <li><strong><code>list</code></strong>: View all historical snapshots held in a repository.</li>
          <li><strong><code>restore</code></strong>: Recover your cluster state and data instantly from a previously saved snapshot.</li>
          <li><strong><code>delete</code></strong>: Prune old snapshots to reclaim storage space.</li>
        </ul>
      </div>

      <hr class="doc-divider" />

      <div class="doc-section">
        <h2>9. <code>utils</code></h2>
        <p><strong>Purpose</strong>: Miscellaneous utility commands.</p>
        <p><strong>Why it's important</strong>: Fast access to high-level cluster metrics and organizational operations for general system administration.</p>
        <ul>
          <li><strong><code>health</code></strong>: Get a quick snapshot of the cluster's pulse (Green, Yellow, Red) and node availability.</li>
          <li><strong><code>aliases</code></strong>: Inspect index aliases, showing how applications transparently route to underlying indices.</li>
          <li><strong><code>templates</code></strong>: Manage legacy index templates (if supporting older Elasticsearch 7.x clusters).</li>
        </ul>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-header {
  margin-bottom: 2rem;
}

.page-header h1 {
  font-size: 2rem;
  font-weight: 700;
  margin-bottom: 0.25rem;
}

.page-header p {
  color: hsl(var(--muted-foreground));
  font-size: 1rem;
}

.doc-content {
  padding: 2.5rem;
  max-width: 900px;
}

.doc-section {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.doc-section h2 {
  font-size: 1.5rem;
  font-weight: 600;
  color: hsl(var(--foreground));
  margin-bottom: 0.25rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.doc-section code {
  background: hsl(var(--muted) / 0.5);
  padding: 0.2rem 0.4rem;
  border-radius: 4px;
  font-family: monospace;
  font-size: 0.9em;
  color: hsl(var(--primary));
}

.doc-section p {
  line-height: 1.6;
  color: hsl(var(--muted-foreground));
}

.doc-section strong {
  color: hsl(var(--foreground));
  font-weight: 600;
}

.doc-section ul {
  list-style: none;
  padding-left: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.doc-section li {
  position: relative;
  line-height: 1.5;
  color: hsl(var(--muted-foreground));
}

.doc-section li::before {
  content: "•";
  color: hsl(var(--primary));
  font-weight: bold;
  position: absolute;
  left: -1rem;
}

.doc-divider {
  border: 0;
  border-bottom: 1px solid hsl(var(--border));
  margin: 2.5rem 0;
  opacity: 0.5;
}
</style>
