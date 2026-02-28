<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { state } from '../store'
import axios from 'axios'
import { AnsiUp } from 'ansi_up'

const route = useRoute()
const router = useRouter()
const apiBase = import.meta.env.VITE_API_URL || ''

const clusterName = ref(decodeURIComponent(route.params.name as string))
const loading = ref(true)
const error = ref<string | null>(null)
const details = ref<any>(null)

// Modal State
const activeModal = ref<'nodes' | 'indices' | 'ilm' | 'backups' | null>(null)
const closeModal = () => { activeModal.value = null }

const fetchClusterDetails = async () => {
  if (!state.token) return
  
  loading.value = true
  error.value = null
  
  try {
    const res = await axios.get(`${apiBase}/api/cluster/${encodeURIComponent(clusterName.value)}`, {
      headers: { Authorization: `Bearer ${state.token}` }
    })
    details.value = res.data
  } catch (err: any) {
    if (err.response?.status === 401) {
       error.value = "Unauthorized: Invalid or missing security token."
    } else if (err.response?.status === 404) {
       error.value = `Cluster '${clusterName.value}' not found in configuration.`
    } else {
       error.value = `Failed to fetch detailed metrics for '${clusterName.value}'. Is the cluster reachable?`
    }
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (state.token) {
    fetchClusterDetails()
  } else {
    const checkToken = setInterval(() => {
      if (state.token) {
        clearInterval(checkToken)
        fetchClusterDetails()
      }
    }, 100)
  }
})

const getHealthColor = (health: string) => {
  switch(health) {
    case 'green': return 'hsl(var(--teal))'
    case 'yellow': return 'hsl(var(--secondary))'
    case 'red': return 'hsl(var(--destructive))'
    default: return 'hsl(var(--muted-foreground))'
  }
}

// CLI Emulator Logic
interface HistoryItem {
  type: 'input' | 'output' | 'error' | 'system'
  text: string
}

const cliInput = ref('')
const cliInputRef = ref<HTMLInputElement | null>(null)

const commandTree: Record<string, string[]> = {
  index: ['close', 'create', 'delete', 'exists', 'find', 'get', 'list', 'open', 'update', 'wizard'],
  doc: ['bulk', 'bulk-delete', 'delete', 'get', 'index', 'search', 'update'],
  datastream: ['create', 'delete', 'get', 'list', 'rollover'],
  config: ['get', 'init', 'list', 'set'],
  snapshot: ['create', 'delete', 'list', 'repo', 'restore'],
  template: ['create', 'delete', 'get', 'list', 'wizard'],
  ilm: ['create', 'delete', 'explain', 'get', 'list', 'start', 'stop'],
  cluster: ['allocation', 'settings'],
  security: ['roles', 'users'],
  tasks: ['cancel', 'list'],
  ingest: ['pipelines', 'simulate'],
  utils: ['aliases', 'health', 'templates']
}

const cliChips = computed(() => {
  const trimmed = cliInput.value.trim()
  if (!trimmed) {
    return Object.keys(commandTree)
  }
  
  const parts = trimmed.split(/\s+/)
  const root = parts[0] as string
  
  // Show subcommands if there's only one root word present and it exists in our tree
  if (parts.length === 1 && root && commandTree[root]) {
    return commandTree[root]
  }
  
  // Hide chips if they are deeper into passing complex arguments
  return []
})

const focusInput = () => {
  if (cliInputRef.value) {
    cliInputRef.value.focus()
  }
}

const appendChip = (chip: string) => {
  const current = cliInput.value.trim()
  cliInput.value = current ? current + ' ' + chip + ' ' : chip + ' '
  focusInput()
}
const cliHistory = ref<HistoryItem[]>([
  { type: 'system', text: `Connected to Elastro CLI. Scope restricted to '${clusterName.value}'.` },
  { type: 'system', text: 'Type a command (e.g., "indices list") and press Enter.' }
])
const cliLoading = ref(false)
const terminalBody = ref<HTMLElement | null>(null)

