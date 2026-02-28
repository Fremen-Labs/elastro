<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import { Terminal, Command, Settings, RotateCcw } from 'lucide-vue-next';
import CodeBlock from '../CodeBlock.vue';

const sections = [
  { id: 'installation', title: 'Installation', icon: Terminal },
  { id: 'cli-usage', title: 'CLI Usage', icon: Command },
  { id: 'ilm-policy', title: 'ILM Policy Management', icon: Settings },
  { id: 'snapshot-restore', title: 'Snapshot & Restore', icon: RotateCcw }
];

const activeSection = ref('installation');

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
          <Terminal class="icon-badge text-accent" />
          <span>CLI Reference</span>
        </div>
        <h1 class="page-title">
          Elastro <span class="gradient-text">CLI</span>
        </h1>
        <p class="subtitle">
          Manage your Elasticsearch clusters, snapshots, and ILM policies directly from the terminal.
        </p>
      </div>

      <!-- Installation -->
      <section id="installation" data-section class="doc-section">
        <h2 class="section-title">
          <Terminal class="icon-large text-primary" />
          Installation
        </h2>
        <p class="section-desc">
          The CLI is installed automatically when you install Elastro.
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

      <!-- CLI Usage -->
      <section id="cli-usage" data-section class="doc-section">
        <h2 class="section-title">
          <Command class="icon-large text-primary" />
          Common Commands
        </h2>
        <p class="section-desc">
          Initialize configuration and perform common operations.
        </p>
        <CodeBlock
          code="# Initialize configuration
elastro config init

# Create an index
elastro index create products --shards 3 --replicas 1

# Interactive Template Wizard
elastro template wizard

# Add a document
elastro doc index products --id 1 --file ./product.json

# Search documents
elastro doc search products --term category=laptop"
          language="bash"
          :showLineNumbers="true"
          title="Common Commands"
        />
      </section>

      <!-- ILM Management -->
      <section id="ilm-policy" data-section class="doc-section">
        <h2 class="section-title">
          <Settings class="icon-large text-primary" />
          ILM Policy Management
        </h2>
        <p class="section-desc">
          Easily manage your Index Lifecycle Management policies with an interactive wizard.
        </p>
        <CodeBlock
          code="# List all policies (Table View)
elastro ilm list

# List with full JSON details
elastro ilm list --full

# Create a policy using the Interactive Wizard (Recommended)
elastro ilm create my-policy

# Create a policy from a file
elastro ilm create my-policy --file ./policy.json

# Explain lifecycle status for an index
elastro ilm explain my-index"
          language="bash"
          :showLineNumbers="true"
          title="ILM Commands"
        />
      </section>

      <!-- Snapshot & Restore -->
      <section id="snapshot-restore" data-section class="doc-section">
        <h2 class="section-title">
          <RotateCcw class="icon-large text-primary" />
          Snapshot & Restore
        </h2>
        <p class="section-desc">
          Manage backup repositories and restore data with confidence using the restoration wizard.
        </p>

        <h3 class="subsection-title">Repository Management</h3>
        <CodeBlock
          code="# List all repositories
elastro snapshot repo list

# Create a filesystem repository
elastro snapshot repo create my_backup fs --setting location=/tmp/backups

# Create an S3 repository
elastro snapshot repo create my_s3_backup s3 --setting bucket=my-bucket --setting region=us-east-1"
          language="bash"
          :showLineNumbers="true"
          title="Repository Commands"
        />

        <h3 class="subsection-title">Snapshot Operations</h3>
        <CodeBlock
          code="# List snapshots in a repository
elastro snapshot list my_backup

# Create a snapshot (async default)
elastro snapshot create my_backup snapshot_1

# Create and wait for completion
elastro snapshot create my_backup snapshot_2 --wait --indices &quot;logs-*,metrics-*&quot;"
          language="bash"
          :showLineNumbers="true"
          title="Snapshot Commands"
        />

        <h3 class="subsection-title">Restoration</h3>
        <CodeBlock
          code="# Restore a snapshot (Interactive Wizard)
elastro snapshot restore
# Launches a wizard to select repo -> snapshot -> indices -> rename pattern

# Restore specific indices from CLI
elastro snapshot restore my_backup snapshot_1 --indices &quot;logs-*&quot;"
          language="bash"
          :showLineNumbers="true"
          title="Restore Commands"
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

/* Main Content */
.main-content {
  flex: 1;
  width: 100%;
  padding-bottom: 6rem;
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

.subsection-title {
  font-size: 1.25rem;
  font-weight: 600;
  margin: 2rem 0 1rem;
  color: hsl(var(--foreground));
}

.icon-small {
  width: 1rem;
  height: 1rem;
}

.icon-badge {
  width: 1rem;
  height: 1rem;
}

.icon-large {
  width: 2rem;
  height: 2rem;
}

.shrink-0 {
  flex-shrink: 0;
}

.text-left {
  text-align: left;
}

/* Mobile Toggle */
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
