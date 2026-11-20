# Elastro CLI live-test backlog

| Field | Value |
|---|---|
| Date | 2026-11-20 |
| Elastro | **1.14.0** installed from local `main` (`e092360`, pipx + Python 3.13.5) |
| Previous install | pipx `elastro-client` **1.13.1** |
| Target cluster | Lima k3s `elastic-telemetry` ES 8.19.25 (`docker-cluster`, 2 nodes, **green**, 247 shards) |
| Access | `kubectl -n elastic-telemetry port-forward svc/elasticsearch 9205:9200` (NodePort 30920 is not reachable from this Mac). Default `~/.elastic/config.yaml` password does **not** match Lima; tests used a 0600 temp config. |
| Result | **Live tests ran.** 54 CLI commands: **41 exit 0**, **13 non-zero**. Scratch index `elastro-cli-smoke-20261120` created and force-deleted. |

Evidence: `/tmp/elastro_lima_live.jsonl` (live) and `/tmp/elastro_cli_matrix.jsonl` (offline).

---

## Live results (2026-11-20, cluster up)

Access path that worked:

```bash
kubectl --kubeconfig ~/.kube/config-lima-k3s -n elastic-telemetry \
  port-forward --address 127.0.0.1 svc/elasticsearch 9205:9200
kubectl --kubeconfig ~/.kube/config-lima-k3s -n elastic-telemetry \
  port-forward --address 127.0.0.1 svc/kibana 5601:5601
```

ES: `elasticsearch-0`, cluster `docker-cluster`, version **8.19.25**, health **green**. Kibana `/api/status` **available**.

### Passed (exit 0)

`health status|nodes|shards|ilm|hotspots|lint|trends|report`, `health assess --feature apm`, `health assess --feature beats`, `health rollback list`, `coverage templates list`, `coverage templates apply --dry-run` (apm-traces, filebeat), `coverage check --pattern filebeat-*`, `coverage check --pattern traces-apm*`, `index list|find|create|exists|get|delete --dry-run|--force`, `doc index|get`, `ilm list|explain`, `template list`, `datastream list`, `cluster settings`, `security users|roles`, `tasks list`, `script list`, `snapshot repo list`, `ingest pipelines`, `utils health|templates|aliases`, `esql query 'FROM * | LIMIT 1'`, `daemon status`.

Scratch index create/index/get/delete worked end to end.

### Non-zero (classified)

| Command | rc | Classification |
|---|---|---|
| `health score` / `health assess` | 2 | **Expected FailOn.** Score 67, findings: `cluster.block.indices` (FAIL/critical), `shards.oversharded` (WARN), `security.tls.plain_http` (WARN). Cluster is green but Elastro degrades on a block + oversharding. |
| `health assess --feature disk` | 2 | **Bug (COV-6).** Score 47 FAIL. Output still includes `security.tls.plain_http`. `--feature disk` is not isolating to disk; it also looks worse than default assess (67). |
| `coverage templates apply apm-traces` (no `--yes`) | 2 | **Expected** confirm gate. Did not PUT. |
| `coverage check --all` | 2 | **Product/gate.** traces-apm* and filebeat-* have fresh docs; fails because `metricbeat-*`, `logs-filebeat*`, `metrics-metricbeat*` are absent on this cluster. `--all` is a full APM+Beats AND-gate. |
| `coverage check --service elasticsearch --window 24h` | 2 | **Bug (COV-7).** Matched 14 APM data streams by name, then 0 docs with `service.name=elasticsearch`. Wrong service for this cluster; also `--service` should not treat APM stream names as a hit if the term filter finds no docs. |
| `coverage report` | 2 | Follows `--all` failure + templates not applied (`applied: false` for elastro-* templates). |
| `coverage fleet status\|agents` | 2 | **Expected.** Fleet disabled in config. Still pings ES first (CLI-2). |
| `doc search INDEX --query '*'` | 2 | **Bug (CLI-8).** `--query` is not a flag (`Did you mean --term?`). Help/examples still show `--query` in some places. |
| `cluster allocation` | 1 | **Bug (CLI-9).** Green cluster with 0 unassigned shards: ES 400 `No shard was specified`. Should succeed with “nothing to explain” instead of exit 1. |
| `memory search` / `tools search` | 1 | **Bug (CLI-10).** Missing `agent_semantic_memory` / `flow_tools` raises raw `NotFoundError` stack + exit 1. Empty result would be correct on a cluster that does not use agent indices. |

