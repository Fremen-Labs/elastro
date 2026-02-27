<script setup lang="ts">
</script>

<template>
  <div class="docs-wrapper animate-fade-in relative z-10 w-full h-full">
    <!-- Background Glow Effects -->
    <div class="bg-glow bg-glow-primary"></div>
    <div class="bg-glow bg-glow-accent"></div>
    
    <header class="page-header relative z-20">
      <div class="header-inner">
        <h1>Documentation</h1>
        <p>A comprehensive guide to the Elastro CLI capabilities and subcommands.</p>
      </div>
    </header>

    <div class="doc-grid relative z-20">
      
      <!-- config -->
      <section class="feature-card group cursor-pointer">
        <div class="card-glow"></div>
        <div class="card-content">
          <h2><code>config</code></h2>
          <p><strong>Purpose</strong>: Manage local configuration and connection profiles.</p>
          <p><strong>Why it's important</strong>: Centralizing connection strings, credentials, and API keys ensures you don't accidentally leak secrets or push them to version control.</p>
          <ul>
            <li><strong><code>profile</code></strong>: Switch or define which configuration profile is actively used by Elastro.</li>
            <li><strong><code>set</code></strong>: Set individual configuration values securely within the active profile.</li>
          </ul>
        </div>
      </section>

      <!-- gui -->
      <section class="feature-card group cursor-pointer">
        <div class="card-glow"></div>
        <div class="card-content">
          <h2><code>gui</code></h2>
          <p><strong>Purpose</strong>: Launch the Elastro Local Web GUI.</p>
          <p><strong>Why it's important</strong>: The fully autonomous local GUI acts as a single pane of glass, allowing you to quickly spot cluster degradation (yellow/red indices) and manage your instances without deploying heavy Kibana stacks.</p>
          <ul>
            <li><strong><code>elastro gui</code></strong>: Starts a secure, detached background server and immediately opens the web dashboard in your browser.</li>
          </ul>
        </div>
      </section>

      <!-- index -->
      <section class="feature-card group cursor-pointer">
        <div class="card-glow"></div>
        <div class="card-content">
          <h2><code>index</code></h2>
          <p><strong>Purpose</strong>: Manage Elasticsearch indices.</p>
          <p><strong>Why it's important</strong>: Proper index management ensures that your data is correctly sharded, optimally routed, and easily purged.</p>
          <ul>
            <li><strong><code>wizard</code></strong>: Interactive wizard for creating indices using "Certified Engineer" optimized recipes.</li>
            <li><strong><code>list</code></strong> / <strong><code>find</code></strong>: Filter and list indices, displaying vital statistics.</li>
            <li><strong><code>create</code></strong> / <strong><code>delete</code></strong>: Safely deploy mapped index schemas or purge indices.</li>
            <li><strong><code>get</code></strong> / <strong><code>exists</code></strong>: Query structure and existence of an index.</li>
            <li><strong><code>update</code></strong>: Inject dynamic settings updates into live indices.</li>
            <li><strong><code>close</code></strong> / <strong><code>open</code></strong>: Freeze/thaw indices.</li>
          </ul>
        </div>
      </section>

      <!-- doc -->
      <section class="feature-card group cursor-pointer">
        <div class="card-glow"></div>
        <div class="card-content">
          <h2><code>doc</code></h2>
          <p><strong>Purpose</strong>: Manage Elasticsearch documents.</p>
          <p><strong>Why it's important</strong>: The <code>doc</code> commands let you easily ingest, query, and mutate specific records directly from the terminal for ad-hoc debugging.</p>
          <ul>
            <li><strong><code>bulk</code></strong>: Perform high-throughput bulk insertion of documents.</li>
            <li><strong><code>search</code></strong>: Execute direct search queries against your indexes.</li>
            <li><strong><code>index</code></strong>: Insert a new specific document or overwrite an existing one.</li>
            <li><strong><code>get</code></strong>: Retrieve a document by its ID.</li>
            <li><strong><code>update</code></strong>: Perform partial updates.</li>
            <li><strong><code>delete</code></strong>: Remove an individual document.</li>
          </ul>
        </div>
      </section>

      <!-- datastream -->
      <section class="feature-card group cursor-pointer">
        <div class="card-glow"></div>
        <div class="card-content">
          <h2><code>datastream</code></h2>
          <p><strong>Purpose</strong>: Manage Elasticsearch datastreams.</p>
          <p><strong>Why it's important</strong>: Data streams are the modern, scalable approach to handling time-series data. Elastro abstracts the complexities of backing indices.</p>
          <ul>
            <li><strong><code>create</code></strong>: Establish a new datastream.</li>
            <li><strong><code>list</code></strong> / <strong><code>get</code></strong> / <strong><code>exists</code></strong>: Discover and inspect streaming channels.</li>
            <li><strong><code>stats</code></strong>: Retrieve detailed volumetric and performance statistics.</li>
            <li><strong><code>delete</code></strong>: Teardown deprecated datastreams.</li>
          </ul>
        </div>
      </section>

      <!-- template -->
      <section class="feature-card group cursor-pointer">
        <div class="card-glow"></div>
        <div class="card-content">
          <h2><code>template</code></h2>
          <p><strong>Purpose</strong>: Manage index and component templates.</p>
          <p><strong>Why it's important</strong>: Templates guarantee that newly generated rolling indices automatically inherit the correct shards, replicas, mappings, and lifecycles dynamically.</p>
          <ul>
            <li><strong><code>wizard</code></strong>: An interactive wizard that makes assembling advanced index schemas easy.</li>
            <li><strong><code>create</code></strong>: Apply a template JSON manifest.</li>
            <li><strong><code>list</code></strong> / <strong><code>get</code></strong>: Inspect currently active templates.</li>
            <li><strong><code>delete</code></strong>: Purge outdated templates.</li>
          </ul>
        </div>
      </section>

      <!-- ilm -->
      <section class="feature-card group cursor-pointer">
        <div class="card-glow"></div>
        <div class="card-content">
          <h2><code>ilm</code></h2>
          <p><strong>Purpose</strong>: Manage Index Lifecycle Management (ILM) policies.</p>
          <p><strong>Why it's important</strong>: ILM policies automate the transition of indices through Hot, Warm, Cold, and Delete phases automatically, saving hardware resources.</p>
          <ul>
            <li><strong><code>wizard</code></strong>: Interactively define retention durations, rollover sizes, and phase transitions.</li>
            <li><strong><code>create</code></strong>: Upload a customized JSON ILM policy.</li>
            <li><strong><code>list</code></strong> / <strong><code>get</code></strong>: Inspect policies governing your cluster.</li>
            <li><strong><code>delete</code></strong>: Remove an ILM policy.</li>
          </ul>
        </div>
      </section>

      <!-- snapshot -->
      <section class="feature-card group cursor-pointer">
        <div class="card-glow"></div>
        <div class="card-content">
          <h2><code>snapshot</code></h2>
          <p><strong>Purpose</strong>: Manage Snapshots and Repositories.</p>
          <p><strong>Why it's important</strong>: Hardware failures, ransomware, or unexpected deletions happen. Standardized cluster snapshotting is the only reliable path to disaster recovery.</p>
          <ul>
            <li><strong><code>repo</code></strong>: Manage the snapshot storage backends.</li>
            <li><strong><code>create</code></strong>: Trigger a manual snapshot of the cluster.</li>
            <li><strong><code>list</code></strong>: View all historical snapshots held in a repository.</li>
            <li><strong><code>restore</code></strong>: Recover your cluster state and data instantly.</li>
            <li><strong><code>delete</code></strong>: Prune old snapshots.</li>
          </ul>
        </div>
      </section>

      <!-- utils -->
      <section class="feature-card group cursor-pointer">
        <div class="card-glow"></div>
        <div class="card-content">
          <h2><code>utils</code></h2>
          <p><strong>Purpose</strong>: Miscellaneous utility commands.</p>
          <p><strong>Why it's important</strong>: Fast access to high-level cluster metrics and organizational operations for general system administration.</p>
          <ul>
            <li><strong><code>health</code></strong>: Get a quick snapshot of the cluster's pulse and node availability.</li>
            <li><strong><code>aliases</code></strong>: Inspect index aliases.</li>
            <li><strong><code>templates</code></strong>: Manage legacy index templates.</li>
          </ul>
        </div>
      </section>

    </div>
  </div>
