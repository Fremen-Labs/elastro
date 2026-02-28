<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import { Rocket, Terminal, Code2, Database, Layers, Search, ChevronRight } from 'lucide-vue-next';
import CodeBlock from '../CodeBlock.vue';

const sections = [
  { id: 'getting-started', title: 'Getting Started', icon: Rocket },
  { id: 'installation', title: 'Installation', icon: Terminal },
  { id: 'quick-start', title: 'Quick Start', icon: Code2 },
  { id: 'client-setup', title: 'Client Setup', icon: Database },
  { id: 'index-management', title: 'Index Management', icon: Layers },
  { id: 'documents', title: 'Documents', icon: Database },
  { id: 'querying', title: 'Querying', icon: Search }
];

const activeSection = ref('getting-started');

const handleScroll = () => {
  const elements = document.querySelectorAll('[data-section]');
  const mainContent = document.querySelector('.main-content');
  if (!mainContent) return;
  
  const mainContentTop = mainContent.getBoundingClientRect().top;
  const triggerOffset = mainContentTop + 250;

  let current = activeSection.value;
  elements.forEach((element) => {
    const rect = element.getBoundingClientRect();
    if (rect.top <= triggerOffset) {
      current = element.id;
    }
  });
  activeSection.value = current;
};

onMounted(() => {
  const mainContent = document.querySelector('.main-content');
  if (mainContent) {
    mainContent.addEventListener('scroll', handleScroll);
  }
});

onUnmounted(() => {
  const mainContent = document.querySelector('.main-content');
  if (mainContent) {
    mainContent.removeEventListener('scroll', handleScroll);
  }
});

const scrollToSection = (id: string) => {
  const element = document.getElementById(id);
  const mainContent = document.querySelector('.main-content');
  
  if (element && mainContent) {
    const headerOffset = 180;
    const elementPosition = element.getBoundingClientRect().top;
    const mainContentPosition = mainContent.getBoundingClientRect().top;
    
    // Calculate total layout offset relative to current scroll
    const offsetPosition = elementPosition - mainContentPosition + mainContent.scrollTop - headerOffset;

    mainContent.scrollTo({
      top: offsetPosition,
      behavior: 'smooth'
    });
  }
};
</script>

<template>
  <div class="docs-layout">
    <!-- Horizontal Top Navigation -->
    <nav class="top-nav">
      <div class="nav-container">
        <span class="nav-title">On this page:</span>
        <div class="nav-links">
          <button
            v-for="section in sections"
            :key="section.id"
            @click="scrollToSection(section.id)"
            :class="['nav-btn', { active: activeSection === section.id }]"
          >
            <component :is="section.icon" class="icon-small shrink-0" />
            <span class="text-left hidden-mobile">{{ section.title }}</span>
          </button>
        </div>
      </div>
    </nav>

    <!-- Main Content -->
    <main class="main-content">
      <!-- Hero Section -->
      <div class="hero-section">
        <div class="badge">
          <Database class="icon-badge text-accent" />
          <span>Python API Reference</span>
        </div>
        <h1 class="page-title">
          Elastro <span class="gradient-text">Python Client</span>
        </h1>
        <p class="subtitle">
          Integrating Elasticsearch into your Python applications with type safety and elegance.
        </p>
      </div>

      <!-- Getting Started -->
      <section id="getting-started" data-section class="doc-section">
        <h2 class="section-title">
          <Rocket class="icon-large text-primary" />
          Getting Started
        </h2>
        <p class="section-desc">
          Elastro is a modern Python library that simplifies working with Elasticsearch.
          It provides a fluent, chainable API that makes complex queries readable and maintainable.
        </p>
        <div class="info-card">
          <h3 class="info-title">Why Elastro?</h3>
          <ul class="info-list">
            <li>
              <ChevronRight class="icon-small text-primary shrink-0 mt-05" />
              <span><strong>Fluent API:</strong> Chain methods for readable, maintainable queries</span>
            </li>
            <li>
              <ChevronRight class="icon-small text-primary shrink-0 mt-05" />
              <span><strong>Type Safety:</strong> Built-in validation for reliable data handling</span>
            </li>
            <li>
              <ChevronRight class="icon-small text-primary shrink-0 mt-05" />
              <span><strong>Less Boilerplate:</strong> Reduce code by up to 60% compared to raw Elasticsearch</span>
            </li>
            <li>
              <ChevronRight class="icon-small text-primary shrink-0 mt-05" />
              <span><strong>Production Ready:</strong> Battle-tested and ready for enterprise use</span>
            </li>
          </ul>
        </div>
      </section>

      <!-- Installation -->
      <section id="installation" data-section class="doc-section">
        <h2 class="section-title">
          <Terminal class="icon-large text-primary" />
          Installation
        </h2>
        <p class="section-desc">
          Install Elastro using pip. It requires Python 3.8 or higher.
        </p>
        <CodeBlock
          code="# Install from PyPI
pip install elastro-client