### Coverage field-presence bug (COV-8)

On `coverage check --all`, a passing filebeat group reported:

`field_presence: service.name=0, host.name=35757 of 2 docs`

Two documents in the 15m window, but `host.name` agg count is 35757. The field-presence aggregations are not scoped to the same window/query as `doc_count`.

### `--feature apm` hides cluster FAILs

`health assess --feature apm` exited 0 with `overall_score: 100`, `findings: []`, while default assess still has `cluster.block.indices` FAIL. Filtering is working for APM-only view; operators can think the cluster is healthy. Document this, or keep global FAIL findings visible.

---

## P0 — Lima cluster access (updated)

The configured Elastro profile points at `http://localhost:9205`. Nothing is listening on `9200` or `9205`. `elastro health status` exits **1** with `Failed to connect to Elasticsearch (host unreachable)`.

Lima/k3s (second pass, cluster up):

| Probe | Result |
|---|---|
| lima-k3s kube API `https://192.168.0.179:6443` | up (401 without kubeconfig; kubectl works) |
| ES NodePort `192.168.0.179:30920` | **not reachable** from this Mac |
| `kubectl port-forward svc/elasticsearch 9205:9200` | works |
| Default `~/.elastic/config.yaml` | **HTTP 401** against Lima (password mismatch) |
| `limactl` / `~/.lima` | still not installed on this workstation |

**Access backlog (LIMA-2):** document port-forward + kube secret `elastic-credentials` / `elastic-password`. Do not rely on localhost:9205 without the forwarder, and do not assume the laptop Elastro profile password is the Lima password.

---

## Install notes

- `pipx install --force --python python3.13 .` from this repo succeeded. `elastro --version` → `1.14.0`. New group `coverage` is on `--help`.
- PyPI `elastro-client` is still **1.13.1**. Anyone installing via `install.sh` / `pipx install elastro-client` will not get coverage, fail-closed CLI, or 1.14.0 until a release is published.

**Backlog:** cut a 1.14.0 GitHub/PyPI release (or document `pipx install git+https://github.com/Fremen-Labs/elastro.git`).

---

## Observed without a cluster (still real bugs / UX)

These showed up in the 122-command matrix. Help always exit 0. Live ES commands exit 1 on connect, which is the intended fail-closed path.

### B1. Root callback pings ES on every invocation, including `--help`

64 of 65 `--help` runs logged a failed ping to `localhost:9205`. `elastro coverage --help`, `elastro health assess --help`, even missing Click arguments (`index find`, `snapshot list`) still connect first.

`config list`, `coverage templates list`, `coverage templates apply --dry-run`, `memory prune --dry-run`, `health rollback list`, `esql build`, and `daemon status` all **succeed** without ES, but they still log a connect **ERROR** first.

`coverage fleet status` talks only to Kibana and still pings Elasticsearch before printing `Fleet is disabled...` (exit 2).

**Wanted:** skip `connect()` for `--help`, `config`, `gui`, `daemon`, Fleet, and dry-run/local paths. Store the error on `ctx.meta` without logging ERROR until a command actually needs the client (`require_client`).

### B2. ASCII art on every `--help`

Stdout for help is ~4KB of banner plus usage. Scripts that scrape `--help` get the art. Root `--help` was the only help that did **not** also ping ES (fast path?).

**Wanted:** banner on interactive TTY only, or `ELASTRO_NO_ART=1`.

### B3. Connect logs are noisy and include auth shape

Every command logs:

```
Connecting with params: hosts=[...], auth={'type': 'basic', 'username': 'elastic', 'password': '******', 'api_key': '******'}, basic_auth=('elastic', '******')
```

Password is masked. Username is not. `INFO` on every CLI start is loud for operators and for `coverage --help`.

**Wanted:** log host (userinfo stripped) at DEBUG; never log `basic_auth` tuples.

### B4. Click usage (exit 2) after a failed ping

`elastro index find` (missing `PATTERN`) and `elastro snapshot list` (missing `REPOSITORY`) exit 2 as Click usage, but only after the connect ERROR. The usage text is buried under logs + ASCII art.

**Wanted:** validate args before connect, or do not connect until the subcommand runs.

### B5. `painless scaffold` is not a clean non-TTY command

Non-interactive run prints the wizard, then `Aborted.` First matrix run exited 1; a later `/dev/null` run exited 0. Local scaffold should not need ES (it still pings). Non-TTY should exit 2 with “interactive wizard requires a TTY” like `ml init-job`.

### B6. Mutations without `--yes`

Covered well for `coverage templates apply`, `memory prune`, `tasks cancel`, `script delete`, `cluster settings --enable-routing` (all exit 2).

`elastro ilm start` / `ilm stop` have **no** `--yes` and would mutate as soon as the cluster is up. Same class of gap as the uplift’s passthrough commands.

### B7. `index find` is only a required-pattern wrapper around `list`

Fine, but `--help` says “Wrapper for list”. Easy to call without a pattern and get usage 2 plus a connect error.

---

## New coverage commands (1.14.0) — what we could prove offline

| Command | Offline result | Notes |
|---|---|---|
| `coverage templates list` | exit 0 | Lists `apm-traces`, `apm-metrics`, `filebeat-logs`, `metricbeat-metrics` |
| `coverage templates apply apm-traces --dry-run` | exit 0 | Prints ILM + template JSON; no PUT |
| `coverage templates apply apm-traces` (no `--yes`) | exit 2 | Confirm gate works |
| `coverage check --all` / `--service` / `--pattern` | exit 1 | Connect fail (needs ES) |
| `coverage report` | exit 1 | Connect fail |
| `coverage fleet status` | exit 2 | Correct “Fleet is disabled” **after** ES ping noise |
| `coverage fleet agents` | exit 2 | Same |

**Needs live ES:** check freshness/doc counts, report combined with health, `templates apply --yes` on a scratch cluster, `--feature apm` vs default assess SKIPPED, Fleet against a real Kibana URL.

---

## Full command matrix (122 runs)

- All `--help` exit **0**.
- Connect-fail live commands exit **1** (fail-closed): `health assess|status|score|nodes|shards|ilm|hotspots|lint|trends|report`, `index list`, `ilm list|start`, `template list`, `datastream list`, `cluster allocation|settings`, `security users|roles`, `tasks list`, `script list`, `snapshot repo list`, `memory search`, `tools search`, `telemetry ingest`, `esql query`, `ingest pipelines`, `utils health|templates|aliases`.
- Usage / confirm / TTY exit **2**: `ml init-job`, `memory prune`, `coverage templates apply` (no yes), `tasks cancel`, `script delete`, `cluster settings --enable-routing all`, `index find`, `snapshot list`, `doc search` (query parse or usage), `coverage fleet *`.
- Offline success exit **0**: `config list`, `coverage templates list|apply --dry-run`, `memory prune --dry-run`, `health rollback list`, `esql build -s logs-*`, `daemon status`.

`gui` was only `--help` (no server started). `daemon start` was not run.

---

## Inefficiencies

1. **Eager connect** on the root Click callback: wasted ping + ERROR log on help, Fleet, dry-run, config.
2. **ASCII art** on help (~4KB) and many error paths.
3. **Cold start** ~250ms per process (122 cmds ≈ 30s). Fine for humans; noisy for scripts that call `elastro` in a loop. Daemon fast-path exists only for `doc search`.
4. **Health assess** on a live cluster still runs the full collector set; `--feature apm` filters findings after the fact (by design). Live retest should measure duration.
5. **`ilm start`** is a one-shot mutation with no preview.