const executeCommand = async () => {
  const cmd = cliInput.value.trim()
  if (!cmd || cliLoading.value) return

  // Add to history
  cliHistory.value.push({ type: 'input', text: `$ ${cmd}` })
  cliInput.value = ''
  cliLoading.value = true

  // Auto scroll
  setTimeout(() => {
    if (terminalBody.value) {
      terminalBody.value.scrollTop = terminalBody.value.scrollHeight
    }
  }, 10)

  try {
    const res = await axios.post(
      `${apiBase}/api/cluster/${encodeURIComponent(clusterName.value)}/cli`,
      { command: cmd },
      { headers: { Authorization: `Bearer ${state.token}` } }
    )
    
    // Convert Typer/Rich VT100 ANSI codes into colorful HTML spans natively 
    const ansiUp = new AnsiUp()
    
    if (res.data.output) {
       const htmlOutput = ansiUp.ansi_to_html(res.data.output)
       
       cliHistory.value.push({ 
         type: res.data.exit_code === 0 ? 'output' : 'error', 
         text: htmlOutput 
       })
    } else {
       cliHistory.value.push({ type: 'system', text: '[Command completed with no output]' })
    }
  } catch (err: any) {
    const errorMsg = err.response?.data?.detail || err.message || 'Unknown execution error'
    cliHistory.value.push({ type: 'error', text: `Error: ${errorMsg}` })
  } finally {
    cliLoading.value = false
    
    // Auto scroll again after response
    setTimeout(() => {
      if (terminalBody.value) {
        terminalBody.value.scrollTop = terminalBody.value.scrollHeight
      }
      focusInput()
    }, 10)
  }
}
</script>

