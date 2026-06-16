<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import axios from 'axios'
import { ChevronDown, RefreshCw, Wrench } from 'lucide-vue-next'
import FindingDetailPanel from './FindingDetailPanel.vue'
import { state } from '../../store'
import PageHeader from '../ui/PageHeader.vue'
import AlertBanner from '../ui/AlertBanner.vue'
import HealthScore from './HealthScore.vue'
import type {
  ClusterInventorySummary,
  HealthAssessment,
  HealthFinding,
  NodeHealthSummary,
} from '../../types/health'
import { severityClass } from '../../types/health'

const props = defineProps<{
  clusterName: string
}>()

const apiBase = import.meta.env.VITE_API_URL || ''
const loading = ref(false)
const assessing = ref(false)
const hasLoaded = ref(false)
const error = ref<string | null>(null)
const assessment = ref<HealthAssessment | null>(null)
const trendPoints = ref<number[]>([])
const trendDelta = ref<number | null>(null)
const nodes = ref<NodeHealthSummary[]>([])
const clusterSummary = ref<ClusterInventorySummary | null>(null)
const summaryLoading = ref(false)
const activeFix = ref<string | null>(null)
const expandedFindings = ref<Record<string, boolean>>({})
const awaitingToken = ref(false)

const authHeaders = () => ({ Authorization: `Bearer ${state.token}` })

const openFindings = computed((): HealthFinding[] => {
  const findings = assessment.value?.findings
  if (!Array.isArray(findings)) return []
  return findings.filter((f) => f.status !== 'pass' && f.status !== 'skipped')
})

const displayScore = computed(() => {
  if (!hasLoaded.value || !assessment.value) return null
  const score = assessment.value.overall_score
  return Number.isFinite(score) ? score : null
})

const isBusy = computed(() => loading.value || assessing.value || awaitingToken.value)

const clusterLabel = computed(() => props.clusterName || 'cluster')

const formatCount = (value: number | null | undefined): string => {
  if (value == null || !Number.isFinite(value)) return '—'
  return new Intl.NumberFormat().format(value)
}

const inventoryRows = computed(() => {
  const summary = clusterSummary.value
  if (!summary) return []

  const indexDetail =
    summary.indices.yellow > 0 || summary.indices.red > 0
      ? `${summary.indices.green}G / ${summary.indices.yellow}Y / ${summary.indices.red}R`
      : undefined

  const shardDetail =
    summary.shards.unassigned > 0
      ? `${summary.shards.unassigned} unassigned`
      : undefined

  const rows: Array<{ label: string; value: string; detail?: string; warn?: boolean }> = [
    { label: 'Cluster status', value: summary.health.toUpperCase() },
    { label: 'Nodes', value: formatCount(summary.nodes.total) },
    {
      label: 'Indices',
      value: formatCount(summary.indices.total),
      detail: indexDetail,
      warn: summary.indices.red > 0 || summary.indices.yellow > 0,
    },
    {
      label: 'Shards',
      value: formatCount(summary.shards.total),
      detail: shardDetail,
      warn: summary.shards.unassigned > 0,
    },
    { label: 'Data streams', value: formatCount(summary.data_streams.total) },
    { label: 'ILM policies', value: formatCount(summary.ilm.policy_count) },
    { label: 'Index templates', value: formatCount(summary.index_templates.total) },
    {
      label: 'Dashboards',
      value: summary.kibana.available ? formatCount(summary.kibana.dashboards ?? 0) : '—',
      detail: summary.kibana.available ? 'from .kibana* indices' : 'no Kibana indices',
    },
    { label: 'Documents', value: formatCount(summary.documents.total) },
    { label: 'Store size', value: summary.storage.total_human || '—' },
    {
      label: 'Snapshots',
      value: summary.backups.configured
        ? `${summary.backups.repository_count} repo(s)`
        : 'Not configured',
      warn: !summary.backups.configured,
    },
  ]

  if (hasLoaded.value) {
    rows.push({
      label: 'Open findings',
      value: formatCount(openFindings.value.length),
      warn: openFindings.value.length > 0,
    })
  }

  return rows
})

