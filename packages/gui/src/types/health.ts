export type FindingStatus = 'pass' | 'warn' | 'fail' | 'unknown' | 'skipped'
export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info'

export interface RemediationAction {
  id: string
  label: string
  command: string
  safety: 'observe' | 'suggest' | 'confirm' | 'destructive'
}

export interface HealthFinding {
  id: string
  category: string
  title: string
  status: FindingStatus
  severity: Severity
  score_impact: number
  summary: string
  detail?: string
  affected_resources: string[]
  remediation?: RemediationAction
}

export interface HealthScoreResponse {
  cluster_name: string
  overall_score: number
  overall_status: FindingStatus
  assessed_at: string
  elasticsearch_version: string
  cached: boolean
  findings_count: number
}

export interface HealthAssessment {
  session_id: string
  cluster_name: string
  elasticsearch_version: string
  assessed_at: string
  duration_ms: number
  overall_score: number
  overall_status: FindingStatus
  findings: HealthFinding[]
  collectors_run: string[]
  collectors_failed: string[]
}

export interface NodeHealthSummary {
  id: string
  name: string
  roles: string[]
  heap_used_percent: number | null
  disk_used_percent: number | null
}

export function scoreColor(score: number | null | undefined): string {
  if (score == null) return 'hsl(var(--muted-foreground))'
  if (score >= 90) return 'hsl(var(--health-green))'
  if (score >= 70) return 'hsl(var(--health-yellow))'
  return 'hsl(var(--health-red))'
}

export function severityClass(severity: Severity): string {
  switch (severity) {
    case 'critical':
    case 'high':
      return 'severity-high'
    case 'medium':
      return 'severity-medium'
    default:
      return 'severity-low'
  }
}