<template>
  <div class="cluster-detail-page animate-fade-in">
    <div class="header-actions">
      <button @click="router.push('/')" class="btn btn-secondary back-btn">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="19" y1="12" x2="5" y2="12"></line><polyline points="12 19 5 12 12 5"></polyline></svg>
        Back to Dashboard
      </button>
    </div>

    <div v-if="loading" class="metrics-grid mt-4">
      <div v-for="i in 4" :key="i" class="card metric-card">
        <div class="metric-header" style="margin-bottom: 1rem;">
          <div class="skeleton skeleton-badge" style="width: 20px; height: 20px; border-radius: 4px;"></div>
          <div class="skeleton skeleton-text w-1/2" style="margin-bottom: 0;"></div>
        </div>
        <div class="metric-body">
          <div class="skeleton skeleton-jumbo w-1/3 mb-4"></div>
          <div class="skeleton skeleton-text w-full"></div>
        </div>
      </div>
    </div>

    <div v-else-if="error" class="error-banner card">
      <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/></svg>
      <div class="error-text">
        <h3>Connection Failed</h3>
        <p>{{ error }}</p>
      </div>
    </div>

    <div v-else-if="details" class="detail-content">
      <header class="page-header">
        <div class="title-group">
          <h1>{{ details.name }}</h1>
          <span class="health-badge outline" :style="{ borderColor: getHealthColor(details.health), color: getHealthColor(details.health) }">
            {{ details.health }}
          </span>
        </div>
        <p class="host-link"><a :href="details.host" target="_blank">{{ details.host }}</a></p>
      </header>

      <div class="metrics-grid">
        <!-- Node Topology -->
        <button class="card metric-card interactive-card" @click="activeModal = 'nodes'">
          <div class="metric-header">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="2" ry="2"></rect><rect x="9" y="9" width="6" height="6"></rect><line x1="9" y1="1" x2="9" y2="4"></line><line x1="15" y1="1" x2="15" y2="4"></line><line x1="9" y1="20" x2="9" y2="23"></line><line x1="15" y1="20" x2="15" y2="23"></line><line x1="20" y1="9" x2="23" y2="9"></line><line x1="20" y1="14" x2="23" y2="14"></line><line x1="1" y1="9" x2="4" y2="9"></line><line x1="1" y1="14" x2="4" y2="14"></line></svg>
            <h3>Node Topology</h3>
          </div>
          <div class="metric-body">
            <div class="mega-stat">{{ details.nodes.total }}</div>
            <div class="sub-stats">
              <div v-for="(count, role) in details.nodes.roles" :key="role" class="sub-stat-badge">
                {{ role }}: <strong>{{ count }}</strong>
              </div>
            </div>
          </div>
        </button>

        <!-- Index Health -->
        <button class="card metric-card interactive-card" @click="activeModal = 'indices'">
          <div class="metric-header">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 22h14a2 2 0 0 0 2-2V7.5L14.5 2H6a2 2 0 0 0-2 2v4"/><polyline points="14 2 14 8 20 8"/><path d="M2 15h10"/><path d="m9 18 3-3-3-3"/></svg>
            <h3>Index Health</h3>
          </div>
          <div class="metric-body">
            <div class="mega-stat">{{ details.indices.total }}</div>
            <div class="health-breakdown mt-3">
              <div class="health-bar-segment" :style="{ 
                width: `${(details.indices.total - details.indices.red - details.indices.yellow) / details.indices.total * 100}%`,
                background: 'hsl(var(--teal))' 
              }" title="Green Indices"></div>
              <div class="health-bar-segment" :style="{ 
                width: `${details.indices.yellow / details.indices.total * 100}%`,
                background: 'hsl(var(--secondary))' 
              }" title="Yellow Indices"></div>
              <div class="health-bar-segment" :style="{ 
                width: `${details.indices.red / details.indices.total * 100}%`,
                background: 'hsl(var(--destructive))' 
              }" title="Red Indices"></div>
            </div>
            <div class="health-legend">
              <span><span class="dot green"></span> {{ details.indices.total - details.indices.red - details.indices.yellow }} Green</span>
              <span><span class="dot yellow"></span> {{ details.indices.yellow }} Yellow</span>
              <span><span class="dot red"></span> {{ details.indices.red }} Red</span>
            </div>
          </div>
        </button>

        <!-- ILM Policies -->
        <button class="card metric-card interactive-card" @click="activeModal = 'ilm'">
          <div class="metric-header">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
            <h3>Lifecycle Policies</h3>
          </div>
          <div class="metric-body">
            <div class="mega-stat">{{ details.ilm.policy_count }}</div>
            <p class="text-sm text-muted mt-2">Active Index Lifecycle Management configurations governing data retention.</p>
          </div>
        </button>

        <!-- Backups -->
        <button class="card metric-card interactive-card" @click="activeModal = 'backups'">
          <div class="metric-header">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            <h3>Snapshot Repositories</h3>
          </div>
          <div class="metric-body">
            <div class="status-indicator mb-4" :class="details.backups.configured ? 'status-good' : 'status-bad'">
              {{ details.backups.configured ? 'Configured' : 'Not Configured' }}
            </div>
            
            <div class="repos-list" v-if="details.backups.configured">
              <div v-for="repo in details.backups.repositories" :key="repo.name" class="repo-item">
                <span class="repo-name">{{ repo.name }}</span>
                <span class="repo-type badge-outline">{{ repo.type }}</span>
              </div>
            </div>
            <p v-else class="text-sm text-muted">No snapshot repositories are currently registered for this cluster.</p>
          </div>
        </button>

      </div>

      <!-- Interactive Embedded CLI -->
      <div class="card terminal-card mt-4">
        <div class="terminal-header">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="terminal-icon"><polyline points="4 17 10 11 4 5"></polyline><line x1="12" y1="19" x2="20" y2="19"></line></svg>
          <h3>Elastro Controller</h3>
          
          <div class="cli-chips">
            <button v-for="chip in cliChips" :key="chip" @click="appendChip(chip)" 
              :class="['cli-chip', { 'chip-destructive': ['delete', 'bulk-delete', 'cancel'].includes(chip) }]">
              {{ chip }}
            </button>
          </div>

          <div class="terminal-actions">
            <button class="btn-clear" @click="cliHistory = []" title="Clear Terminal">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
            </button>
          </div>
        </div>
        
        <div class="terminal-body" ref="terminalBody" @click="focusInput">
          <div v-for="(item, idx) in cliHistory" :key="idx" :class="['cli-line', `cli-${item.type}`]">
            <pre v-html="item.text"></pre>
          </div>
          <div v-if="cliLoading" class="cli-line cli-system cli-loading">
            Executing command... <span class="cursor-blink">_</span>
          </div>
        </div>
        
        <form @submit.prevent="executeCommand" class="terminal-input-form">
          <span class="prompt">$</span>
          <input 
            ref="cliInputRef"
            type="text" 
            v-model="cliInput" 
            class="cli-input" 
            placeholder="Type a command and press Enter..." 
            :disabled="cliLoading"
            autocomplete="off"
            spellcheck="false"
          >
        </form>
      </div>
      
      <!-- Glassmorphic Modal Overlay -->
      <div v-if="activeModal" class="modal-overlay glass-panel" @click.self="closeModal">
        <div class="modal-content animate-zoom-in">
          <div class="modal-header">
            <h2>
              {{ 
                activeModal === 'nodes' ? 'Node Topology Details' :
                activeModal === 'indices' ? 'Index Health Breakdown' :
                activeModal === 'ilm' ? 'Lifecycle Policies' :
                'Snapshot Repositories'
              }}
            </h2>
            <button class="btn-close" @click="closeModal" aria-label="Close modal">
              <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
            </button>
          </div>
          
          <div class="modal-body">
            <!-- Modal: Nodes -->
            <div v-if="activeModal === 'nodes'">
              <div class="detail-grid">
                 <div v-for="(count, role) in details.nodes.roles" :key="role" class="detail-row">
                   <span class="detail-label">{{ role }} Nodes</span>
                   <span class="detail-value badge-outline">{{ count }}</span>
                 </div>
              </div>
              <p class="text-muted mt-4">Total nodes operating in this cluster: {{ details.nodes.total }}</p>
            </div>

            <!-- Modal: Indices -->
            <div v-else-if="activeModal === 'indices'">
               <div class="health-legend vertical mt-2">
                  <div class="legend-row mb-3">
                    <span class="dot green"></span> 
                    <span class="legend-text"><strong>{{ details.indices.total - details.indices.red - details.indices.yellow }}</strong> Green (Healthy) Indices</span>
                  </div>
                  <div class="legend-row mb-3">
                    <span class="dot yellow"></span> 
                    <span class="legend-text"><strong>{{ details.indices.yellow }}</strong> Yellow (Warning) Indices</span>
                  </div>
                  <div class="legend-row">
                    <span class="dot red"></span> 
                    <span class="legend-text"><strong>{{ details.indices.red }}</strong> Red (Critical/Offline) Indices</span>
                  </div>
               </div>
            </div>

            <!-- Modal: ILM -->
            <div v-else-if="activeModal === 'ilm'">
               <div v-if="details.ilm.policy_count > 0">
                 <div class="detail-row mb-4">
                   <span class="detail-label">Active Global Policies</span>
                   <span class="detail-value badge-outline">{{ details.ilm.policy_count }}</span>
                 </div>
                 <p class="text-sm text-muted">To view deeper ILM configurations and rulesets, run <code class="mono-code">ilm list</code> or <code class="mono-code">ilm explain</code> in the Controller.</p>
               </div>
               <p v-else class="text-muted">No Data Lifecycle Policies are currently registered on this cluster.</p>
            </div>

            <!-- Modal: Backups -->
            <div v-else-if="activeModal === 'backups'">
               <div v-if="details.backups.configured">
                  <div class="repos-list">
                    <div v-for="repo in details.backups.repositories" :key="repo.name" class="repo-item detail-row">
                      <span class="repo-name">{{ repo.name }}</span>
                      <span class="repo-type badge-outline">{{ repo.type }}</span>
                    </div>
                  </div>
               </div>
               <p v-else class="text-muted">No snapshot repositories are configured.</p>
            </div>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<style scoped>
