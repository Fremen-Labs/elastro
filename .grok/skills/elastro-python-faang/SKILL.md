---
name: elastro-python-faang
description: >
  FAANG-synthesized Python engineering patterns for Elastro: typing, Pydantic
  models, error taxonomy, thin CLI, test pyramids, safe remediation, and
  incremental PRs. Use when implementing features, reviewing Elastro PRs, or
  refactoring health/remediation/core modules.
---

# Elastro Python Engineering (FAANG Threads)

Common threads across **Google** (Abseil/Fire), **Amazon** (AWS CLI/boto3), **Microsoft** (Azure CLI/Knack), **Netflix** (Dispatch/Metaflow), and **Meta** (Hydra/Instagram tooling).

## 1. Layered architecture

| Layer | Responsibility | Elastro path |
|-------|----------------|--------------|
| CLI | Args, exit codes, render | `elastro/cli/` |
| Domain | Business logic, models | `elastro/health/`, `elastro/core/` |
| Transport | ES client, retries | `elastro/core/client.py` |
| Config | Profiles, secrets | `elastro/config/` |

**No layer skipping:** CLI → domain → client, never CLI → raw `es.*` except legacy paths being migrated.

## 2. Types and models (Google + Amazon)

- Public APIs use **type hints** on all parameters and returns
- Wire formats use **Pydantic v2** (`elastro/health/models.py` pattern)
- Enums for fixed vocab: `Severity`, `FindingStatus`, `RemediationSafety`
- `Optional[X]` only when None is meaningful; prefer defaults on models

## 3. Error handling (AWS botocore pattern)

```python
try:
    return dict(self._es.cluster.health(**params))
except Exception as e:
    logger.error("Cluster health failed: %s", e, exc_info=True)
    raise OperationError(f"Failed to get cluster health: {e}") from e
```

- Domain exceptions: `OperationError`, `ValidationError`, `ElasticIndexError`
- CLI catches `OperationError` → message on stderr → `SystemExit(1)`
- Never swallow exceptions without logging

## 4. Logging (see `elastro-logging` skill)

- `logger = get_logger(__name__)` everywhere operational
- One package-level handler configuration
- LogLoom enrichment for Elastic-ingestible NDJSON

## 5. Testing pyramid (Netflix + Google)

| Tier | Target | Elastro |
|------|--------|---------|
| Unit | Pure logic, mappers, scoring | `tests/unit/health/` |
| Integration | CLI with mocks | `tests/integration/test_health_*.py` |
| Live | Real cluster, gated | `@pytest.mark.integration` + skip |

Aim for **fast unit tests** on every PR; live tests optional in CI.

## 6. Safe operations (SRE thread across FAANG)

- **Dry-run first:** preview API calls before mutate
- **Interactive confirm** for DESTRUCTIVE/CONFIRM tiers
- **Idempotent handlers:** `RemediationCatalog` single source of truth
- **Audit trail:** LogLoom node IDs on assess/fix paths (PR-3c will index)

## 7. Incremental delivery (Amazon two-pizza / PR DAG)

Follow `docs/health_assessment_implementation_plan.md` PR chain:

- Small PRs with acceptance criteria
- Backward-compatible shims (`elastro/utils/health.py` re-export)
- Version bump in `pyproject.toml` per shipped PR

## 8. Code style

- Match surrounding module — don't drive-by refactor
- **%-style** log formatting, not f-strings in logger calls
- Imports: stdlib → third-party → elastro
- No verbose docstrings on obvious helpers

## 9. Dependency discipline

- `rich-click` for CLI — not Typer/Fire (already chosen)
- `elasticsearch` official client — not raw requests
- Optional LogLoom — graceful import failure in `logger.py`

## 10. Review checklist

Before marking work complete:

- [ ] Types on new public functions
- [ ] Logging at INFO/DEBUG/ERROR appropriate layers
- [ ] Tests for happy path + one failure path
- [ ] CLI docstring example with global `-o` placement
- [ ] No secrets in logs or test fixtures
- [ ] `pytest` passes for touched packages

## Reference

See `references/faang-python-synthesis.md` for per-company sources and pattern mapping.