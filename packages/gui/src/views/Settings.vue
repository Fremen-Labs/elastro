<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { state } from '../store'
import axios from 'axios'

const apiBase = import.meta.env.VITE_API_URL || ''
const error = ref<string | null>(null)
const successMsg = ref<string | null>(null)
const isLoading = ref(false)

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
    const res = await axios.get(`${apiBase}/api/config`, {
      headers: { Authorization: `Bearer ${state.token}` }
    })
    // For simplicity, we just list them here. Real app would populate a table.
    state.clusters = res.data.clusters || []
  } catch (err: any) {
    error.value = "Failed to load configuration."
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

    <div class="settings-grid">
      <!-- Add New Cluster Form -->
      <div class="card form-card">
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

      <!-- Managed Clusters List -->
      <div class="card list-card">
        <h3>Managed Configurations</h3>
        <p class="text-sm text-muted">Clusters currently configured in ~/.elastro/config</p>
        
        <div v-if="isLoading && state.clusters.length === 0" class="loader mt-4">Loading...</div>
        
        <ul class="cluster-list mt-4" v-else-if="state.clusters.length > 0">
          <li v-for="cluster in state.clusters" :key="cluster.name" class="cluster-list-item">
            <div class="cluster-info">
              <strong>{{ cluster.name }}</strong>
              <span class="host-url">{{ cluster.host }}</span>
            </div>
            <button class="btn btn-outline btn-sm">Edit</button>
          </li>
        </ul>
        
        <div v-else class="empty-list mt-4">
          No clusters configured yet.
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

.settings-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 2rem;
  align-items: start;
}

@media (max-width: 1024px) {
  .settings-grid {
    grid-template-columns: 1fr;
  }
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

.cluster-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.cluster-list-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  background: hsl(var(--background));
  border: 1px solid hsl(var(--border));
  border-radius: var(--radius);
}

.cluster-info {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.host-url {
  font-size: 0.85rem;
  color: hsl(var(--muted-foreground));
}

.empty-list {
  color: hsl(var(--muted-foreground));
  font-style: italic;
  padding: 2rem 0;
  text-align: center;
}

.mt-4 {
  margin-top: 1rem;
}
</style>