.header-actions {
  margin-bottom: 2rem;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  font-size: 0.875rem;
}

.page-header {
  margin-bottom: 3rem;
  padding-bottom: 1.5rem;
  border-bottom: 1px solid hsl(var(--border) / 0.3);
}

.title-group {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 0.5rem;
}

.title-group h1 {
  font-size: 2.5rem;
  font-weight: 700;
  letter-spacing: -0.025em;
}

.host-link a {
  color: hsl(var(--muted-foreground));
  text-decoration: none;
  transition: color 0.2s;
  font-family: var(--font-mono);
  font-size: 0.95rem;
}

.host-link a:hover {
  color: hsl(var(--primary));
  text-decoration: underline;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
  gap: 2rem;
}

.metric-card {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.metric-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
  color: hsl(var(--muted-foreground));
}

.metric-header h3 {
  font-size: 1.1rem;
  font-weight: 600;
  color: hsl(var(--foreground));
}

.mega-stat {
  font-size: 3.5rem;
  font-weight: 800;
  line-height: 1;
  background: var(--gradient-accent);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  margin-bottom: 1rem;
}

.sub-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.sub-stat-badge {
  background: hsl(var(--muted) / 0.5);
  padding: 0.25rem 0.5rem;
  border-radius: 0.25rem;
  font-size: 0.85rem;
  color: hsl(var(--muted-foreground));
  border: 1px solid hsl(var(--border) / 0.5);
}

.sub-stat-badge strong {
  color: hsl(var(--foreground));
}

/* Health Bar */
.health-breakdown {
  display: flex;
  height: 8px;
  width: 100%;
  border-radius: 4px;
  overflow: hidden;
  background: hsl(var(--muted));
  margin-bottom: 1rem;
}

.health-bar-segment {
  height: 100%;
  transition: width 1s ease-in-out;
}

