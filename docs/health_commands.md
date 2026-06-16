# Health Assessment Commands

Elastro's `health` command group provides scored cluster assessments, actionable findings, safe remediation, rollback, and optional audit/history indexing. Available since v1.4.x; rollback and audit indexing shipped in **v1.8.0**.

For the full implementation plan and PR history, see [health_assessment_implementation_plan.md](./health_assessment_implementation_plan.md).

---

## Quick start

```bash
# Full assessment with table output (recommended)
elastro health assess -o table

# Score only (fast; skips verbose _health_report)
elastro health score

# Classic cluster status (replaces elastro utils health)
elastro health status
```

---

## Commands

### `elastro health assess`

Runs collectors and rules, computes a 0–100 score, and prints findings.

```bash
elastro health assess [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--timeout` | Per-collector timeout (default: `30s`) |
| `--feature` | Limit `_health_report` to one indicator; repeatable |
| `--verbose-report` / `--no-verbose-report` | Request verbose root-cause analysis (default: on) |
| `--include-raw` | Include raw `_health_report` in JSON/YAML output |
| `--fix` | After assessment, offer interactive index remediations |
| `--dry-run` | With `--fix`, preview API calls without executing |
| `--history` / `--no-history` | Index report to `elastro-health-assessments` (default: off) |
| `--history-index` | Override assessment history index name |

**Examples:**

```bash
elastro health assess -o table
elastro health assess --feature disk -o json
elastro health assess --fix --dry-run -o table
elastro health assess --history -o table
```

Exit code `2` when overall status is `fail` (score band red).

---

### `elastro health score`

Prints the current cluster health score without full table formatting.

```bash
elastro health score [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--timeout` | Per-collector timeout when re-assessing (default: `30s`) |
| `--history` | Read scores from the assessment history index instead of re-assessing |
| `--last` | Number of historical records to show with `--history` (default: `10`) |
| `--history-index` | Override assessment history index name |

**Examples:**

```bash
elastro health score
elastro health score -o json
elastro health score --history --last 5 -o table
```

---

### `elastro health rollback`

Restores index settings from a snapshot taken immediately before a remediation ran.

```bash
elastro health rollback --id ROLLBACK_ID [--dry-run]
```

| Option | Description |
|--------|-------------|
| `--id` | Rollback snapshot id (e.g. `rb-abc123-...`) |
| `--dry-run` | Preview restored settings without applying |

**Examples:**

```bash
elastro health rollback --id rb-abc123 --dry-run
elastro health rollback --id rb-abc123
```

Rollback files are stored locally at `~/.elastic/health-rollbacks/` with `0600` permissions. Each successful remediation that modifies index settings returns a `rollback_id` in CLI JSON output and API fix responses.

---

### `elastro health status`

Replacement for `elastro utils health`. Checks cluster, indices, or shard-level health.

```bash
elastro health status [--level cluster|indices|shards] [--wait green|yellow|red] [--timeout 30s]
```

---

### `elastro health report`

Raw `_health_report` passthrough with Elastro formatting.

```bash
elastro health report [--feature NAME] [--verbose] [--size N]
```

---

### `elastro health nodes`

Per-node JVM, filesystem, and circuit-breaker stats.

```bash
elastro health nodes [--node-id ID] [--metric jvm,fs,os,breaker] [--hotspots]
```

---

### `elastro health shards`

Shard allocation summary and optional size analysis.

```bash
elastro health shards [--index NAME] [--analyze] [--explain]
```

`--analyze` reports oversharded (`< 1 MB`) and undersharded (`> 50 GB`) shard counts.

---

### `elastro health hotspots`

Detects per-node JVM, disk, and CPU variance hotspots (alias for `health nodes --hotspots`).

```bash
elastro health hotspots [--variance 30]
```

---

## Remediation and rollback workflow

1. Run `elastro health assess --fix` (or `elastro index fix`) and confirm a suggested action.
2. Before applying, Elastro captures relevant index settings (replicas, routing filters, etc.).
3. The remediation executes; the result includes a `rollback_id` when a snapshot was saved.
4. If the fix was incorrect, run `elastro health rollback --id <rollback_id>`.

Supported automated actions (via `RemediationCatalog`):

| Action | Use case |
|--------|----------|
| `reduce_replicas` | Yellow index with unassigned replicas |
| `reroute_failed` | Force retry of failed shard allocation |
| `clear_routing_filters` | Remove custom node routing allocation filters |

Use `--dry-run` on assess or rollback to preview changes without mutating the cluster.

---

## Audit and assessment history

Every assess and fix operation emits structured events to stderr (LogLoom-enriched when LogLoom is installed). When an Elasticsearch client is available, events are also indexed.

| Index | Purpose | Default name |
|-------|---------|--------------|
| Assessment history | Stored assessment reports when `--history` is used | `elastro-health-assessments` |
| Audit | Assess, fix, and rollback events | `elastro-health-audit` |

Indices are created automatically with bundled mappings when first written.

**Configuration** (`~/.elastic/config.yaml` or `elastro config set`):

```yaml
health:
  assessment:
    timeout: 30s
    verbose_report: true
    cache_ttl_seconds: 60
    history_index: elastro-health-assessments
    audit_index: elastro-health-audit
    enable_history: false
```

```bash
elastro config get health.assessment.history_index
elastro config get health.assessment.audit_index
```

Audit payloads include cluster metadata, session id, action id, index name, and rollback id. Credentials are never written to audit documents.

---

## GUI API endpoints

The local GUI uses the same assessment and remediation stack:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/clusters/{name}/health/assess` | Full assessment |
| `GET` | `/api/clusters/{name}/health/score` | Cached score (60s TTL) |
| `GET` | `/api/clusters/{name}/health/findings` | Open findings from cache |
| `GET` | `/api/clusters/{name}/health/history` | In-memory assessment history |
| `GET` | `/api/clusters/{name}/health/nodes` | Node stats summary |
| `POST` | `/api/clusters/{name}/health/fix` | Apply remediation; returns `rollback_id` |
| `POST` | `/api/clusters/{name}/indices/{index}/fix` | Index-level fix; returns `rollback_id` |

---

## Deprecations

`elastro utils health` remains available but prints a deprecation notice pointing to `elastro health status`. Prefer the `health` command group for new workflows.