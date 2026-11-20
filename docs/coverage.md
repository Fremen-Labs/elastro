# Coverage & Readiness

Elastro’s `coverage` group validates the Elasticsearch side of APM and Beats rollouts: opinionated ILM + index templates, post-instrumentation data arrival checks, APM/Beats health rules, and an optional read-only Fleet status helper.

It does **not** deploy agents, enroll Fleet policies, or SSH to hosts.

## CLI

Global `-o json|yaml|table` is on the root group.

```bash
# List shipped templates
elastro coverage templates list

# Preview ILM + template bodies (no cluster writes)
elastro coverage templates apply apm-traces --dry-run

# Apply (non-interactive)
elastro coverage templates apply metricbeat --policy-name custom-metrics --yes

# Data arrival / freshness
elastro coverage check --service my-app --window 15m
elastro coverage check --pattern "traces-apm*" --min-docs 100 --max-age 5m
# --all is a full APM+Beats gate: every default pattern must pass
elastro -o table coverage check --all

# Combined readiness report
elastro -o json coverage report

# Optional Fleet (requires coverage.fleet.enabled: true plus kibana_url + api_key)
elastro coverage fleet status
elastro coverage fleet agents --policy apm-apps
```

Exit codes: `0` success (or all checks pass); `1` operational failure; `2` usage error or a failed coverage/readiness check. Declining an interactive apply confirm exits `0`.

`elastro health assess --feature apm` and `--feature beats` filter custom APM/Beats findings. They are **not** passed to Elasticsearch `_health_report` (unlike `--feature disk`).

## Python API

```python
from elastro import ElasticsearchClient
from elastro.coverage.templates import TemplateManager
from elastro.coverage.validators import CoverageValidator
from elastro.coverage.readiness import ReadinessReporter

client = ElasticsearchClient()
client.connect()

tm = TemplateManager(client)
tm.apply("apm-traces", dry_run=True)
tm.apply("filebeat-logs", ilm_policy_name="logs-30d")

v = CoverageValidator(client)
report = v.check_service("checkout-service", window="15m")
report = v.check_pattern("metrics-apm*", min_docs=50, max_age="10m")

ready = ReadinessReporter(client).report(window="15m")
```

Fleet is imported only when used:

```python
from elastro.coverage.fleet import FleetClient

fc = FleetClient(kibana_url, api_key)
agents = fc.list_agents(policy_id="...")
```

## Configuration

```yaml
coverage:
  default_window: 15m
  templates_path: null   # optional directory of extra YAML templates
  fleet:
    enabled: false
    kibana_url: null
    api_key: null        # or ELASTIC_COVERAGE_FLEET_API_KEY
```

Set `coverage.fleet.enabled: true` before `elastro coverage fleet …`. Env overrides use the existing `ELASTIC_` path, for example `ELASTIC_COVERAGE_FLEET_API_KEY` and `ELASTIC_COVERAGE_FLEET_KIBANA_URL`. The API key is never logged.

`elastro coverage check --all` (and the default `elastro coverage report` coverage section) is a **full APM+Beats gate**: every default pattern must pass — APM `traces-apm*`, `metrics-apm*`, `logs-apm*`, classic Beats `filebeat-*` / `metricbeat-*`, and data-stream Beats `logs-filebeat*` / `metrics-metricbeat*`. Use `--pattern` or `--service` when you only instrumented one group.

Shipped templates: `apm-traces`, `apm-metrics`, `filebeat-logs` (alias `filebeat`, pattern `logs-filebeat*`), `metricbeat-metrics` (alias `metricbeat`, pattern `metrics-metricbeat*`). They use priority `100` (below typical Fleet/integration templates), omit replica counts, and do **not** match classic `filebeat-*` / `metricbeat-*` daily indices. `apply` is for clusters without Fleet-managed APM/Beats templates; do not apply on top of Elastic Agent integrations. Overrides: `--retention-days`, `--rollover-size`, `--hot-max-age`, `--warm-min-age`, `--policy-name`.

`elastro coverage report` is read-only: it does not write `elastro-health-audit`.