.health-legend {
  display: flex;
  gap: 1rem;
  font-size: 0.85rem;
  color: hsl(var(--muted-foreground));
}

.dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 0.25rem;
}
.dot.green { background: hsl(var(--teal)); }
.dot.yellow { background: hsl(var(--secondary)); }
.dot.red { background: hsl(var(--destructive)); }

/* Backups */
.status-indicator {
  display: inline-block;
  padding: 0.25rem 0.75rem;
  border-radius: 999px;
  font-size: 0.85rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.status-good {
  background: hsl(var(--teal) / 0.1);
  color: hsl(var(--teal));
}

.status-bad {
  background: hsl(var(--destructive) / 0.1);
  color: hsl(var(--destructive));
}

.repos-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.repo-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem;
  background: hsl(var(--muted) / 0.3);
  border-radius: var(--radius);
  border: 1px solid hsl(var(--border) / 0.5);
}

.repo-name {
  font-family: var(--font-mono);
  font-weight: 600;
}

.badge-outline {
  font-size: 0.75rem;
  padding: 0.1rem 0.5rem;
  border-radius: 999px;
  border: 1px solid currentColor;
  opacity: 0.7;
  text-transform: uppercase;
}

/* Utilities */
.text-muted { color: hsl(var(--muted-foreground)); }
.text-sm { font-size: 0.875rem; }
.mt-2 { margin-top: 0.5rem; }
.mt-3 { margin-top: 1rem; }
.mb-4 { margin-bottom: 1.5rem; }

.health-badge.outline {
  background: transparent;
  border: 1.5px solid;
  padding: 0.25rem 0.75rem;
  border-radius: 999px;
  font-size: 0.85rem;
  font-weight: 700;
  text-transform: uppercase;
}

.error-banner {
  display: flex;
  align-items: flex-start;
  gap: 1.5rem;
  padding: 2rem;
  background: hsl(var(--destructive) / 0.05);
  border-left: 4px solid hsl(var(--destructive));
  color: hsl(var(--foreground));
}

.error-banner svg {
  color: hsl(var(--destructive));
  flex-shrink: 0;
  margin-top: 0.25rem;
}

.error-text h3 {
  font-size: 1.25rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
  color: hsl(var(--destructive));
}

.loader-container {
  display: flex;
  justify-content: center;
  padding: 5rem 0;
}

/* Embedded CLI Terminal */
.mt-4 { margin-top: 2rem; }

.terminal-card {
  display: flex;
  flex-direction: column;
  background: hsl(240 10% 4%); /* Deep dark background */
  border: 1px solid hsl(var(--border));
  overflow: hidden;
  padding: 0;
}

.terminal-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  background: hsl(var(--muted) / 0.5);
  border-bottom: 1px solid hsl(var(--border) / 0.5);
  color: hsl(var(--muted-foreground));
}

.terminal-header h3 {
  font-size: 0.95rem;
  font-weight: 600;
  color: hsl(var(--foreground));
  letter-spacing: 0.025em;
  margin: 0;
}

.cli-chips {
  display: flex;
  gap: 0.5rem;
  margin: 0 1rem;
  overflow-x: auto;
  flex-grow: 1;
  padding-bottom: 6px; /* For scrollbar breathing room */
  padding-top: 4px;
}

.cli-chips::-webkit-scrollbar {
  height: 4px;
}
.cli-chips::-webkit-scrollbar-thumb {
  background: hsl(var(--primary) / 0.5);
  border-radius: 4px;
}

.cli-chip {
  background: hsl(var(--primary) / 0.2);
  color: hsl(var(--primary));
  border: 2px solid hsl(var(--primary) / 0.6);
  border-radius: 8px;
  padding: 0.5rem 1.25rem;
  font-size: 1rem;
  font-family: var(--font-mono);
  font-weight: 800;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275);
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}

.cli-chip:hover {
  background: hsl(var(--primary) / 0.35);
  border-color: hsl(var(--primary));
  transform: translateY(-3px);
  box-shadow: 0 6px 16px rgba(0,0,0,0.3);
}

.terminal-icon {
  color: hsl(var(--primary));
}

