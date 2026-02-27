<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { state } from '../store'
import axios from 'axios'

const apiBase = import.meta.env.VITE_API_URL || ''
const error = ref<string | null>(null)
const successMsg = ref<string | null>(null)
const isLoading = ref(false)

const activeTab = ref('manage')

const clusterForm = ref({
  name: '',
  host: '',
  username: '',
  password: '',
  api_key: ''
})

const authMethod = ref('basic') // 'basic' or 'api_key'

const fetchConfig = async () => {
  if (!state.token) return
  isLoading.value = true
  try {
    const res = await axios.get(`${apiBase}/api/clusters`, {
      headers: { Authorization: `Bearer ${state.token}` }
    })
    state.clusters = res.data.clusters || []
  } catch (err: any) {
    error.value = "Failed to load cluster details."
  } finally {
    isLoading.value = false
  }
}

const saveCluster = async () => {
  if (!state.token) return
  
  error.value = null
  successMsg.value = null
  isLoading.value = true
  
  try {
    const payload: any = {
      name: clusterForm.value.name,
      host: clusterForm.value.host,
    }
    
    if (authMethod.value === 'basic') {
      payload.auth = {
        username: clusterForm.value.username,
        password: clusterForm.value.password
      }
    } else {
      payload.auth = {
        api_key: clusterForm.value.api_key
      }
    }

    await axios.post(`${apiBase}/api/config/clusters`, payload, {
      headers: { Authorization: `Bearer ${state.token}` }
    })
    
    successMsg.value = `Cluster '${clusterForm.value.name}' added successfully.`
    clusterForm.value = { name: '', host: '', username: '', password: '', api_key: '' }
    fetchConfig()
    
    // Switch to manage tab smoothly after saving
    activeTab.value = 'manage'
    
  } catch (err: any) {
    error.value = err.response?.data?.detail || "Failed to save cluster configuration."
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
  // Wait for token
  const checkToken = setInterval(() => {
    if (state.token) {
      clearInterval(checkToken)
      fetchConfig()
    }
  }, 100)
})
</script>

<template>
  <div class="settings animate-fade-in">
    <header class="page-header">
      <h1>Settings</h1>
      <p>Manage your local Elastro configuration and connected clusters.</p>
    </header>

    <div v-if="error" class="alert error-banner animate-fade-in">
      {{ error }}
    </div>
    <div v-if="successMsg" class="alert success-banner animate-fade-in">
      {{ successMsg }}
    </div>

    <div class="tabs-container">
      <div class="tabs">
        <button 
          class="tab-btn" 
          :class="{ active: activeTab === 'manage' }" 
          @click="activeTab = 'manage'">
          Managed Clusters
        </button>
        <button 
          class="tab-btn" 
          :class="{ active: activeTab === 'add' }" 
          @click="activeTab = 'add'">
          Add Cluster
        </button>
      </div>

      <div class="tab-content" v-if="activeTab === 'manage'">
        <!-- Managed Clusters Grid -->
        <div class="animate-fade-in">
          <div class="flex-header">
             <h3>Managed Clusters</h3>
             <p class="text-sm text-muted">A dynamic overview of your connected environments.</p>
          </div>
          
          <div v-if="isLoading && state.clusters.length === 0" class="loader mt-4">Pinging clusters...</div>
          
          <div class="clusters-grid mt-4" v-else-if="state.clusters.length > 0">
            <div v-for="cluster in state.clusters" :key="cluster.name" class="card cluster-grid-card">
              <div class="card-top">
                <div class="cluster-name-block">
                  <strong>{{ cluster.name }}</strong>
                  <span class="host-url">{{ cluster.host }}</span>
                </div>
                <div class="health-chip" :class="'health-' + (cluster.health || 'offline')">
                   <div class="chip-dot"></div>
                   {{ cluster.health || 'offline' }}
                </div>
              </div>
              
              <div class="card-stats">
                <div class="stat-small">
                  <span class="stat-label">Indices</span>
                  <span class="stat-val">{{ cluster.index_count !== undefined ? cluster.index_count : 'N/A' }}</span>
                </div>
                <div class="stat-small">
                  <span class="stat-label">Largest Index</span>
                  <span class="stat-val" v-if="cluster.largest_index">{{ cluster.largest_index.name }} ({{ cluster.largest_index.size }})</span>
                  <span class="stat-val" v-else>N/A</span>
                </div>
              </div>
              
              <div class="card-actions">
                 <button class="btn btn-outline btn-sm" style="width: 100%;">Map Connection</button>
              </div>
            </div>
          </div>
          
          <div v-else class="empty-list mt-4 card">
            No clusters configured yet.
          </div>
        </div>
      </div>

      <div class="tab-content" v-if="activeTab === 'add'">
        <!-- Add New Cluster Form -->
        <div class="card form-card animate-fade-in">
          <h3>Add Elasticsearch Cluster</h3>
          <p class="text-sm text-muted">Configure a new cluster. Secrets are saved locally to ~/.elastro/config.</p>
          
          <form @submit.prevent="saveCluster" class="cluster-form">
            <div class="form-group">
              <label>Cluster Name</label>
              <input v-model="clusterForm.name" type="text" placeholder="e.g. Production Cluster" required />
            </div>
            
            <div class="form-group">
              <label>Host URL</label>
              <input v-model="clusterForm.host" type="url" placeholder="https://elastic:9200" required />
            </div>

            <div class="form-group">
              <label>Authentication Method</label>
              <div class="radio-group">
                <label class="radio-label">
                  <input type="radio" v-model="authMethod" value="basic" /> Basic Auth
                </label>
                <label class="radio-label">
                  <input type="radio" v-model="authMethod" value="api_key" /> API Key
                </label>
              </div>
            </div>

            <template v-if="authMethod === 'basic'">
              <div class="form-row">
                <div class="form-group">
                  <label>Username</label>
                  <input v-model="clusterForm.username" type="text" placeholder="elastic" />
                </div>
                <div class="form-group">
                  <label>Password</label>
                  <input v-model="clusterForm.password" type="password" placeholder="••••••••" />
                </div>
              </div>
            </template>

            <template v-if="authMethod === 'api_key'">
              <div class="form-group">
                <label>API Key</label>
                <input v-model="clusterForm.api_key" type="password" placeholder="Base64 Encoded API Key" />
              </div>
            </template>

            <button type="submit" class="btn btn-primary submit-btn" :disabled="isLoading">
              {{ isLoading ? 'Saving...' : 'Save Cluster' }}
            </button>
          </form>
        </div>
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