const isHtmlResponse = (data: unknown): boolean =>
  typeof data === 'string' && data.trim().toLowerCase().startsWith('<!doctype html')

const coercePayload = (data: unknown): Record<string, unknown> | null => {
  if (data == null) return null
  if (typeof data === 'string') {
    const trimmed = data.trim()
    if (!trimmed || isHtmlResponse(trimmed)) return null
    try {
      const parsed = JSON.parse(trimmed)
      return typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)
        ? (parsed as Record<string, unknown>)
        : null
    } catch {
      return null
    }
  }
  if (typeof data === 'object' && !Array.isArray(data)) {
    return data as Record<string, unknown>
  }
  return null
}

const toAssessment = (raw: Record<string, unknown> | null): HealthAssessment | null => {
  if (!raw) return null

  const nested = raw.report
  const source =
    typeof nested === 'object' && nested !== null && !Array.isArray(nested)
      ? (nested as Record<string, unknown>)
      : raw

  if (!('overall_score' in source)) return null

  const score = Number(source.overall_score)
  if (!Number.isFinite(score)) return null

  return {
    session_id: String(source.session_id ?? ''),
    cluster_name: String(source.cluster_name ?? props.clusterName),
    elasticsearch_version: String(source.elasticsearch_version ?? 'unknown'),
    assessed_at: String(source.assessed_at ?? new Date().toISOString()),
    duration_ms: Number(source.duration_ms ?? 0),
    overall_score: score,
    overall_status: (source.overall_status as HealthAssessment['overall_status']) ?? 'unknown',
    findings: Array.isArray(source.findings) ? (source.findings as HealthFinding[]) : [],
    collectors_run: Array.isArray(source.collectors_run) ? (source.collectors_run as string[]) : [],
    collectors_failed: Array.isArray(source.collectors_failed)
      ? (source.collectors_failed as string[])
      : [],
  }
}

const sparkline = computed(() => {
  if (!trendPoints.value.length) return ''
  const blocks = '▁▂▃▄▅▆▇█'
  const scores = trendPoints.value
  const low = Math.min(...scores)
  const high = Math.max(...scores)
  const midBlock = blocks.charAt(4) || blocks.charAt(0)
  if (low === high) return midBlock.repeat(scores.length)
  return scores
    .map((score) => {
      const normalized = (score - low) / (high - low)
      const index = Math.min(blocks.length - 1, Math.round(normalized * (blocks.length - 1)))
      return blocks.charAt(index) || midBlock
    })
    .join('')
})

const fetchClusterSummary = async () => {
  if (!state.token || !props.clusterName) return
  summaryLoading.value = true
  try {
    const res = await axios.get(
      `${apiBase}/api/cluster/${encodeURIComponent(props.clusterName)}`,
      { headers: authHeaders(), timeout: 30000 }
    )
    clusterSummary.value = res.data as ClusterInventorySummary
  } catch {
    clusterSummary.value = null
  } finally {
    summaryLoading.value = false
  }
}

const fetchTrends = async () => {
  if (!state.token || !props.clusterName) return
  try {
    const res = await axios.get(
      `${apiBase}/api/clusters/${encodeURIComponent(props.clusterName)}/health/trends`,
      { headers: authHeaders(), timeout: 30000, params: { window: '7d', limit: 30 } }
    )
    const points = Array.isArray(res.data?.points) ? res.data.points : []
    trendPoints.value = points
      .map((point: { overall_score?: number }) => Number(point?.overall_score))
      .filter((score: number) => Number.isFinite(score))
    const delta = res.data?.score_delta_7d
    trendDelta.value = typeof delta === 'number' && Number.isFinite(delta) ? delta : null
  } catch {
    trendPoints.value = []
    trendDelta.value = null
  }
}

const fetchNodes = async () => {
  if (!state.token || !props.clusterName) return
  try {
    const res = await axios.get(
      `${apiBase}/api/clusters/${encodeURIComponent(props.clusterName)}/health/nodes`,
      { headers: authHeaders(), timeout: 30000 }
    )
    nodes.value = Array.isArray(res.data?.nodes) ? res.data.nodes : []
  } catch {
    nodes.value = []
  }
}

