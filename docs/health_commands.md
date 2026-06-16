# Health Assessment Commands

Elastro's `health` command group provides scored cluster assessments, actionable findings, safe remediation, rollback, and optional audit/history indexing. Available since v1.4.x; rollback and audit indexing shipped in **v1.8.0**; unified remediation workflow (`health fix`, `assess --plan`) shipped in **v1.10.0**; monitoring exit codes and `--fail-on` shipped in **v1.11.0**; disk + ILM catalog remediations shipped in **v1.12.0**; fleet history trends and ES-backed GUI history shipped in **v1.13.0**.

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
| `--fix` | After assessment, run the unified remediation workflow |
| `--plan` | After assessment, show remediation runbook only (no mutations) |
| `--dry-run` | With `--fix`, preview API calls without executing |
| `--yes` | With `--fix`, auto-confirm CONFIRM-level actions |
| `--force` | With `--fix` and `--yes`, allow DESTRUCTIVE actions |
| `--index` | Limit fixes to an index pattern (with `--fix` / `--plan`) |
| `--action` | Limit fixes to one action: `reduce_replicas`, `reroute_failed`, `clear_routing_filters`, `ilm_retry`, `clear_read_only` |
| `--target-replicas` | Explicit replica target for `reduce_replicas` |
| `--history` / `--no-history` | Index report to `elastro-health-assessments` (default: off) |
| `--history-index` | Override assessment history index name |
| `--fail-on` | Exit `2` when health degrades past threshold (default: `fail`) |

**Examples:**

```bash
elastro health assess -o table
elastro health assess --feature disk -o json
elastro health assess --fix --dry-run -o table
elastro health assess --plan -o table
elastro health assess --history -o table
```

Exit code `2` when overall status is `fail` by default (`--fail-on fail`). Use `--fail-on warn` for stricter CI gates.

---

### `elastro health fix`

Unified remediation workflow for yellow/red indices. Diagnoses allocation issues, builds an ordered runbook, shows impact before each action, and captures rollback snapshots for index-setting changes.

```bash
elastro health fix [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--dry-run` | Preview planned API calls without executing |
| `--yes` | Auto-confirm CONFIRM-level actions (non-interactive) |
| `--force` | With `--yes`, allow DESTRUCTIVE actions |
| `--index` | Limit fixes to an index pattern |
| `--action` | Limit to one remediation action (`reduce_replicas`, `reroute_failed`, `clear_routing_filters`, `ilm_retry`, `clear_read_only`) |
| `--target-replicas` | Explicit replica target for `reduce_replicas` |

Remediation failures exit `3` when any executed action fails.

**Safety behavior:**

| Safety level | Interactive default | Non-interactive automation |
|--------------|---------------------|----------------------------|
| `CONFIRM` | Prompt (default No) | Requires `--yes` |
| `DESTRUCTIVE` | Prompt + type index name (default No) | Requires `--yes --force` |

**Examples:**

```bash
elastro health fix -o table
elastro health fix --dry-run -o table
elastro health fix --yes --action reroute_failed
elastro health fix --yes --force --index logs-*
elastro health fix --dry-run --action ilm_retry --index logs-000042
elastro health fix --yes --force --action clear_read_only --index logs-flood-*
```

`elastro index fix` remains available but prints a deprecation notice and delegates to this workflow.

---

### `elastro health ilm`

List indices with stuck or failed ILM lifecycle steps.

```bash
elastro health ilm [--stuck-only] [--index PATTERN]
```

| Option | Description |
|--------|-------------|
| `--stuck-only` | Focus output on ERROR or blocked ILM steps |
| `--index` | Limit to an index pattern |

**Examples:**

```bash
elastro -o table health ilm --stuck-only
elastro health ilm --index logs-* --stuck-only -o json
```

Pair with `elastro health fix --action ilm_retry --index <name>` to retry a failed step.

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
| `--fail-on` | Exit `2` when score/status/findings exceed threshold (default: `fail`) |

**Examples:**