</template>

<style scoped>
/* Public Site Equivalent Layout */
.docs-wrapper {
  position: relative;
  min-height: 100%;
}

/* Background Glow Effects to match elastro.fremenlabs.com */
.bg-glow {
  position: absolute;
  width: 50%;
  height: 50%;
  border-radius: 50%;
  filter: blur(140px);
  z-index: 1;
  pointer-events: none;
  opacity: 0.25;
}

.bg-glow-primary {
  top: -10%;
  right: -10%;
  background: radial-gradient(circle, hsl(var(--primary)) 0%, transparent 70%);
}

.bg-glow-accent {
  bottom: -20%;
  left: -20%;
  background: radial-gradient(circle, hsl(var(--teal)) 0%, transparent 70%);
}

.page-header {
  margin-bottom: 3rem;
  padding-bottom: 2rem;
  border-bottom: 1px solid hsl(var(--border) / 0.3);
}

.page-header h1 {
  font-size: 2.75rem;
  font-weight: 800;
  letter-spacing: -0.025em;
  background: linear-gradient(to right, hsl(var(--foreground)), hsl(var(--muted-foreground)));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  margin-bottom: 0.5rem;
}

.page-header p {
  color: hsl(var(--muted-foreground));
  font-size: 1.15rem;
  max-width: 600px;
}