# Or install from source
pip install git+https://github.com/Fremen-Labs/elastro.git"
          language="bash"
          :showLineNumbers="true"
          title="Installation"
        />
      </section>

      <!-- Quick Start -->
      <section id="quick-start" data-section class="doc-section">
        <h2 class="section-title">
          <Code2 class="icon-large text-primary" />
          Quick Start
        </h2>
        <p class="section-desc">
          Get up and running with Elastro in minutes. This example shows the basic workflow.
        </p>
        <CodeBlock
          code="from elastro import ElasticsearchClient, IndexManager, DocumentManager
from elastro.advanced import QueryBuilder

# Connect to your Elasticsearch cluster
client = ElasticsearchClient(
    hosts=[&quot;http://localhost:9200&quot टेबलेट;&quot;http://127.0.0.1:9200&quot;]
)
client.connect()

# Create managers
index_manager = IndexManager(client)
doc_manager = DocumentManager(client)

# Create an index with mappings
index_manager.create(
    &quot;products&quot;,
    mappings={
        &quot;properties&quot;: {
            &quot;name&quot;: {&quot;type&quot;: &quot;text&quot;},
            &quot;price&quot;: {&quot;type&quot;: &quot;float&quot;},
            &quot;category&quot;: {&quot;type&quot;: &quot;keyword&quot;},
            &quot;rating&quot;: {&quot;type&quot;: &quot;float&quot;}
        }
    }
)

# Index a document
doc_manager.index(
    &quot;products&quot;,
    id=&quot;1&quot;,
    document={
        &quot;name&quot;: &quot;Laptop Pro&quot;,
        &quot;price&quot;: 1299.99,
        &quot;category&quot;: &quot;electronics&quot;,
        &quot;rating&quot;: 4.8
    }
)

# Build and execute a search query
query_builder = QueryBuilder()
query_builder.match(&quot;name&quot;, &quot;laptop&quot;)
query_builder.range(&quot;price&quot;, gte=500, lte=2000)
query = query_builder.build()

results = doc_manager.search(
    &quot;products&quot;,
    query,
    {&quot;sort&quot;: [{&quot;rating&quot;: {&quot;order&quot;: &quot;desc&quot;}}], &quot;size&quot;: 10}
)

# Access results
for hit in results[&quot;hits&quot;][&quot;hits&quot;]:
    print(f&quot;{hit['_source']['name']}: ${hit['_source']['price']}&quot;)"
          language="python"
          :showLineNumbers="true"
          title="quickstart.py"
        />
      </section>

      <!-- Client Setup -->
      <section id="client-setup" data-section class="doc-section">
        <h2 class="section-title">
          <Database class="icon-large text-primary" />
          Client Setup
        </h2>
        <p class="section-desc">
          Configure your ElastroClient with connection settings, authentication, and more.
        </p>
        <CodeBlock
          code="from elastro import ElasticsearchClient

# Single host
client = ElasticsearchClient(hosts=[&quot;http://localhost:9200&quot;])
client.connect()

# Multiple hosts (for high availability)
client = ElasticsearchClient(
    hosts=[
        &quot;http://node1:9200&quot;,
        &quot;http://node2:9200&quot;,
        &quot;http://node3:9200&quot;
    ]
)
client.connect()"
          language="python"
          :showLineNumbers="true"
          title="basic_connection.py"
        />
      </section>

      <!-- Index Management -->
      <section id="index-management" data-section class="doc-section">
        <h2 class="section-title">
          <Layers class="icon-large text-primary" />
          Index Management
        </h2>
        <p class="section-desc">
          Create, configure, and manage Elasticsearch indices with ease.
        </p>
        <CodeBlock
          code="from elastro import ElasticsearchClient, IndexManager

client = ElasticsearchClient(hosts=[&quot;http://localhost:9200&quot;])
client.connect()
index_manager = IndexManager(client)

# Create a simple index
index_manager.create(&quot;products&quot;)"
          language="python"
          :showLineNumbers="true"
          title="create_index.py"
        />
      </section>

      <!-- Document Operations -->
      <section id="documents" data-section class="doc-section">
        <h2 class="section-title">
          <Database class="icon-large text-primary" />
          Document Operations
        </h2>
        <p class="section-desc">
          Index, update, retrieve, and delete documents with simple, intuitive methods.
        </p>
        <CodeBlock
          code="from elastro import ElasticsearchClient, DocumentManager

client = ElasticsearchClient(hosts=[&quot;http://localhost:9200&quot;])
client.connect()
doc_manager = DocumentManager(client)

# Index a single document (auto-generate ID)
doc_manager.index(
    &quot;products&quot;,
    id=None,
    document={
        &quot;name&quot;: &quot;Laptop Pro&quot;,
        &quot;price&quot;: 1299.99,
        &quot;category&quot;: &quot;electronics&quot;
    }
)"
          language="python"
          :showLineNumbers="true"
          title="index_documents.py"
        />
      </section>

      <!-- Querying -->
      <section id="querying" data-section class="doc-section">
        <h2 class="section-title">
          <Search class="icon-large text-primary" />
          Querying
        </h2>
        <p class="section-desc">
          Build powerful queries with Elastro's QueryBuilder. No more nested dictionaries!
        </p>
        <CodeBlock
          code="from elastro import ElasticsearchClient, DocumentManager
from elastro.advanced import QueryBuilder

client = ElasticsearchClient(hosts=[&quot;http://localhost:9200&quot;])
client.connect()
doc_manager = DocumentManager(client)

# Match query
query_builder = QueryBuilder()
query_builder.match(&quot;name&quot;, &quot;laptop&quot;)
query = query_builder.build()
results = doc_manager.search(&quot;products&quot;, query)"
          language="python"
          :showLineNumbers="true"
          title="basic_queries.py"
        />
      </section>

    </main>
  </div>
</template>

<style scoped>
.docs-layout {
  display: flex;
  flex-direction: column;
  position: relative;
  width: 100%;
}

/* Horizontal Top Navigation */
.top-nav {
  position: sticky;
  top: 0;
  z-index: 30;
  background: hsl(var(--background) / 0.8);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid hsl(var(--border) / 0.5);
  margin-bottom: 2rem;
  padding: 0.75rem 0;
}

.nav-container {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  width: 100%;
  padding: 0 1rem;
}

.nav-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: hsl(var(--foreground));
  white-space: nowrap;
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  overflow-x: auto;
  padding-bottom: 2px;
}

/* Hide scrollbar for nav links */
.nav-links::-webkit-scrollbar {
  display: none;
}
.nav-links {
  -ms-overflow-style: none;
  scrollbar-width: none;
}

.nav-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  border-radius: 0.5rem;
  border: 1px solid transparent;
  background: transparent;
  color: hsl(var(--muted-foreground));
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.nav-btn:hover {
  background: hsl(var(--muted) / 0.5);
  color: hsl(var(--foreground));
}

.nav-btn.active {
  background: hsl(var(--primary) / 0.1);
  color: hsl(var(--primary));
}

.main-content {
  flex: 1;
  width: 100%;
}

.hero-section {
  margin-bottom: 3rem;
  animation: fade-in 0.5s ease-out;
}

@keyframes fade-in {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

.badge {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  border-radius: 9999px;
  background: hsl(var(--card) / 0.4);
  backdrop-filter: blur(8px);
  border: 1px solid hsl(var(--border) / 0.5);
  margin-bottom: 1.5rem;
}

.badge span {
  font-size: 0.875rem;
  font-weight: 500;
  color: hsl(var(--muted-foreground));
}

.text-accent {
  color: hsl(var(--teal));
}

.page-title {
  font-size: 3rem;
  font-weight: 800;
  margin-bottom: 1rem;
  letter-spacing: -0.025em;
}

.gradient-text {
  background: linear-gradient(to right, hsl(var(--primary)), hsl(var(--teal)));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.subtitle {
  font-size: 1.25rem;
  color: hsl(var(--muted-foreground));
  line-height: 1.6;
}

.doc-section {
  margin-bottom: 4rem;
  scroll-margin-top: 6rem;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 1.875rem;
  font-weight: 700;
  margin-bottom: 1rem;
  color: hsl(var(--foreground));
}

.text-primary {
  color: hsl(var(--primary));
}

.section-desc {
  font-size: 1.125rem;
  color: hsl(var(--muted-foreground));
  margin-bottom: 1.5rem;
}

.info-card {
  background: hsl(var(--card) / 0.4);
  backdrop-filter: blur(4px);
  border: 1px solid hsl(var(--border) / 0.5);
  border-radius: 0.75rem;
  padding: 1.5rem;
  margin-bottom: 1.5rem;
}

.info-title {
  font-size: 1.25rem;
  font-weight: 600;
  margin-bottom: 0.75rem;
}

.info-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  list-style: none;
  padding: 0;
  margin: 0;
}

.info-list li {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  color: hsl(var(--muted-foreground));
}

.info-list strong {
  color: hsl(var(--foreground));
  font-weight: 600;
}

.icon-small {
  width: 1rem;
  height: 1rem;
}
.icon-badge { width: 1rem; height: 1rem; }
.icon-large { width: 2rem; height: 2rem; }
.shrink-0 { flex-shrink: 0; }
.mt-05 { margin-top: 0.125rem; }
.text-left { text-align: left; }

.mobile-toggle {
  display: none;
}

@media (max-width: 1024px) {
  .sidebar {
    position: fixed;
    top: 4rem;
    left: 0;
    height: calc(100vh - 4rem);
    background: hsl(var(--background));
    transform: translateX(-100%);
    transition: transform 0.3s;
    border-right: 1px solid hsl(var(--border) / 0.5);
  }

  .sidebar-open {
    transform: translateX(0);
  }

  .mobile-toggle {
    display: block;
    position: fixed;
    top: 4rem;
    left: 0;
    right: 0;
    background: hsl(var(--background));
    border-bottom: 1px solid hsl(var(--border) / 0.5);
    padding: 0.75rem 1rem;
    z-index: 20;
  }

  .toggle-btn {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    background: transparent;
    border: none;
    color: hsl(var(--foreground));
    font-size: 0.875rem;
    font-weight: 500;
  }

  .main-content {
    padding-top: 4rem;
    padding-left: 1rem;
    padding-right: 1rem;
  }
}
</style>