const applyPayload = (raw: Record<string, unknown> | null): boolean => {
  const parsed = toAssessment(raw)
  if (!parsed) return false
  assessment.value = parsed
  hasLoaded.value = true
  return true
}

const loadFullAssessment = async () => {
  const res = await axios.get(
    `${apiBase}/api/clusters/${encodeURIComponent(props.clusterName)}/health/assess`,
    { headers: authHeaders(), timeout: 120000, responseType: 'json' }
  )
  return applyPayload(coercePayload(res.data))
}

const loadCachedSnapshot = async () => {
  const scoreRes = await axios.get(
    `${apiBase}/api/clusters/${encodeURIComponent(props.clusterName)}/health/score`,
    { headers: authHeaders(), timeout: 120000, responseType: 'json' }
  )

  const scorePayload = coercePayload(scoreRes.data)
  if (!scorePayload) return false

  let findings: HealthFinding[] = []
  try {
    const findingsRes = await axios.get(
      `${apiBase}/api/clusters/${encodeURIComponent(props.clusterName)}/health/findings`,
      { headers: authHeaders(), timeout: 30000, responseType: 'json' }
    )
    if (Array.isArray(findingsRes.data?.findings)) {
      findings = findingsRes.data.findings
    }
  } catch {
    return loadFullAssessment()
  }

  return applyPayload({ ...scorePayload, findings })
}

const loadAssessment = async (forceRefresh = false) => {
  if (!state.token) {
    awaitingToken.value = true
    return
  }
  awaitingToken.value = false

  if (!props.clusterName) {
    error.value = 'Cluster name is missing.'
    return
  }

  loading.value = true
  assessing.value = true
  error.value = null

  try {
    const ok = forceRefresh ? await loadFullAssessment() : await loadCachedSnapshot()
    if (!ok) {
      hasLoaded.value = false
      assessment.value = null
      error.value =
        'The GUI server is outdated or returned an invalid response. Stop it and run `elastro gui` again to launch a fresh server with health API support.'
      return
    }
    await Promise.all([fetchNodes(), fetchTrends(), fetchClusterSummary()])
  } catch (err: any) {
    hasLoaded.value = false
    assessment.value = null
    const detail = err.response?.data?.detail
    error.value =
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: { msg?: string }) => d.msg).join(', ')
          : err.message || 'Failed to run health assessment.'
  } finally {
    loading.value = false
    assessing.value = false
  }
}

const applyFix = async (
  finding: HealthFinding,
  action: string,
  indexName?: string,
  dryRun = false
) => {
  if (!state.token) return
  const key = `${finding.id}:${action}`
  activeFix.value = key
  try {
    const res = await axios.post(
      `${apiBase}/api/clusters/${encodeURIComponent(props.clusterName)}/health/fix`,
      {
        finding_id: finding.id,
        action,
        index_name: indexName,
        dry_run: dryRun,
      },
      { headers: authHeaders(), timeout: 60000 }
    )
    if (dryRun) {
      alert(`Dry run: ${res.data.planned_api_call || res.data.message}`)
    } else {
      await loadAssessment(true)
    }
  } catch (err: any) {
    const detail = err.response?.data?.detail
    alert(typeof detail === 'string' ? detail : 'Fix failed.')
  } finally {
    activeFix.value = null
  }
}

const hasExpandableDetail = (finding: HealthFinding): boolean =>
  Boolean(finding.detail || finding.metadata?.detail_sections)

const toggleFindingDetail = (findingId: string) => {
  expandedFindings.value = {
    ...expandedFindings.value,
    [findingId]: !expandedFindings.value[findingId],
  }
}

const suggestCatalogAction = (finding: HealthFinding): string | null => {
  const title = `${finding.title} ${finding.summary} ${finding.detail || ''}`.toLowerCase()
  if (title.includes('replica')) return 'reduce_replicas'
  if (title.includes('reroute') || title.includes('allocation failed')) return 'reroute_failed'
  if (title.includes('routing filter')) return 'clear_routing_filters'
  return null
}

