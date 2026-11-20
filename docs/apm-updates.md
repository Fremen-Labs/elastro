**Design Spec: Elastro Coverage & Readiness Module**
**Target:** Elastro Engineering Team
**Version:** 1.0
**Date:** 2026-11-19
**Owner:** Jonathan Doughty / Fremen Labs

### 1. Overview

Elastro is a Python library + CLI for Elasticsearch management. This spec adds a focused **Coverage & Readiness** capability so Elastro can support APM + Beats rollouts without becoming a full agent deployment tool.

The goal is to make Elastro excellent at the Elasticsearch side of observability coverage:
- Pre-built, opinionated ILM policies and index templates for APM traces/metrics and Beats data streams
- Post-deployment validation that expected data is arriving
- Health assessment extensions that surface APM/Beats-related risks
- Optional thin Fleet status helpers (read-only)

This keeps Elastro’s scope coherent and high-leverage for the 100-app APM + Beats engagement and future observability work.

### 2. Goals & Non-Goals

**Goals**
- Provide repeatable, automated checks that APM and Beats data is flowing after instrumentation.
- Ship opinionated, production-ready ILM policies and index templates for common APM/Beats patterns.
- Extend the existing Health Assessment framework with APM/Beats-aware rules.
- Offer a thin, optional Fleet API client for basic agent/policy status.
- Deliver clear CLI and Python API surfaces that can be used in pipelines or handoff documentation.

**Non-Goals**
- Deploying, configuring, or upgrading Beats or Elastic Agent (no SSH, package management, or service control).
- Replacing Ansible or Fleet.
- Full Fleet policy authoring or enrollment workflows.
- Real-time streaming or continuous monitoring agents.

### 3. Proposed Architecture

```
elastro/
├── coverage/                  # New package
│   ├── __init__.py
│   ├── validators.py          # Data arrival & freshness checks
│   ├── templates.py           # Pre-built ILM + index templates
│   ├── fleet.py               # Optional thin Fleet client
│   └── readiness.py           # Orchestrator (CLI entry)
├── health/                    # Existing – extend with new rules
│   └── rules/
│       └── apm_beats.py       # New APM/Beats-specific rules
└── cli/
    └── coverage.py            # New CLI group: `elastro coverage`
```

Existing components leveraged:
- `ElasticsearchClient`
- `HealthAssessor` + remediation/audit infrastructure
- `ILM` management (create, explain, list)
- Index / data stream managers
- CLI framework (Click)

### 4. Feature Details

#### 4.1 Pre-built ILM Policies & Index Templates

**CLI**
```bash
elastro coverage templates list
elastro coverage templates apply apm-traces --dry-run
elastro coverage templates apply metricbeat --policy-name custom-metrics
```

**Python API**
```python
from elastro.coverage.templates import TemplateManager

tm = TemplateManager(client)
tm.apply("apm-traces", dry_run=True)
tm.apply("filebeat-logs", ilm_policy_name="logs-30d")
```

**Initial templates (ship as YAML/JSON assets)**
- `apm-traces` – hot/warm/delete, rollover on size or age, suitable for traces-apm*
- `apm-metrics` – shorter retention, higher throughput
- `filebeat-logs` / `metricbeat-metrics` – standard Beats data stream patterns
- Configurable overrides for retention days, rollover size, and phase transitions

#### 4.2 Data Arrival & Freshness Validation

**CLI**
```bash
elastro coverage check --service my-app --window 15m
elastro coverage check --pattern "traces-apm*" --min-docs 100 --max-age 5m
elastro coverage check --all --output table
```

**Python API**
```python
from elastro.coverage.validators import CoverageValidator

v = CoverageValidator(client)
report = v.check_service("checkout-service", window="15m")
report = v.check_pattern("metrics-apm*", min_docs=50, max_age="10m")
```

**Checks**
- Document count in time window
- Most recent document timestamp (freshness)
- Presence of expected data streams / indices
- Basic field presence (e.g., `service.name`, `host.name`)
- Optional cardinality sanity (too many unique services?)

#### 4.3 Health Assessment Extensions

Add new rules under the existing Health Assessment framework:

- APM data stream missing or stale
- Beats index without active ILM
- High document rejection rate on APM indices
- Shard imbalance on high-volume APM/Beats indices
- ILM phase lag (indices stuck in hot)

These surface in `elastro health assess` and can be filtered with `--feature apm` or `--feature beats`.

#### 4.4 Optional Fleet Status Helpers (Thin)

Read-only, behind an explicit flag or separate command so it does not become a hard dependency.

**CLI**
```bash
elastro coverage fleet status
elastro coverage fleet agents --policy apm-apps
```

**Python API**
```python
from elastro.coverage.fleet import FleetClient

fc = FleetClient(kibana_url, api_key)
agents = fc.list_agents(policy_id="...")
```

Minimal surface only: agent list, last check-in, policy assignment, upgrade status. No enrollment or policy mutation in v1.

### 5. CLI Surface Summary

| Command | Purpose |
|---------|---------|
| `elastro coverage templates list` | Show available templates |
| `elastro coverage templates apply <name>` | Apply ILM + template (dry-run supported) |
| `elastro coverage check` | Validate data arrival / freshness |
| `elastro coverage report` | Combined readiness report (templates + checks + health) |
| `elastro coverage fleet status` | Optional Fleet agent overview |

All commands support `-o table|json|yaml` and `--dry-run` where applicable.

### 6. Configuration

Extend existing `elastic.yaml` / config system:

```yaml
coverage:
  default_window: 15m
  templates_path: ~/.elastic/templates   # optional override
  fleet:
    enabled: false
    kibana_url: https://kibana:5601
    api_key: ${FLEET_API_KEY}
```

### 7. Implementation Notes

- Reuse existing `HealthAssessor` collector/rule pattern for new APM/Beats rules.
- Templates stored as package data (YAML) so they can be versioned and overridden.
- Validation queries should use efficient range filters and `track_total_hits` carefully to avoid heavy load.
- Fleet client should be optional (import only when used) and use the official Fleet API endpoints.
- All new code must include unit tests (mocked ES) and at least one integration test against a local ES.
- Follow existing Elastro patterns: Pydantic models, rich CLI output, dry-run support, and audit logging where mutations occur.

### 8. Phasing

**Phase 1 (MVP – highest value for the engagement)**
- Pre-built ILM + index templates
- Basic `coverage check` (pattern + service freshness)
- 2–3 new health rules
- Documentation and examples

**Phase 2**
- Combined readiness report
- Fleet status helpers
- Additional templates and configurable overrides

### 9. Success Criteria

- An engineer can apply a production-ready APM ILM policy with one CLI command.
- Post-instrumentation validation of a service takes < 10 seconds and produces a clear pass/fail.
- Health assess surfaces APM/Beats-specific issues without custom scripting.
- The module does not require any host-level access or agent deployment logic.
- All new functionality is covered by tests and documented in the existing docs structure.

### 10. Out of Scope Reminders

- No SSH, Ansible generation, package installation, or service management.
- No full Fleet policy authoring.
- No continuous background monitoring process.

---