---

## Backlog (prioritized)

| ID | Pri | Item |
|---|---|---|
| LIMA-1 | P0 | Done for this session (kube API up). Keep a documented port-forward. |
| LIMA-2 | P1 | NodePort 30920 not reachable from Mac; default Elastro profile 401s. Document `port-forward` + Lima secret vs laptop `config.yaml`. |
| REL-1 | P0 | Publish 1.14.0 to PyPI / update `install.sh` so `pipx install elastro-client` matches git main. |
| CLI-1 | P1 | Do not `connect()` until `require_client()`; never ERROR-log a failed ping on `--help`. |
| CLI-2 | P1 | Skip ES connect for Fleet (Kibana-only), `coverage templates list`, dry-run apply, `config *`. Confirmed live: fleet still pings ES. |
| CLI-3 | P2 | ASCII art on `--help`; `-o json health status` still prints a human banner line before JSON. |
| CLI-4 | P2 | Connect logs: host only, no username/`basic_auth` tuple; DEBUG not INFO. |
| CLI-5 | P2 | `painless scaffold` non-TTY → exit 2, no ES. |
| CLI-6 | P2 | `ilm start` / `ilm stop` get `--yes` / dry-run like other mutations. |
| CLI-7 | P3 | Click missing-arg (exit 2) should not ping ES first. |
| CLI-8 | P2 | `doc search` has no `--query` flag (`Did you mean --term?`). Fix help/examples. |
| CLI-9 | P2 | `cluster allocation` on a green cluster (0 unassigned shards) exits 1 with ES 400. Treat as empty success. |
| CLI-10 | P2 | `memory search` / `tools search` dump Elasticsearch 404 stack traces when agent indices are absent. Return empty + exit 0 or a one-line “index missing”. |
| COV-1 | P1 | `--all` AND-gate confirmed live: filebeat + traces pass; metricbeat / `logs-filebeat*` / `metrics-metricbeat*` fail this cluster. |
| COV-2 | P1 | Still open: `templates apply --yes` not run against Lima (would install templates over existing APM/Beats patterns). Use a scratch cluster. |
| COV-3 | P1 | Live: default assess FAIL (`cluster.block.indices`); `--feature apm`/`beats` exit 0 with score 100 and empty findings. Filter hides cluster FAILs. |
| COV-4 | P2 | `health.audit` still logs on `health assess`. `coverage report` was not separately verified for audit index writes. |
| COV-5 | P2 | Fleet not live-tested against Kibana (`enabled: false`). Need an API key. |
| COV-6 | P1 | `--feature disk` still emits `security.tls.plain_http` and FAIL score 47. Feature filter is leaky. |
| COV-7 | P1 | `--service elasticsearch` matched 14 APM streams then 0 docs. Service check should query `service.name` only, not treat stream names as coverage. |
| COV-8 | P1 | `field_presence` reported `host.name=35757 of 2 docs`. Aggregations are not scoped to the time window. |
| TEST-1 | P2 | Add a live CLI smoke job (gated) so Lima/CI can run this matrix. |

---

## Live retest checklist (when Lima answers)

```bash
elastro --version   # 1.14.0
elastro -o json health status
elastro -o table health assess
elastro health assess --feature disk
elastro health assess --feature apm
elastro health assess --feature beats
elastro coverage templates list
elastro coverage templates apply apm-traces --dry-run
# only on a scratch cluster:
elastro coverage templates apply apm-traces --yes
elastro coverage check --all
elastro coverage check --service <name> --window 15m
elastro -o json coverage report
elastro index list
elastro ilm list
elastro template list
elastro datastream list
elastro cluster settings
elastro security users
elastro tasks list
elastro snapshot repo list
```

Do not run `index delete`, `doc delete`, `snapshot restore`, or `ilm delete` against the shared Lima cluster without an explicit scratch prefix.