const formatRoles = (roles: string[] | undefined) => (Array.isArray(roles) ? roles.join(', ') : '—')

const waitForTokenAndLoad = () => {
  hasLoaded.value = false
  assessment.value = null
  loading.value = true

  if (state.token) {
    loadAssessment(false)
    return
  }

  awaitingToken.value = true
  const interval = setInterval(() => {
    if (state.token) {
      clearInterval(interval)
      awaitingToken.value = false
      loadAssessment(false)
    }
  }, 100)
}

onMounted(waitForTokenAndLoad)

watch(
  () => props.clusterName,
  () => waitForTokenAndLoad()
)
</script>

<template>
  <div class="health-panel">
    <PageHeader
      title="Cluster Health"
      :description="`Weighted score and findings for ${clusterLabel}.`"
    >
      <template #actions>
        <button class="btn btn-primary" :disabled="isBusy" @click="loadAssessment(true)">
          <RefreshCw :size="16" :class="{ spinning: assessing }" />
          {{ assessing ? 'Assessing...' : 'Run Assessment' }}
        </button>
      </template>
    </PageHeader>

    <AlertBanner v-if="awaitingToken" variant="warning">
      Waiting for security token. Launch via <code>elastro gui</code> if this persists.
    </AlertBanner>

    <AlertBanner v-if="error" variant="error">{{ error }}</AlertBanner>

    <div class="health-layout">
      <div class="card health-summary-card">
        <div class="score-wrap">
          <HealthScore
            :score="displayScore"
            :status="hasLoaded ? assessment?.overall_status : undefined"
            :loading="isBusy"
          />
        </div>
        <div v-if="sparkline" class="health-trend">
          <span class="label-caps">7d Trend</span>
          <span class="sparkline" aria-hidden="true">{{ sparkline }}</span>
          <span v-if="trendDelta !== null" class="trend-delta">
            {{ trendDelta > 0 ? '+' : '' }}{{ trendDelta }}
          </span>
        </div>
        <div v-if="hasLoaded && assessment" class="health-meta">
          <h4 class="summary-heading">Assessment</h4>
          <p>
            <span class="label-caps">Version</span>
            <span class="value-chip">{{ assessment.elasticsearch_version }}</span>
          </p>
          <p v-if="assessment.assessed_at">
            <span class="label-caps">Assessed</span>
            <span class="value-chip">{{ new Date(assessment.assessed_at).toLocaleString() }}</span>
          </p>
          <p v-if="assessment.duration_ms">
            <span class="label-caps">Duration</span>
            <span class="value-chip">{{ assessment.duration_ms }}ms</span>
          </p>
        </div>

        <div class="health-meta inventory-meta">
          <h4 class="summary-heading">Cluster inventory</h4>
          <div v-if="summaryLoading" class="inventory-skeleton">
            <div v-for="i in 6" :key="i" class="skeleton skeleton-text w-full mb-2"></div>
          </div>
          <template v-else-if="clusterSummary">
            <div class="inventory-grid">
              <div
                v-for="row in inventoryRows"
                :key="row.label"
                class="inventory-row"
                :class="{ 'inventory-row--warn': row.warn }"
              >
                <span class="label-caps">{{ row.label }}</span>
                <div class="inventory-values">
                  <span class="value-chip">{{ row.value }}</span>
                  <span v-if="row.detail" class="inventory-detail">{{ row.detail }}</span>
                </div>
              </div>
            </div>
          </template>
          <p v-else class="text-muted inventory-empty">Cluster inventory unavailable.</p>
        </div>
      </div>

      <div class="card findings-card">
        <h3 class="section-title">Open Findings</h3>
        <div v-if="isBusy" class="findings-skeleton">
          <p class="loading-label text-muted">Running health assessment…</p>
          <div v-for="i in 3" :key="i" class="skeleton skeleton-text w-full mb-4"></div>
        </div>
        <div v-else-if="hasLoaded && openFindings.length === 0" class="empty-findings">
          <p>No open findings — cluster looks healthy.</p>
        </div>
        <div v-else-if="hasLoaded" class="findings-list">
          <article
            v-for="finding in openFindings"
            :key="finding.id"
            class="finding-row"
            :class="[severityClass(finding.severity), { expanded: expandedFindings[finding.id] }]"
          >
            <button
              v-if="hasExpandableDetail(finding)"
              type="button"
              class="finding-toggle"
              :aria-expanded="expandedFindings[finding.id] ? 'true' : 'false'"
              @click="toggleFindingDetail(finding.id)"
            >
              <div class="finding-header">
                <span class="finding-severity label-caps">{{ finding.severity }}</span>
                <span class="finding-status">{{ finding.status }}</span>
              </div>
              <div class="finding-title-row">
                <h4>{{ finding.title }}</h4>
                <ChevronDown
                  :size="16"
                  class="chevron"
                  :class="{ open: expandedFindings[finding.id] }"
                />
              </div>
              <p class="finding-summary">{{ finding.summary }}</p>
            </button>
            <template v-else>
              <div class="finding-header">
                <span class="finding-severity label-caps">{{ finding.severity }}</span>
                <span class="finding-status">{{ finding.status }}</span>
              </div>
              <h4>{{ finding.title }}</h4>
              <p class="finding-summary">{{ finding.summary }}</p>
            </template>
            <FindingDetailPanel
              v-if="hasExpandableDetail(finding) && expandedFindings[finding.id]"
              :finding="finding"
            />
            <p v-if="finding.detail" class="finding-detail text-muted">{{ finding.detail }}</p>
            <p v-if="finding.remediation" class="finding-action text-muted">
              <Wrench :size="14" />
              {{ finding.remediation.label || finding.remediation.command }}
            </p>
            <div
              v-if="suggestCatalogAction(finding) && finding.affected_resources?.length"
              class="finding-fixes"
            >
              <button
                class="btn btn-secondary btn-sm"
                :disabled="activeFix === `${finding.id}:${suggestCatalogAction(finding)}`"
                @click="applyFix(finding, suggestCatalogAction(finding)!, finding.affected_resources[0], false)"
              >
                Apply Fix
              </button>
              <button
                class="btn btn-outline btn-sm"
                @click="applyFix(finding, suggestCatalogAction(finding)!, finding.affected_resources[0], true)"
              >
                Preview
              </button>
            </div>
          </article>
        </div>
      </div>
    </div>

    <div v-if="hasLoaded && nodes.length > 0" class="card nodes-card mt-4">
      <h3 class="section-title">Node Resources</h3>
      <div class="nodes-grid">
        <div v-for="node in nodes" :key="node.id" class="node-stat">
          <div class="node-stat__header">
            <strong>{{ node.name }}</strong>
            <span class="node-roles text-muted">{{ formatRoles(node.roles) }}</span>
          </div>
          <div class="node-bars">
            <div class="bar-row">
              <span class="label-caps">Heap</span>
              <div class="bar-track">
                <div
                  class="bar-fill"
                  :style="{
                    width: `${node.heap_used_percent ?? 0}%`,
                    background: (node.heap_used_percent ?? 0) >= 75 ? 'hsl(var(--health-yellow))' : 'hsl(var(--health-green))',
                  }"
                ></div>
              </div>
              <span class="bar-value">{{ node.heap_used_percent ?? '—' }}%</span>
            </div>
            <div class="bar-row">
              <span class="label-caps">Disk</span>
              <div class="bar-track">
                <div
                  class="bar-fill"
                  :style="{
                    width: `${node.disk_used_percent ?? 0}%`,
                    background: (node.disk_used_percent ?? 0) >= 85 ? 'hsl(var(--health-red))' : 'hsl(var(--health-green))',
                  }"
                ></div>
              </div>
              <span class="bar-value">{{ node.disk_used_percent ?? '—' }}%</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.health-panel {
  min-height: 320px;
}

