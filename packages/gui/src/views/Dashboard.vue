<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { state } from '../store'
import axios from 'axios'

const apiBase = import.meta.env.VITE_API_URL || ''
const error = ref<string | null>(null)

const fetchClusters = async () => {
  if (!state.token) return
  
  state.loadingClusters = true
  error.value = null
  
  try {
    const res = await axios.get(`${apiBase}/api/clusters`, {
      headers: { Authorization: `Bearer ${state.token}` }
    })
    state.clusters = res.data.clusters
  } catch (err: any) {
    if (err.response?.status === 401) {
       error.value = "Unauthorized: Invalid or missing security token."
    } else {
       error.value = "Failed to fetch cluster data. Is the Python backend running?"
    }
  } finally {
    state.loadingClusters = false
  }
}

onMounted(() => {
  if (state.token) {
    fetchClusters()
  } else {
    // Check interval until token is injected by App.vue onMount
    const checkToken = setInterval(() => {
      if (state.token) {
        clearInterval(checkToken)
        fetchClusters()
      }
    }, 100)
  }
})

// Helper to determine index health color
const getHealthColor = (health: string) => {
  switch(health) {
    case 'green': return 'hsl(var(--teal))'
    case 'yellow': return 'hsl(var(--secondary))' // Reusing a warning-ish color
    case 'red': return 'hsl(var(--destructive))'
    default: return 'hsl(var(--muted-foreground))'
  }
}
</script>

<template>
  <div class="dashboard animate-fade-in">
    <header class="page-header">
      <h1>Dashboard</h1>
      <p>Overview of managed Elasticsearch clusters.</p>
    </header>

    <div v-if="error" class="error-banner">
      <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/></svg>
      {{ error }}
    </div>

    <!-- Summary Statistics -->
    <div class="stats-grid" v-if="state.loadingClusters || state.clusters.length > 0">
      <div class="card stat-card">
        <h3>Total Clusters</h3>
        <div v-if="state.loadingClusters" class="skeleton skeleton-text skeleton-jumbo w-12 mt-2"></div>
        <div v-else class="value">{{ state.clusters.length }}</div>
      </div>
      <div class="card stat-card">
        <h3>Unstable Indices</h3>
        <div v-if="state.loadingClusters" class="skeleton skeleton-text skeleton-jumbo w-12 mt-2"></div>
        <div v-else class="value text-destructive">
          {{ state.clusters.reduce((acc, c) => acc + (c.unstable_indices || []).length, 0) }}
        </div>
      </div>
    </div>

    <!-- Skeleton Loading State -->
    <div v-if="state.loadingClusters" class="clusters-container">
      <div v-for="i in 3" :key="i" class="card cluster-card">
        <div class="cluster-header" style="padding-bottom: 0; border-bottom: none;">
          <div class="skeleton skeleton-text skeleton-title w-1/3" style="margin-bottom: 0;"></div>
          <div class="skeleton skeleton-badge w-16"></div>
        </div>
        <div class="cluster-details" style="margin-bottom: 0px; margin-top: 1rem;">
          <div class="skeleton skeleton-text w-1/4" style="margin-bottom: 0;"></div>
          <div class="skeleton skeleton-text w-1/4" style="margin-bottom: 0;"></div>
        </div>
      </div>
    </div>

    <!-- Cluster Lists -->
    <div class="clusters-container" v-else-if="state.clusters.length > 0">
      <div v-for="cluster in state.clusters" :key="cluster.name" class="card cluster-card">
        
        <router-link :to="`/cluster/${encodeURIComponent(cluster.name)}`" class="cluster-link-wrapper">
          <div class="cluster-header hover-effect">
            <h2>{{ cluster.name }} <svg class="chevron" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg></h2>
            <span class="health-badge" :style="{ backgroundColor: getHealthColor(cluster.health) }">
              {{ cluster.health }}
            </span>
          </div>
          
          <div class="cluster-details">
            <p><strong>Host:</strong> {{ cluster.host }}</p>
            <p><strong>Total Indices:</strong> {{ cluster.index_count }}</p>
          </div>
        </router-link>

        <div class="unstable-indices" v-if="cluster.unstable_indices?.length > 0">
          <h4>Alerts (Unstable Indices)</h4>
          <table class="indices-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Health</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="idx in cluster.unstable_indices" :key="idx.index">
                <td>{{ idx.index }}</td>
                <td>
                   <span class="health-dot" :style="{ backgroundColor: getHealthColor(idx.health) }"></span>
                   {{ idx.health }}
                </td>
                <td>{{ idx.status }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div v-else-if="!state.loadingClusters && !error" class="empty-state card">
      <div class="empty-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
      </div>
      <h2>No Clusters Managed</h2>
      <p>You haven't added any Elasticsearch clusters yet.</p>
      <router-link to="/settings" class="btn btn-primary mt-4">Add Cluster</router-link>
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

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1.5rem;
  margin-bottom: 2rem;
}

.stat-card {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.stat-card h3 {
  font-size: 0.875rem;
  font-weight: 500;
  color: hsl(var(--muted-foreground));
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.stat-card .value {
  font-size: 2.5rem;
  font-weight: 700;
}

.text-destructive {
  color: hsl(var(--destructive));
}

.cluster-card {
  margin-bottom: 1.5rem;
}

.cluster-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.25rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid hsl(var(--border) / 0.5);
}

.cluster-header h2 {
  font-size: 1.25rem;
  font-weight: 600;
}

.health-badge {
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 700;
  color: white;
  text-transform: uppercase;
}

.cluster-details {
  display: flex;
  gap: 2rem;
  margin-bottom: 1.5rem;
  font-size: 0.95rem;
}

.cluster-details a {
  color: hsl(var(--primary));
  text-decoration: none;
}

.unstable-indices h4 {
  font-size: 0.95rem;
  font-weight: 600;
  margin-bottom: 0.75rem;
  color: hsl(var(--destructive));
}

.indices-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.indices-table th {
  text-align: left;
  padding: 0.75rem;
  background: hsl(var(--muted) / 0.5);
  font-weight: 500;
  color: hsl(var(--muted-foreground));
  border-bottom: 1px solid hsl(var(--border));
}

.indices-table td {
  padding: 0.75rem;
  border-bottom: 1px solid hsl(var(--border) / 0.5);
}

.health-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 0.5rem;
}

.error-banner {
  background: hsl(var(--destructive) / 0.1);
  color: hsl(var(--destructive));
  padding: 1rem;
  border-radius: var(--radius);
  margin-bottom: 2rem;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-weight: 500;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem 2rem;
  text-align: center;
}

.empty-icon {
  color: hsl(var(--muted-foreground));
  margin-bottom: 1rem;
  opacity: 0.5;
}

.empty-state h2 {
  font-size: 1.25rem;
  margin-bottom: 0.5rem;
}

.empty-state p {
  color: hsl(var(--muted-foreground));
}

.mt-4 {
  margin-top: 1rem;
}
</style>