.tabs-container {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.tabs {
  display: flex;
  gap: 0.5rem;
  border-bottom: 1px solid hsl(var(--border) / 0.5);
  padding-bottom: 0;
  margin-bottom: 0.5rem;
}

.tab-btn {
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  padding: 0.75rem 1.5rem;
  font-size: 1rem;
  font-weight: 500;
  color: hsl(var(--muted-foreground));
  cursor: pointer;
  transition: all 0.2s ease;
  margin-bottom: -1px;
}

.tab-btn:hover {
  color: hsl(var(--foreground));
  background: hsl(var(--muted) / 0.5);
  border-top-left-radius: var(--radius);
  border-top-right-radius: var(--radius);
}

.tab-btn.active {
  color: hsl(var(--primary));
  border-bottom: 2px solid hsl(var(--primary));
  background: transparent;
}

.tab-content {
  width: 100%;
  max-width: 800px;
}

.card h3 {
  font-size: 1.25rem;
  font-weight: 600;
  margin-bottom: 0.25rem;
}

.text-muted {
  color: hsl(var(--muted-foreground));
  margin-bottom: 1.5rem;
}

.text-sm {
  font-size: 0.875rem;
}

.cluster-form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

label {
  font-size: 0.875rem;
  font-weight: 500;
  color: hsl(var(--foreground));
}

.radio-group {
  display: flex;
  gap: 1.5rem;
  padding: 0.5rem 0;
}

.radio-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 400;
  cursor: pointer;
}

.submit-btn {
  margin-top: 0.5rem;
  align-self: flex-start;
}

.alert {
  padding: 1rem;
  border-radius: var(--radius);
  margin-bottom: 1.5rem;
  font-weight: 500;
}

.error-banner {
  background: hsl(var(--destructive) / 0.1);
  color: hsl(var(--destructive));
  border: 1px solid hsl(var(--destructive) / 0.2);
}

.success-banner {
  background: hsl(var(--teal) / 0.1);
  color: hsl(var(--teal));
  border: 1px solid hsl(var(--teal) / 0.2);
}

/* Clusters Grid Styles */
.flex-header {
  margin-bottom: 1.5rem;
}

.clusters-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 1.5rem;
  width: 100%;
}

.cluster-grid-card {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  height: 100%;
}

.card-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  border-bottom: 1px solid hsl(var(--border) / 0.5);
  padding-bottom: 1rem;
}

.cluster-name-block strong {
  display: block;
  font-size: 1.15rem;
  font-weight: 600;
  margin-bottom: 0.1rem;
}

.host-url {
  font-size: 0.85rem;
  color: hsl(var(--muted-foreground));
}

.health-chip {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  background: hsl(var(--muted) / 0.3);
  color: hsl(var(--muted-foreground));
}

.chip-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.health-green { 
  background: hsl(var(--teal) / 0.15); 
  color: hsl(var(--teal)); 
}
.health-yellow { 
  background: hsl(var(--secondary) / 0.15); 
  color: hsl(var(--secondary)); 
}
.health-red { 
  background: hsl(var(--destructive) / 0.15); 
  color: hsl(var(--destructive)); 
}

.card-stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin-bottom: 0.5rem;
}

.stat-small {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.stat-label {
  font-size: 0.75rem;
  color: hsl(var(--muted-foreground));
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 600;
}

.stat-val {
  font-size: 0.95rem;
  font-weight: 500;
  word-break: break-all;
  color: hsl(var(--foreground));
}

.card-actions {
  margin-top: auto;
  padding-top: 0.5rem;
}

.empty-list {
  color: hsl(var(--muted-foreground));
  font-style: italic;
  padding: 3rem 0;
  text-align: center;
}

.mt-4 {
  margin-top: 1rem;
}
</style>