.health-layout {
  display: grid;
  grid-template-columns: minmax(260px, 320px) 1fr;
  gap: 1.5rem;
}

@media (max-width: 900px) {
  .health-layout {
    grid-template-columns: 1fr;
  }
}

.health-summary-card {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 1rem;
}

.score-wrap {
  display: flex;
  justify-content: center;
}

.summary-heading {
  margin: 0 0 0.35rem;
  font-size: 0.72rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: hsl(var(--muted-foreground));
}

.inventory-meta {
  border-top: 1px solid hsl(var(--border) / 0.6);
  padding-top: 0.75rem;
}

.inventory-grid {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.inventory-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 0.5rem;
  align-items: start;
}

.inventory-row--warn .value-chip {
  color: hsl(var(--health-yellow));
}

.inventory-values {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.1rem;
}

.inventory-detail {
  font-size: 0.68rem;
  color: hsl(var(--muted-foreground));
  font-family: var(--font-mono);
}

.inventory-empty {
  font-size: 0.8rem;
  margin: 0;
}

.inventory-skeleton {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.health-trend {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 0.8rem;
}

.sparkline {
  font-family: var(--font-mono);
  letter-spacing: 0.05em;
  color: hsl(var(--primary));
}

.trend-delta {
  font-family: var(--font-mono);
  color: hsl(var(--muted-foreground));
}

.health-meta {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  font-size: 0.85rem;
}

.health-meta p {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin: 0;
}

.loading-label {
  font-size: 0.875rem;
  margin-bottom: 0.75rem;
}

.section-title {
  font-size: 1.05rem;
  font-weight: 600;
  margin-bottom: 1rem;
}

.findings-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.finding-row {
  padding: 1rem;
  border-radius: var(--radius);
  border: 1px solid hsl(var(--border));
  background: hsl(var(--muted) / 0.25);
}

.finding-row.expanded {
  border-color: hsl(var(--primary) / 0.35);
}

.finding-toggle {
  width: 100%;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.finding-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.5rem;
}

.chevron {
  flex-shrink: 0;
  margin-top: 0.15rem;
  color: hsl(var(--muted-foreground));
  transition: transform 0.2s ease;
}

.chevron.open {
  transform: rotate(180deg);
}

.finding-row.severity-high {
  border-color: hsl(var(--destructive) / 0.35);
}

.finding-row.severity-medium {
  border-color: hsl(var(--warning) / 0.35);
}

.finding-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.35rem;
}