.doc-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 2rem;
  padding-bottom: 4rem;
}

/* Glassmorphism Feature Cards */
.feature-card {
  position: relative;
  border-radius: 1.5rem; /* rounded-2xl */
  background: hsl(var(--card) / 0.4);
  backdrop-filter: blur(12px);
  border: 1px solid hsl(var(--border) / 0.5);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
}

.feature-card:hover {
  transform: translateY(-4px);
  border-color: hsl(var(--primary) / 0.4);
  box-shadow: 0 10px 40px -10px hsl(var(--primary) / 0.15);
  background: hsl(var(--card) / 0.6);
}

.card-glow {
  position: absolute;
  inset: -2px;
  background: linear-gradient(to right, hsl(var(--primary)/0.2), hsl(var(--teal)/0.2), hsl(var(--secondary)/0.2));
  opacity: 0;
  border-radius: 1.5rem;
  filter: blur(10px);
  transition: opacity 0.3s ease;
  z-index: 0;
}

.feature-card:hover .card-glow {
  opacity: 1;
}

.card-content {
  position: relative;
  z-index: 10;
  padding: 2rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  height: 100%;
}

.card-content h2 {
  font-size: 1.4rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
}

.card-content code {
  background: hsl(var(--primary) / 0.15);
  padding: 0.3rem 0.6rem;
  border-radius: 0.5rem;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.95em;
  color: hsl(var(--primary));
  letter-spacing: -0.01em;
  border: 1px solid hsl(var(--primary) / 0.2);
}

.card-content p {
  line-height: 1.6;
  color: hsl(var(--muted-foreground));
  font-size: 0.95rem;
}

.card-content strong {
  color: hsl(var(--foreground));
  font-weight: 600;
}

.card-content ul {
  list-style: none;
  padding-top: 1rem;
  margin-top: auto;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  border-top: 1px dashed hsl(var(--border) / 0.5);
}

.card-content li {
  position: relative;
  line-height: 1.5;
  color: hsl(var(--muted-foreground));
  font-size: 0.85rem;
  padding-left: 1.25rem;
}

.card-content li::before {
  content: "→";
  color: hsl(var(--primary));
  font-weight: bold;
  position: absolute;
  left: 0;
  font-family: inherit;
  transition: transform 0.2s ease;
}

.feature-card:hover li::before {
  transform: translateX(3px);
  color: hsl(var(--teal));
}
</style>