```bash
elastro health score
elastro health score -o json
elastro health score --history --last 30 -o table
```

With `--history` and table output, Elastro renders a sparkline-friendly history table including a Unicode trend line across samples.

---

### `elastro health trends`

Analyze assessment history for score deltas, recurring findings, and persistent yellow signals.

```bash
elastro health trends [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--window` | History window such as `7d`, `24h`, or `30d` (default: `7d`) |
| `--cluster` | Limit to one cluster; omit for a fleet summary table |
| `--finding` | Filter recurring findings to a specific finding id |
| `--limit` | Maximum assessment samples to analyze (default: `50`) |
| `--history-index` | Override assessment history index name |

**Examples:**

```bash
elastro health trends -o table
elastro health trends --cluster docker-cluster --window 30d
elastro health trends --finding shards.oversharded --window 30d -o json
```

When no history index documents exist, the command returns guidance to run `elastro health assess --history` first.

---

### `elastro health rollback`

Manage remediation rollback snapshots.

```bash
elastro health rollback list [--last 20]
elastro health rollback apply --id ROLLBACK_ID [--dry-run]
```

| Subcommand | Description |
|------------|-------------|
| `list` | Show recent rollback snapshots (`--last` default 20) |
| `apply` | Restore settings from a snapshot (`--dry-run` to preview) |

**Examples:**

```bash
elastro health rollback list -o table
elastro health rollback apply --id rb-550e8400-e29b-41d4-a716-446655440000 --dry-run
elastro health rollback apply --id rb-550e8400-e29b-41d4-a716-446655440000
```

Rollback files are stored locally at `~/.elastic/health-rollbacks/` with `0600` permissions. Each successful remediation that modifies index settings returns a `rollback_id` in CLI JSON output and API fix responses.

---

### `elastro health status`

Replacement for `elastro utils health`. Checks cluster, indices, or shard-level health.

```bash
elastro health status [--level cluster|indices|shards] [--wait green|yellow|red] [--timeout 30s] [--fail-on fail]
```

`--wait` exits `2` on timeout or if the cluster never reaches the requested status.

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

`--fail-on warn` (default `fail`) exits `2` when `unassigned_shards > 0`.

---

### `elastro health hotspots`

Detects per-node JVM, disk, and CPU variance hotspots (alias for `health nodes --hotspots`).

```bash
elastro health hotspots [--variance 30]
```

---

### `elastro health lint`

Best-practice linter for index settings, mapping field counts, and shard layout. Shipped in **v1.9.0**.

```bash
elastro health lint [--category settings|mappings|shards|security] [--index PATTERN] [--timeout 30s]
```

| Option | Description |
|--------|-------------|
| `--category` | Category to lint; repeatable (default: all) |
| `--index` | Limit settings/mappings/shard analysis to an index pattern |
| `--max-indices` | Cap indices scanned for settings/mappings (default: 50) |
| `--timeout` | Per-request timeout |
| `--fail-on` | Exit `2` on lint findings past threshold (default: `fail` = fail-level only) |

**Examples:**

```bash
elastro health lint -o table
elastro health lint --category mappings --category shards -o json
elastro health lint --category shards --index logs-* -o table
```

Exit codes: `0` when clean (or only warnings with default `--fail-on fail`), `1` on operational errors, `2` when findings exceed `--fail-on` (use `--fail-on warn` to fail on warnings).

Lint checks include:

| Category | Examples |
|----------|----------|
| `settings` | Zero replicas, aggressive refresh on large indices, high primary shard counts on small indices |
| `mappings` | Field counts approaching `index.mapping.total_fields.limit` |
| `shards` | Unassigned, oversharded, and undersharded shards |
| `security` | Plain HTTP connections, enabled `elastic` user, elevated RBAC roles |

Security posture checks also run during `health assess` via the security collector.

---

## Exit codes (v1.11.0+)

| Code | Meaning |
|------|---------|
| `0` | Success; health meets `--fail-on` threshold |
| `1` | Operational error (connection failure, collector error) |
| `2` | Health degraded per `--fail-on` |
| `3` | Remediation partial failure (`health fix` / `assess --fix` only) |

