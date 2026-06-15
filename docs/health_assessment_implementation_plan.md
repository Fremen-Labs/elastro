# Elastro Health Assessment — Technical Implementation Plan

**Status:** Draft  
**Version target:** 1.4.x → 1.6.x  
**Author:** Engineering (derived from strategic health assessment report)  
**Last updated:** 2026-06-15

---

## 1. Purpose & Scope

This document defines the technical implementation for evolving Elastro from an Elasticsearch management CLI into a **health assessment and remediation platform**. The plan is organized as a **DAG of small, reviewable PRs** that can ship incrementally without breaking existing workflows.

### 1.1 Goals

| Goal | Success metric |
|------|----------------|
| One-command health assessment | `elastro health assess` returns scored findings in <30s on a 20-node cluster |
| Actionable remediation | ≥80% of `_health_report` diagnoses map to an elastro command or guided fix |
| Engineer-first UX | CLI table output readable without JSON parsing; GUI health tab mirrors CLI |
| Safe execution | All destructive fixes require `--fix` or interactive confirm; dry-run by default |
| Auditability | Every assess/fix run logged with LogLoom node IDs to `elastro-health-audit` index |
| Self-managed excellence | Works offline/air-gapped without Cloud Connect |

### 1.2 Non-goals (v1)

- Replacing AutoOps or Stack Monitoring as a continuous metrics platform
- Long-term time-series retention (delegated to customer's ES indices)
- Full Elastic Stack monitoring (Logstash, Kibana, APM)
- Auto-remediation without human confirmation (safety tier `auto` deferred to Phase 4)

### 1.3 Backward compatibility

| Current | Migration |
|---------|-----------|
| `elastro utils health` | Kept; deprecated notice pointing to `elastro health status` |
| `elastro cluster allocation` | Kept; folded into `elastro health shards` |
| `elastro index fix` | Kept; becomes remediation backend for `elastro health assess --fix` |
| GUI unhealthy indices API | Extended, not replaced |

---

## 2. Architecture

### 2.1 Package layout (new modules)

```
elastro/
├── health/                          # NEW top-level health domain package
│   ├── __init__.py
│   ├── models.py                    # Pydantic: Finding, Assessment, Score, Remediation
│   ├── collectors/                  # Data gathering (thin ES API wrappers)
│   │   ├── __init__.py
│   │   ├── base.py                  # Collector protocol + registry
│   │   ├── cluster.py               # cluster.health, pending_tasks
│   │   ├── health_report.py         # _health_report API (8.7+)
│   │   ├── nodes.py                 # nodes.stats, nodes.info
│   │   ├── shards.py                # cat.shards, allocation_explain
│   │   ├── disk.py                  # fs stats + watermark derivation
│   │   ├── ilm.py                   # ilm status + health_report ilm indicator
│   │   ├── snapshots.py           # repos + verify_repository
│   │   └── security.py              # Phase 4: native realm, TLS hints
│   ├── rules/                       # Custom checks beyond ES health report
│   │   ├── __init__.py
│   │   ├── engine.py                # Rule evaluation + severity
│   │   ├── replica.py               # replica > data_nodes - 1
│   │   ├── oversharding.py          # avg shard size thresholds
│   │   ├── hotspots.py              # per-node resource variance
│   │   ├── mapping_explosion.py     # field count limits
│   │   └── persistent_yellow.py     # yellow > N hours (needs history)
│   ├── scoring.py                   # Weighted 0-100 composite score
│   ├── remediation/                 # Safe fix execution
│   │   ├── __init__.py
│   │   ├── catalog.py               # diagnosis.action → elastro handler map
│   │   ├── executor.py              # dry-run, confirm, execute, rollback snapshot
│   │   └── actions/                 # One module per fix type
│   │       ├── reduce_replicas.py
│   │       ├── reroute.py
│   │       ├── clear_routing_filters.py
│   │       ├── enable_routing.py
│   │       └── cancel_task.py
│   ├── assessor.py                  # Orchestrator: collect → rule → score → findings
│   ├── audit.py                     # LogLoom-enriched session logging
│   └── formatters/                  # CLI/GUI output
│       ├── table.py
│       ├── json_fmt.py
│       └── yaml_fmt.py
├── utils/health.py                  # REFACTOR: thin facade delegating to health/
├── cli/commands/health.py           # NEW: health command group
└── server/routes/health.py          # NEW: /api/clusters/{name}/health/*
```

### 2.2 Data flow

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────┐
│ CLI / GUI    │────▶│ HealthAssessor  │────▶│ Collectors   │──▶ ES APIs
│ health assess│     │ .run()          │     │ (parallel)   │
└──────────────┘     └────────┬────────┘     └──────────────┘
                              │
                    ┌─────────▼─────────┐
                    │ RuleEngine        │
                    │ + ScoringEngine   │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │ AssessmentReport  │
                    │ (findings, score) │
                    └─────────┬─────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        TableFormatter   RemediationExecutor  AuditLogger
                                              (LogLoom NDJSON → ES)
```

### 2.3 Collector concurrency

Collectors run via `concurrent.futures.ThreadPoolExecutor` (existing pattern in ingest engine). Each collector:

- Declares `name`, `es_version_min`, `timeout`, `depends_on`
- Returns `CollectorResult(status, data, error, duration_ms)`
- Fails soft: partial assessment if one collector times out

```python
# elastro/health/collectors/base.py
class Collector(Protocol):
    name: str
    def collect(self, ctx: CollectContext) -> CollectorResult: ...
```

Orchestrator merges results; worst indicator status wins for section score.

---

## 3. Core data models

**File:** `elastro/health/models.py`

```python
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class Severity(str, Enum):
    CRITICAL = "critical"   # red / data loss risk
    HIGH = "high"             # yellow / imminent failure
    MEDIUM = "medium"         # degraded performance
    LOW = "low"               # best-practice deviation
    INFO = "info"             # informational

class FindingStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    UNKNOWN = "unknown"
    SKIPPED = "skipped"       # ES version unsupported

class RemediationSafety(str, Enum):
    OBSERVE = "observe"       # read-only recommendation
    SUGGEST = "suggest"       # show command, no execution
    CONFIRM = "confirm"       # interactive or --fix required
    DESTRUCTIVE = "destructive"  # extra guard (system indices)

class RemediationAction(BaseModel):
    id: str                          # e.g. "reduce_replicas"
    label: str                       # human label
    command: str                     # elastro command template
    safety: RemediationSafety
    preconditions: List[str] = []
    rollback_command: Optional[str] = None

class Finding(BaseModel):
    id: str                          # stable: "disk.flood_stage.node-3"
    category: str                    # disk | shards | master | ilm | ...
    title: str
    status: FindingStatus
    severity: Severity
    score_impact: int                # points deducted from 100
    summary: str
    detail: Optional[str] = None
    affected_resources: List[str] = []
    source: str                      # "health_report" | "rule" | "collector"
    indicator: Optional[str] = None  # ES health report indicator name
    remediation: Optional[RemediationAction] = None
    metadata: Dict[str, Any] = {}

class AssessmentReport(BaseModel):
    schema_version: str = "1.0"
    session_id: str                  # uuid4
    cluster_name: str
    elasticsearch_version: str
    assessed_at: datetime
    duration_ms: int
    overall_score: int               # 0-100
    overall_status: FindingStatus    # derived from score bands
    findings: List[Finding]
    collectors_run: List[str]
    collectors_failed: List[str] = []
    raw_health_report: Optional[Dict[str, Any]] = None  # omitted in table output

class AssessmentHistoryRecord(BaseModel):
    """Indexed to elastro-health-assessments."""
    report: AssessmentReport
    profile: str
    host: str
    fixes_applied: List[str] = []
```

### 3.1 Score bands

| Score | Status | CLI color |
|-------|--------|-----------|
| 90–100 | `pass` | green |
| 70–89 | `warn` | yellow |
| 50–69 | `degraded` | orange |
| 0–49 | `fail` | red |

### 3.2 Default indicator weights

**File:** `elastro/health/scoring.py`

```python
DEFAULT_WEIGHTS = {
    "master_is_stable": 20,
    "shards_availability": 20,
    "disk": 15,
    "shards_capacity": 10,
    "ilm": 8,
    "slm": 5,
    "repository_integrity": 7,
    "data_stream_lifecycle": 5,
    "file_settings": 3,
    "pending_tasks": 4,
    "jvm_pressure": 3,       # custom rule
}
```

Custom rules add deductions on top; cap total deduction at 100.

---

## 4. Elasticsearch API integration

### 4.1 APIs by phase

| API | Phase | Collector | Notes |
|-----|-------|-----------|-------|
| `GET _health_report` | 1 | `health_report.py` | `verbose=false` for polling; `true` for assess |
| `GET _health_report/{feature}` | 1 | `health_report.py` | Per-indicator drill-down |
| `GET _cluster/health` | 1 | `cluster.py` | Existing |
| `GET _cluster/pending_tasks` | 1 | `cluster.py` | Existing in HealthManager |
| `GET _nodes/stats` | 1 | `nodes.py` | jvm, fs, os, breaker metrics |
| `GET _nodes/info` | 1 | `nodes.py` | roles, version |
| `GET _cat/shards` | 1 | `shards.py` | v=true for explain |
| `POST _cluster/allocation/explain` | 1 | `shards.py` | Existing IndexManager pattern |
| `GET _cluster/stats` | 2 | `cluster.py` | Aggregate stats |
| `GET _indices/stats` | 2 | `shards.py` | Indexing rate baseline |
| `GET _cat/fielddata` | 2 | `nodes.py` | Memory pressure |
| `GET _nodes/hot_threads` | 2 | `nodes.py` | CPU diagnosis |
| `GET _ilm/explain/{index}` | 2 | `ilm.py` | Per-index lifecycle |
| `POST _snapshot/{repo}/_verify` | 1 | `snapshots.py` | Existing verify_repository |
| `GET _cluster/settings` | 1 | `cluster.py` | Routing, shard limits |

### 4.2 Version gating

```python
# elastro/health/collectors/health_report.py
def supports(es_version: str) -> bool:
    major, minor = parse_version(es_version)
    return (major, minor) >= (8, 7)

# Fallback for < 8.7: synthesize findings from cluster.health + allocation_explain only
```

### 4.3 Health report → Finding mapper

**File:** `elastro/health/collectors/health_report.py`

```python
INDICATOR_SEVERITY = {
    "red": (FindingStatus.FAIL, Severity.CRITICAL),
    "yellow": (FindingStatus.WARN, Severity.HIGH),
    "green": (FindingStatus.PASS, Severity.INFO),
    "unknown": (FindingStatus.UNKNOWN, Severity.MEDIUM),
}

def map_indicator(indicator_name: str, body: dict) -> Finding:
    status = body.get("status", "unknown")
    # Extract diagnosis[0].cause, diagnosis[0].action when verbose=true
    ...
```

---

## 5. Remediation catalog

**File:** `elastro/health/remediation/catalog.py`

Maps ES `diagnosis.action` text and rule IDs to executable handlers.

| Remediation ID | Trigger | Handler | Safety | Existing code |
|----------------|---------|---------|--------|---------------|
| `reduce_replicas` | Yellow replica / same-node | `actions/reduce_replicas.py` | DESTRUCTIVE | `index.py` fix, `indices.py` API |
| `reroute_failed` | ALLOCATION_FAILED | `actions/reroute.py` | CONFIRM | same |
| `clear_routing_filters` | filter decider | `actions/clear_routing_filters.py` | CONFIRM | same |
| `enable_routing` | allocation.enable=none | `actions/enable_routing.py` | CONFIRM | `cluster.py` settings |
| `cancel_task` | Stuck reindex/snapshot | `actions/cancel_task.py` | CONFIRM | `tasks.py` |
| `verify_snapshot_repo` | repository_integrity yellow | `actions/verify_repo.py` | SUGGEST | HealthManager.verify_repository |
| `ilm_retry` | ilm indicator yellow | `actions/ilm_retry.py` | CONFIRM | new wrapper on `_ilm/retry` |

### 5.1 Executor contract

**File:** `elastro/health/remediation/executor.py`

```python
class RemediationExecutor:
    def __init__(self, client, *, dry_run: bool = True, interactive: bool = True):
        ...

    def execute(self, action: RemediationAction, context: dict) -> RemediationResult:
        """
        1. Validate preconditions (e.g. not system index without --force)
        2. Snapshot current settings to rollback store
        3. If dry_run: return planned changes only
        4. If interactive: Confirm.ask()
        5. Execute via existing IndexManager / cluster APIs
        6. Return RemediationResult(success, message, rollback_id)
        """
```

### 5.2 Rollback store

**File:** `~/.elastic/health-rollbacks/{session_id}.json` (local)  
Optional index: `elastro-health-rollbacks` for team visibility.

```json
{
  "rollback_id": "rb-uuid",
  "session_id": "assess-uuid",
  "action": "reduce_replicas",
  "index": "my-index",
  "before": {"index": {"number_of_replicas": 1}},
  "applied_at": "2026-06-15T12:00:00Z"
}
```

---

## 6. CLI design

### 6.1 New command group

**File:** `elastro/cli/commands/health.py`

Register in `elastro/cli/cli.py`:

```python
from elastro.cli.commands.health import health_group
cli.add_command(health_group)
```

### 6.2 Commands

#### `elastro health assess`

Primary entry point.

```bash
elastro health assess [OPTIONS]

Options:
  --profile, -p TEXT          Config profile (inherits global)
  --output, -o [table|json|yaml]   Default: table
  --verbose, -v               Include raw collector data
  --feature TEXT              Limit to health report feature(s); repeatable
  --timeout TEXT              Per-collector timeout (default: 30s)
  --no-verbose-report         Pass verbose=false to _health_report (faster)
  --fix                       Execute CONFIRM-tier remediations interactively
  --dry-run                   Show planned fixes only (default when --fix)
  --history / --no-history    Index report to elastro-health-assessments (default: off)
  --index TEXT                Assessment history index name
```

**Behavior:**
1. `HealthAssessor.run()` with all Phase-1 collectors
2. Print score banner + findings table (severity-sorted)
3. If `--fix`: prompt per CONFIRM finding
4. If `--history`: bulk index `AssessmentReport` JSON

#### `elastro health status`

Replacement for `utils health` (thin wrapper).

```bash
elastro health status [--level cluster|indices|shards] [--wait STATUS] [--timeout 30s]
```

**Fix:** Wire `--wait` → `wait_for_status` (bug fix PR 0).

#### `elastro health report`

```bash
elastro health report [--feature NAME] [--verbose] [--size N]
```

Raw `_health_report` passthrough with elastro formatting.

#### `elastro health nodes`

```bash
elastro health nodes [--node-id ID] [--metric jvm,fs,os,breaker] [--hotspots]
```

Exposes `HealthManager.node_stats()`. `--hotspots` runs variance rule.

#### `elastro health shards`

```bash
elastro health shards [--index NAME] [--analyze] [--explain]
```

Merges `cluster allocation` + shard size analysis (Phase 2).

#### `elastro health score`

```bash
elastro health score [--history] [--last N]
```

Print current or historical scores from assessment index.

#### `elastro health rollback`

```bash
elastro health rollback --id ROLLBACK_ID [--dry-run]
```

Phase 3.

#### `elastro health lint`

```bash
elastro health lint [--category settings|mappings|shards]
```

Phase 4 best-practice linter.

### 6.3 Table output example

**File:** `elastro/health/formatters/table.py`

Uses Rich (existing pattern in `index.py`, `cluster.py`):

```
╭─────────────────────────────────────────────────────────────╮
│  production-es  │  Score: 72/100 (DEGRADED)  │  ES 8.17.2  │
╰─────────────────────────────────────────────────────────────╯

┌──────────┬────────────────────────────┬──────────┬─────────────────────────┐
│ Severity │ Finding                    │ Status   │ Action                  │
├──────────┼────────────────────────────┼──────────┼─────────────────────────┤
│ CRITICAL │ Disk flood-stage node-3    │ FAIL     │ elastro health assess   │
│          │                            │          │   --fix (rollover)      │
│ HIGH     │ 2 unassigned replica shards│ WARN     │ index fix               │
│ MEDIUM   │ ILM stuck: logs-000042     │ WARN     │ ilm explain logs-000042 │
└──────────┴────────────────────────────┴──────────┴─────────────────────────┘
```

### 6.4 Deprecation

`elastro utils health` prints:

```
DeprecationWarning: use 'elastro health status' (removal in 2.0)
```

---

## 7. GUI & API design

### 7.1 New routes

**File:** `elastro/server/routes/health.py`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/clusters/{name}/health/assess` | Full assessment (query: `verbose`, `features`) |
| `GET` | `/api/clusters/{name}/health/score` | Score only (cached 60s) |
| `GET` | `/api/clusters/{name}/health/findings` | Open findings list |
| `POST` | `/api/clusters/{name}/health/fix` | Body: `{finding_id, action, dry_run}` |
| `GET` | `/api/clusters/{name}/health/history` | Past assessments |
| `GET` | `/api/clusters/{name}/health/nodes` | Node stats summary |

Register in `elastro/server/routes/__init__.py`.

### 7.2 Schemas

**File:** `elastro/server/schemas.py` (extend)

```python
class HealthFixRequestSchema(BaseModel):
    finding_id: str
    action: str
    dry_run: bool = True
    force: bool = False  # system indices

class HealthAssessQuerySchema(BaseModel):
    verbose: bool = True
    features: Optional[List[str]] = None
```

### 7.3 Dashboard enhancements

**File:** `packages/gui/src/views/Dashboard.vue`

- Add `score` column per cluster (from `/health/score`)
- Color badge: 90+ green, 70+ yellow, <70 red
- Click → `ClusterDetail` health tab

**File:** `packages/gui/src/views/ClusterDetail.vue`

New **Health** tab (alongside existing unhealthy indices):

- Score gauge component
- Findings list with fix buttons (reuses existing fix modal pattern)
- Node resource mini-charts (heap %, disk %)
- "Run Assessment" button → `GET /health/assess`

**New component:** `packages/gui/src/components/health/HealthScore.vue`

### 7.4 Caching

Server-side: cache `AssessmentReport` per cluster for 60 seconds (in-memory dict with TTL). Prevents hammering `_health_report?verbose=true`.

---

## 8. Audit & LogLoom integration

### 8.1 Session logging

**File:** `elastro/health/audit.py`

Every `assess` and `fix` call:

```python
def log_event(event_type: str, session_id: str, payload: dict):
    logger.info("health.%s", event_type, extra={...})  # → LogLoom enrichment
```

Ensure these functions have `logger.*()` calls (instrument in PR 0):

- `HealthAssessor.run`
- `RemediationExecutor.execute`
- Each collector `collect()` on failure

### 8.2 CI gate

Add to `.github/workflows` (or local `Makefile`):

```bash
logloom build --source .
logloom lint --min-coverage 80 --paths elastro/health/
```

### 8.3 Assessment history index

**Default index:** `elastro-health-assessments`  
**Mapping:**

```json
{
  "mappings": {
    "properties": {
      "session_id": {"type": "keyword"},
      "cluster_name": {"type": "keyword"},
      "assessed_at": {"type": "date"},
      "overall_score": {"type": "integer"},
      "overall_status": {"type": "keyword"},
      "findings": {"type": "nested"},
      "elasticsearch_version": {"type": "keyword"},
      "profile": {"type": "keyword"}
    }
  }
}
```

---

## 9. PR plan (DAG)

PRs are ordered; parallel PRs share a letter suffix.

```
PR-0 (foundation)
  ├── PR-1a (health_report collector)
  ├── PR-1b (CLI health group + assess MVP)
  └── PR-1c (fix --wait bug)
        ├── PR-2a (nodes collector + health nodes)
        ├── PR-2b (GUI health tab MVP)
        └── PR-2c (remediation executor refactor)
              ├── PR-3a (custom rules: replica, disk)
              ├── PR-3b (shard analyze + hotspots)
              └── PR-3c (rollback + audit index)
                    └── PR-4a (lint + history trends)
```

### PR-0: Foundation & quick wins

**Estimate:** 3 days  
**Branch:** `feature/health-foundation`

| Task | File(s) |
|------|---------|
| Create `elastro/health/` package skeleton | `health/__init__.py`, `models.py`, `assessor.py` |
| Add `Collector` protocol + registry | `health/collectors/base.py` |
| Refactor `HealthManager` to delegate (keep public API) | `utils/health.py` |
| Fix `--wait` on utils health | `cli/commands/utils.py` |
| Add `elastro health status` alias | `cli/commands/health.py` |
| Implement `snapshot delete` or remove stub | `cli/commands/snapshot.py` |
| Unit tests for models + registry | `tests/unit/health/` |

**Acceptance criteria:**
- `elastro health status --wait green` blocks until green
- `pytest tests/unit/health/` passes
- No breaking changes to existing imports of `HealthManager`

---

### PR-1a: Health Report collector

**Estimate:** 4 days  
**Depends on:** PR-0

| Task | File(s) |
|------|---------|
| `HealthReportCollector` | `health/collectors/health_report.py` |
| Indicator → Finding mapper | same |
| Version fallback for ES < 8.7 | `health/collectors/cluster.py` |
| Unit tests with recorded fixtures | `tests/fixtures/health_report_*.json` |

**Acceptance criteria:**
- Maps all 9 indicators to `Finding` objects
- `verbose=true` extracts `diagnosis[0].action`
- Graceful `SKIPPED` on 404 (old ES)

---

### PR-1b: `elastro health assess` MVP

**Estimate:** 5 days  
**Depends on:** PR-1a

| Task | File(s) |
|------|---------|
| `ClusterCollector`, `PendingTasksCollector` | `health/collectors/cluster.py` |
| `ScoringEngine` | `health/scoring.py` |
| `HealthAssessor.run()` | `health/assessor.py` |
| CLI `assess`, `report`, `score` | `cli/commands/health.py` |
| Table + JSON formatters | `health/formatters/` |
| Register `health_group` in cli.py | `cli/cli.py` |
| Integration test (mock ES) | `tests/integration/test_health_assess.py` |

**Acceptance criteria:**
- `elastro health assess -o table` prints score + findings
- `elastro health assess -o json` validates against `AssessmentReport` schema
- Completes in <5s against mocked ES

---

### PR-1c: Wire existing remediation into assess

**Estimate:** 3 days  
**Depends on:** PR-1b

| Task | File(s) |
|------|---------|
| Extract fix logic from `index.py` | `health/remediation/actions/*.py` |
| `RemediationCatalog` | `health/remediation/catalog.py` |
| `RemediationExecutor` (dry-run + confirm) | `health/remediation/executor.py` |
| `--fix` flag on assess | `cli/commands/health.py` |
| Refactor `index fix` to use executor | `cli/commands/index.py` |
| Refactor API fix endpoint | `server/routes/indices.py` |

**Acceptance criteria:**
- `elastro health assess --fix` offers same 3 fixes as `index fix`
- `index fix` behavior unchanged (regression test)
- Dry-run prints planned API calls without executing

---

### PR-2a: Node & disk collectors

**Estimate:** 4 days  
**Depends on:** PR-1b

| Task | File(s) |
|------|---------|
| `NodesCollector` (jvm, fs, breaker) | `health/collectors/nodes.py` |
| `DiskCollector` (watermark derivation) | `health/collectors/disk.py` |
| `SnapshotsCollector` | `health/collectors/snapshots.py` |
| `elastro health nodes` command | `cli/commands/health.py` |
| JVM pressure rule (heap > 75%) | `health/rules/jvm.py` |

**Watermark logic:**

```python
used_pct = fs.total.available_bytes / fs.total.total_bytes  # invert as needed
if used_pct >= flood_stage: severity = CRITICAL
elif used_pct >= high_stage: severity = HIGH
```

**Acceptance criteria:**
- `elastro health nodes --metric jvm,fs` table output
- Disk finding generated when any node exceeds high watermark

---

### PR-2b: GUI health tab

**Estimate:** 5 days  
**Depends on:** PR-1b

| Task | File(s) |
|------|---------|
| Health API routes | `server/routes/health.py` |
| Pydantic schemas | `server/schemas.py` |
| Dashboard score column | `Dashboard.vue` |
| ClusterDetail health tab | `ClusterDetail.vue`, `HealthScore.vue` |
| Fix button → `/health/fix` | same |

**Acceptance criteria:**
- Dashboard shows numeric score per cluster
- Health tab lists findings with fix actions
- 60s server cache prevents duplicate assess calls

---

### PR-2c: Integration tests for remediation API

**Estimate:** 3 days  
**Depends on:** PR-1c, PR-2b

| Task | File(s) |
|------|---------|
| API tests for `/health/fix` | `tests/integration/test_health_api.py` |
| API tests for `/indices/unhealthy` (existing) | same |
| CLI regression for `index fix` | `tests/integration/test_index_fix.py` |

---

### PR-3a: Custom rules engine

**Estimate:** 5 days  
**Depends on:** PR-2a

| Task | File(s) |
|------|---------|
| `RuleEngine` | `health/rules/engine.py` |
| Replica misconfig rule | `health/rules/replica.py` |
| Persistent yellow rule (requires history) | `health/rules/persistent_yellow.py` |
| `IlmCollector` | `health/collectors/ilm.py` |

**Replica rule logic:**

```python
data_nodes = count(nodes where "data" in roles)
if index.replicas >= data_nodes and data_nodes > 0:
    emit Finding(severity=HIGH, remediation=reduce_replicas_smart)
# Smart: suggest min(replicas, data_nodes - 1) not always 0
```

---

### PR-3b: Shard analysis & hotspots

**Estimate:** 5 days  
**Depends on:** PR-3a

| Task | File(s) |
|------|---------|
| `elastro health shards --analyze` | `cli/commands/health.py` |
| Oversharding / undersharding rules | `health/rules/oversharding.py` |
| Hotspot variance rule | `health/rules/hotspots.py` |
| `elastro health hotspots` alias | same |

**Shard analyze output:**

```
Total shards: 1,247
Avg size: 2.3 GB
< 1 MB: 45 shards (OVERSHARDED)
> 50 GB: 3 shards (UNDERSHARDED)
```

---

### PR-3c: Rollback & audit index

**Estimate:** 4 days  
**Depends on:** PR-1c

| Task | File(s) |
|------|---------|
| Rollback store | `health/remediation/rollback.py` |
| `elastro health rollback` | `cli/commands/health.py` |
| Audit logger + LogLoom instrumentation | `health/audit.py` |
| `--history` flag + index template | `health/assessor.py` |
| `elastro health score --history` | `cli/commands/health.py` |

---

### PR-4a: Lint, mapping explosion, docs

**Estimate:** 5 days  
**Depends on:** PR-3b, PR-3c

| Task | File(s) |
|------|---------|
| `elastro health lint` | `cli/commands/health.py` |
| Mapping explosion rule | `health/rules/mapping_explosion.py` |
| Security collector (basic) | `health/collectors/security.py` |
| Update `docs/commands_reference.md` | docs |
| Deprecation notices | `cli/commands/utils.py` |
| LogLoom CI lint gate | `.github/workflows/ci.yml` |

---

## 10. Testing strategy

### 10.1 Test pyramid

| Layer | Coverage target | Location |
|-------|-----------------|----------|
| Unit | 90% on `elastro/health/` | `tests/unit/health/` |
| Integration (mock ES) | All collectors + assess | `tests/integration/health/` |
| Integration (real ES) | Optional CI job | `tests/integration/health_live/` (nightly) |
| GUI e2e | Health tab smoke | `packages/gui` Playwright (optional) |

### 10.2 Fixtures

Record real `_health_report` responses (sanitized) for ES 8.17:

```
tests/fixtures/health/
  health_report_green.json
  health_report_disk_red.json
  health_report_shards_yellow.json
  node_stats_pressure.json
  cat_shards_oversharded.json
```

### 10.3 Key test cases

```python
# tests/unit/health/test_scoring.py
def test_score_all_green_returns_100()
def test_disk_red_deducts_15_points()
def test_multiple_yellow_caps_at_49()

# tests/unit/health/test_remediation_executor.py
def test_dry_run_does_not_call_put_settings()
def test_system_index_requires_force()
def test_rollback_restores_replica_count()

# tests/integration/test_health_assess.py
def test_assess_cli_table_output()
def test_assess_fix_interactive_decline()
```

---

## 11. Configuration

**File:** `elastro/config/defaults.py` (extend)

```yaml
health:
  assessment:
    timeout: 30s
    verbose_report: true
    cache_ttl_seconds: 60
    history_index: elastro-health-assessments
    audit_index: elastro-health-audit
    enable_history: false
  scoring:
    weights: {}  # override DEFAULT_WEIGHTS
  remediation:
    safety_default: confirm
    allow_destructive: false
    system_index_patterns: [".*"]
  rules:
    overshard_threshold_mb: 1
    undershard_threshold_gb: 50
    jvm_heap_warn_pct: 75
    hotspot_variance_pct: 30
```

Accessible via:

```bash
elastro config get health.assessment.timeout
```

---

## 12. Performance & reliability

### 12.1 Latency budget

| Step | Target |
|------|--------|
| `_health_report?verbose=true` | <10s |
| `nodes.stats` | <5s |
| `cat.shards` (large cluster) | <8s |
| Rule evaluation | <500ms |
| **Total assess** | <30s |

### 12.2 Large cluster mitigations

- `cat.shards` with `h=` filter for analyze (exclude closed)
- `--feature disk` for targeted assess
- `--no-verbose-report` for polling mode
- Collector timeouts with partial results

### 12.3 Error handling

- Collector timeout → `Finding(status=SKIPPED, detail="collector timed out")`
- ES 403 → `Finding(severity=HIGH, title="Insufficient privileges for _health_report")`
- Connection failure → exit code 2, no partial report

---

## 13. Security considerations

| Risk | Mitigation |
|------|------------|
| Destructive replica reduction | `DESTRUCTIVE` tier; system index confirm; `--force` flag |
| Routing enable=all during maintenance | Show current setting; require typed confirm |
| Audit index contains cluster metadata | No credentials in audit payload |
| GUI fix endpoint CSRF | Existing Bearer token auth |
| Rollback file permissions | `0600` on `~/.elastic/health-rollbacks/` |

---

## 14. Documentation deliverables

| Document | PR |
|----------|-----|
| `docs/health_assessment_implementation_plan.md` | (this doc) |
| `docs/health_commands.md` | PR-1b |
| Update `docs/commands_reference.md` | PR-4a |
| Update `README.md` health section | PR-2b |
| Fix `cluster health` README typo | PR-1b |
| GUI health tab screenshot | PR-2b |

---

## 15. Timeline summary

| Phase | PRs | Estimate | Cumulative |
|-------|-----|----------|------------|
| Foundation | PR-0, PR-1a, PR-1b, PR-1c | ~15 days | 3 weeks |
| Depth | PR-2a, PR-2b, PR-2c | ~12 days | 5 weeks |
| Intelligence | PR-3a, PR-3b, PR-3c | ~14 days | 8 weeks |
| Polish | PR-4a | ~5 days | **~9 weeks** |

*Estimates assume 1 engineer full-time; PR-2b GUI can parallelize with PR-2a backend.*

---

## 16. Risks & mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| `_health_report` API changes across ES versions | Mapper breaks | Fixture tests per minor version; version gate |
| String-matching allocation explanations (existing) | False fix suggestions | Phase 3: prefer health report diagnosis over string match |
| `reduce_replicas: 0` destroys HA | Production incident | Smart replica suggestion; DESTRUCTIVE tier; dry-run default |
| verbose health report load on large clusters | ES master pressure | Default `verbose=false` for polling; document `--no-verbose-report` |
| LogLoom not installed | No audit enrichment | Graceful degradation (existing pattern in logger.py) |
| GUI/API drift from CLI | Inconsistent fixes | Shared `RemediationExecutor` (PR-1c) |

---

## 17. Definition of done (v1.5 release)

- [ ] `elastro health assess` ships with 9 health report indicators + 4 custom rules
- [ ] Score 0–100 displayed in CLI and GUI dashboard
- [ ] 3 existing remediations + `enable_routing` + `verify_repo` executable via `--fix`
- [ ] `--wait` fixed on health status
- [ ] Integration tests for assess + fix API
- [ ] LogLoom coverage ≥80% on `elastro/health/`
- [ ] Documentation updated; `utils health` deprecated
- [ ] No regressions in `elastro index fix` behavior

---

## 18. Appendix: `_health_report` diagnosis → elastro command mapping

| ES diagnosis action (paraphrased) | elastro command |
|-----------------------------------|-----------------|
| Reroute/shard retry | `elastro health assess --fix` → `reroute_failed` |
| Adjust replica count | `elastro index fix` / smart replica |
| Clear allocation filters | `elastro health assess --fix` → `clear_routing_filters` |
| Enable shard routing | `elastro cluster settings --enable-routing all` |
| Free disk space / rollover | `elastro datastream rollover NAME` or ILM guidance |
| Verify snapshot repository | `elastro snapshot repo list` + verify |
| ILM policy correction | `elastro ilm explain INDEX` + `ilm create` |
| Increase shard limit | `elastro cluster settings` (new `--max-shards-per-node`) |

This mapping table is maintained in `elastro/health/remediation/catalog.py` as the single source of truth.