.finding-severity {
  color: hsl(var(--muted-foreground));
}

.finding-status {
  font-size: 0.75rem;
  text-transform: uppercase;
  color: hsl(var(--muted-foreground));
}

.finding-row h4 {
  font-size: 0.95rem;
  font-weight: 600;
  margin-bottom: 0.35rem;
}

.finding-summary {
  font-size: 0.875rem;
  margin-bottom: 0.25rem;
}

.finding-detail,
.finding-action {
  font-size: 0.8rem;
  margin-top: 0.35rem;
  display: flex;
  align-items: flex-start;
  gap: 0.35rem;
}

.finding-fixes {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.75rem;
}

.btn-sm {
  padding: 0.35rem 0.75rem;
  font-size: 0.8rem;
}

.empty-findings {
  color: hsl(var(--muted-foreground));
  padding: 2rem 0;
  text-align: center;
}

.nodes-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 1rem;
}

.node-stat {
  padding: 1rem;
  border: 1px solid hsl(var(--border));
  border-radius: var(--radius);
  background: hsl(var(--muted) / 0.2);
}

.node-stat__header {
  margin-bottom: 0.75rem;
}

.node-roles {
  display: block;
  font-size: 0.75rem;
  margin-top: 0.15rem;
}

.bar-row {
  display: grid;
  grid-template-columns: 3rem 1fr 3rem;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
  font-size: 0.75rem;
}

.bar-track {
  height: 6px;
  background: hsl(var(--muted));
  border-radius: 999px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: 999px;
  transition: width 0.3s ease;
}

.bar-value {
  text-align: right;
  font-family: var(--font-mono);
}

.mt-4 {
  margin-top: 1rem;
}

.mb-4 {
  margin-bottom: 1rem;
}

.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .spinning {
    animation: none;
  }
}
</style>