.btn-clear {
  background: transparent;
  border: none;
  color: hsl(var(--muted-foreground));
  cursor: pointer;
  padding: 0.25rem;
  border-radius: 0.25rem;
  transition: color 0.15s, background-color 0.15s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-clear:hover {
  background: hsl(var(--muted));
  color: hsl(var(--foreground));
}

.terminal-body {
  padding: 1rem;
  height: 75vh;
  min-height: 500px;
  overflow-y: auto;
  overflow-x: auto;
  font-family: var(--font-mono);
  font-size: 0.85rem;
  line-height: 1.5;
  background: transparent; /* inherits from card */
}

/* Custom Scrollbar for Terminal */
.terminal-body::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}
.terminal-body::-webkit-scrollbar-track {
  background: transparent;
}
.terminal-body::-webkit-scrollbar-thumb {
  background: hsl(var(--muted));
  border-radius: 4px;
}

.cli-line {
  margin-bottom: 0.5rem;
}

.cli-line pre {
  margin: 0;
  font-family: inherit;
  white-space: pre;
}

.cli-input { color: hsl(var(--foreground)); font-weight: 600; }
.cli-output { color: hsl(var(--muted-foreground)); }
.cli-error { color: hsl(var(--destructive)); }
.cli-system { color: hsl(var(--primary)); opacity: 0.8; font-style: italic; }

.terminal-input-form {
  display: flex;
  align-items: center;
  padding: 0.75rem 1rem;
  background: transparent;
  border-top: 1px solid hsl(var(--border) / 0.3);
}

.prompt {
  color: hsl(var(--teal));
  font-family: var(--font-mono);
  font-weight: 700;
  margin-right: 0.75rem;
  user-select: none;
}

.terminal-input-form input {
  flex-grow: 1;
  background: transparent;
  border: none;
  color: hsl(var(--foreground));
  font-family: var(--font-mono);
  font-size: 0.9rem;
  outline: none;
}

.terminal-input-form input:focus {
  outline: none;
}

.terminal-input-form input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.cursor-blink {
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.chip-destructive {
  color: hsl(var(--destructive));
  border-color: hsl(var(--destructive) / 0.6);
  background: hsl(var(--destructive) / 0.1);
}

.chip-destructive:hover {
  background: hsl(var(--destructive) / 0.2);
  border-color: hsl(var(--destructive));
  box-shadow: 0 6px 16px hsl(var(--destructive) / 0.3);
}

/* Modal & Glassmorphism Properties */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: hsl(var(--background) / 0.5);
}

.glass-panel {
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.modal-content {
  background: hsl(var(--card));
  border: 1px solid hsl(var(--border) / 0.7);
  border-radius: var(--radius);
  box-shadow: 0 20px 50px rgba(0,0,0,0.5);
  width: 90%;
  max-width: 500px;
  overflow: hidden;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem;
  border-bottom: 1px solid hsl(var(--border) / 0.5);
}

.modal-header h2 {
  font-size: 1.25rem;
  font-weight: 600;
  margin: 0;
}

.btn-close {
  background: transparent;
  border: none;
  color: hsl(var(--muted-foreground));
  cursor: pointer;
  padding: 0.25rem;
  border-radius: 4px;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-close:hover {
  background: hsl(var(--muted));
  color: hsl(var(--foreground));
}

.modal-body {
  padding: 1.5rem;
}

.detail-grid {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  background: hsl(var(--muted) / 0.3);
  border: 1px solid hsl(var(--border) / 0.5);
  border-radius: var(--radius);
}

.detail-label {
  font-weight: 600;
  color: hsl(var(--foreground));
  text-transform: capitalize;
}

.legend-row {
  display: flex;
  align-items: center;
  font-size: 1.05rem;
}

.legend-text strong {
  color: hsl(var(--foreground));
  font-family: var(--font-mono);
  margin-right: 0.25rem;
}

.interactive-card {
  cursor: pointer;
  background: hsl(var(--card));
  border: 1px solid hsl(var(--border));
  text-align: left;
  transition: all 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275);
  padding: 1.5rem;
  border-radius: var(--radius);
}

.interactive-card:hover {
  transform: translateY(-2px);
  border-color: hsl(var(--primary) / 0.5);
}

.interactive-card:active {
  transform: scale(0.98);
  box-shadow: 0 0 15px hsl(var(--primary) / 0.3);
}

.animate-zoom-in {
  animation: zoom-in 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

@keyframes zoom-in {
  0% { transform: scale(0.95); opacity: 0; }
  100% { transform: scale(1); opacity: 1; }
}

.mono-code {
  font-family: var(--font-mono);
  background: hsl(var(--muted));
  padding: 0.1rem 0.3rem;
  border-radius: 4px;
}

.mb-3 { margin-bottom: 0.75rem; }
</style>
