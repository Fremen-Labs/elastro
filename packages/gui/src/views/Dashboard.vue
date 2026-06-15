<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Shield } from 'lucide-vue-next'
import { state } from '../store'
import axios from 'axios'
import PageHeader from '../components/ui/PageHeader.vue'
import StatusBadge from '../components/ui/StatusBadge.vue'
import AlertBanner from '../components/ui/AlertBanner.vue'
import EmptyState from '../components/ui/EmptyState.vue'
import { healthColor } from '../utils/health'

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
      error.value = 'Unauthorized: Invalid or missing security token.'
    } else {
      error.value = 'Failed to fetch cluster data. Is the Python backend running?'
    }
  } finally {
    state.loadingClusters = false
  }
}

onMounted(() => {
  if (state.token) {
    fetchClusters()
  } else {
    const checkToken = setInterval(() => {
      if (state.token) {
        clearInterval(checkToken)
        fetchClusters()
      }
    }, 100)
  }
})

const unstableCount = () =>
  state.clusters.reduce((acc, c) => acc + (c.unstable_indices || []).length, 0)
</script>

<template>
  <div class="dashboard animate-fade-in">
    <PageHeader
      eyebrow="Overview"
      title="Dashboard"
      description="Overview of managed Elasticsearch clusters."
    />

    <AlertBanner v-if="error" variant="error">{{ error }}</AlertBanner>

    <div v-if="state.loadingClusters || state.clusters.length > 0" class="stats-grid">
      <div class="card stat-card">
        <h3 class="label-caps">Total Clusters</h3>
        <div v-if="state.loadingClusters" class="skeleton skeleton-text skeleton-jumbo w-12 mt-2"></div>
        <div v-else class="stat-value">{{ state.clusters.length }}</div>
      </div>
      <div class="card stat-card">
        <h3 class="label-caps">Unstable Indices</h3>
        <div v-if="state.loadingClusters" class="skeleton skeleton-text skeleton-jumbo w-12 mt-2"></div>
        <div v-else class="stat-value text-destructive">{{ unstableCount() }}</div>
      </div>
    </div>

    <div v-if="state.loadingClusters" class="clusters-container">
      <div v-for="i in 3" :key="i" class="card cluster-card">
        <div class="cluster-header skeleton-header">
          <div class="skeleton skeleton-text skeleton-title w-1/3" style="margin-bottom: 0;"></div>
          <div class="skeleton skeleton-badge w-16"></div>
        </div>
        <div class="cluster-details" style="margin-top: 1rem;">
          <div class="skeleton skeleton-text w-1/4" style="margin-bottom: 0.5rem;"></div>
          <div class="skeleton skeleton-text w-1/4" style="margin-bottom: 0;"></div>
        </div>
      </div>
    </div>

    <div v-else-if="state.clusters.length > 0" class="clusters-container">
      <router-link
        v-for="cluster in state.clusters"
        :key="cluster.name"
        :to="`/cluster/${encodeURIComponent(cluster.name)}`"
        class="card cluster-card cluster-link"
      >
        <div class="cluster-header">
          <h2>
            {{ cluster.name }}
            <svg class="chevron" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
          </h2>
          <StatusBadge :status="cluster.health" />
        </div>

        <div class="cluster-details">
          <div class="info-block">
            <p><span class="label-caps info-label">Host</span> <span class="value-chip">{{ cluster.host }}</span></p>
            <p><span class="label-caps info-label">Indices</span> <span class="value-chip">{{ cluster.index_count }}</span></p>
          </div>
        </div>

        <div v-if="cluster.unstable_indices?.length > 0" class="unstable-indices">
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
                  <span class="health-dot" :style="{ backgroundColor: healthColor(idx.health) }"></span>
                  <span :class="{ 'text-destructive': idx.health === 'red' }">{{ idx.health }}</span>
                </td>
                <td>{{ idx.status }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </router-link>
    </div>

    <EmptyState
      v-else-if="!state.loadingClusters && !error"
      title="No Clusters Managed"
      description="You haven't added any Elasticsearch clusters yet."
    >
      <template #icon>
        <Shield :size="48" />
      </template>
      <template #actions>
        <router-link to="/settings" class="btn btn-primary">Add Cluster</router-link>
      </template>
    </EmptyState>
  </div>
</template>

<style scoped>
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
  color: hsl(var(--muted-foreground));
}

.stat-value {
  font-size: 2.5rem;
  font-weight: 700;
  line-height: 1;
}

.clusters-container {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.cluster-card {
  margin-bottom: 0;
}

.cluster-link {
  display: block;
  text-decoration: none;
  color: inherit;
}

.cluster-link:hover {
  transform: translateY(-2px);
  border-color: hsl(var(--ring) / 0.5);
}

.cluster-link:focus-visible {
  outline: 2px solid hsl(var(--ring));
  outline-offset: 2px;
}

.cluster-link:active {
  transform: scale(0.995);
}

.cluster-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.25rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid hsl(var(--border) / 0.5);
}

.skeleton-header {
  border-bottom: none;
  padding-bottom: 0;
  margin-bottom: 0;
}

.cluster-header h2 {
  font-size: 1.25rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.chevron {
  opacity: 0;
  transform: translateX(-8px);
  transition: opacity 0.2s ease, transform 0.2s ease;
  color: hsl(var(--primary));
}

.cluster-link:hover .chevron {
  opacity: 1;
  transform: translateX(0);
}

.cluster-details {
  margin-bottom: 0.5rem;
}

.info-block {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.info-block p {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.info-label {
  color: hsl(var(--muted-foreground));
  min-width: 4.5rem;
}

.unstable-indices {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid hsl(var(--border) / 0.5);
}

.unstable-indices h4 {
  font-size: 0.9rem;
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
  vertical-align: middle;
}
</style>