When both health degradation (`2`) and remediation failure (`3`) apply (e.g. `assess --fix`), exit `2` takes precedence so health gates still fail.

### `--fail-on` thresholds

| Value | Exits `2` when |
|-------|----------------|
| `fail` (default) | Overall status `fail`, fail-level findings, cluster `red`, or score &lt; 50 |
| `warn` | Any `warn`/`fail` finding, unassigned shards, or stricter than `fail` |
| `yellow` | Score &lt; 90, cluster `yellow`/`red`, or stricter than `warn` |
| `green` | Score &lt; 90, any warn/fail finding, cluster not `green`, or unassigned shards |

**CI examples:**

```bash
# Fail the job on warnings (paging threshold)
elastro health assess --fail-on warn -o json

# Lint gate: fail-level issues only (default)
elastro health lint -o json

# Stricter lint gate
elastro health lint --fail-on warn -o json

# Wait for green or fail
elastro health status --wait green --timeout 120s
```

---

## Remediation and rollback workflow

1. Run `elastro health fix` (or `elastro health assess --plan` to preview, `elastro health assess --fix` to fix after assessment).
2. Before applying, Elastro captures relevant index settings (replicas, routing filters, etc.).
3. The remediation executes; the result includes a `rollback_id` when a snapshot was saved.
4. If the fix was incorrect, run `elastro health rollback apply --id <rollback_id>`.

Supported automated actions (via `RemediationCatalog`):

| Action | Use case |
|--------|----------|
| `reduce_replicas` | Yellow index with unassigned replicas |
| `reroute_failed` | Force retry of failed shard allocation |
| `clear_routing_filters` | Remove custom node routing allocation filters |
| `ilm_retry` | Retry a stuck ILM lifecycle step (`CONFIRM`) |
| `clear_read_only` | Clear flood-stage `read_only_allow_delete` block (`DESTRUCTIVE`) |

Disk findings suggest `elastro cluster settings` to review watermarks. Flood-stage indices with read-only blocks surface `clear_read_only` remediation hints during assessment.

Use `--dry-run` on assess or rollback to preview changes without mutating the cluster.

### Scriptable dry-run (v1.10.0+)

Dry-run is **preview-only**: no index settings change, no cluster reroute, no rollback snapshot writes, and no audit documents indexed to Elasticsearch. Diagnostics (cat indices, allocation explain) are read-only cluster calls.

**Recommended scripting paths:**

```bash
# Preview remediation runbook as JSON
elastro -o json health fix --dry-run

# Preview rollback restore
elastro -o json health rollback apply --id rb-... --dry-run

# Assessment + runbook without mutations
elastro -o json health assess --plan
```

JSON output for `health fix --dry-run` includes:

| Field | Meaning |
|-------|---------|
| `dry_run` | Always `true` |
| `summary.preview_only` | `true` when no mutations will occur |
| `summary.executed_count` | Always `0` in dry-run |
| `planned_actions[].planned_api_call` | Exact API preview per step |
| `results[].planned_api_call` | Same preview echoed per result |

Rollback dry-run JSON includes `planned_api_call` with the `PUT /{index}/_settings` body that would be restored.

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
| `GET` | `/api/clusters/{name}/health/history` | Assessment history (ES index when `health.assessment.enable_history=true`, merged with cache) |
| `GET` | `/api/clusters/{name}/health/trends` | Trend report JSON for sparkline display (`?window=7d`) |
| `GET` | `/api/clusters/{name}/health/nodes` | Node stats summary |
| `POST` | `/api/clusters/{name}/health/fix` | Apply remediation; returns `rollback_id` |
| `POST` | `/api/clusters/{name}/indices/{index}/fix` | Index-level fix; returns `rollback_id` |

---

## Deprecations

`elastro utils health` remains available but prints a deprecation notice pointing to `elastro health status`. Prefer the `health` command group for new workflows.