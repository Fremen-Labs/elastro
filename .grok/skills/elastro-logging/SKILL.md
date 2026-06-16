---
name: elastro-logging
description: >
  Enforce Elastro logging standards: get_logger(__name__), package-level handler
  configuration, LogLoom enrichment, stderr-only diagnostics, and coverage for
  operational paths (collectors, remediation, managers, CLI commands). Use when
  adding or reviewing Elastro code, doing a logging coverage pass, or when the
  user mentions logs, observability, LogLoom, or ELASTRO_LOG_LEVEL.
---

# Elastro Logging Standards

Apply these rules whenever you touch Elastro Python code.

## Setup (mandatory)

```python
from elastro.core.logger import get_logger

logger = get_logger(__name__)
```

- **Never** call `print()` for operational/diagnostic output in library code.
- **Never** attach handlers to child loggers — handlers live on the `elastro` package logger only.
- CLI user-facing tables/banners use `click.echo` / Rich; everything else uses `logger`.

## Level guide (aligned with Azure Knack + Netflix Dispatch)

| Level | When to use in Elastro |
|-------|------------------------|
| `DEBUG` | ES API params, per-collector timing, per-index diagnosis, formatter internals |
| `INFO` | Command entry, assessment start/complete, remediation dry-run/execute, connection success |
| `WARNING` | Collector soft-fail, skipped remediation, recoverable ES errors, version gating |
| `ERROR` | Exceptions before re-raising `OperationError`; always `exc_info=True` |
| `CRITICAL` | Process cannot continue (rare in CLI) |

## Required coverage by layer

| Layer | Must log |
|-------|----------|
| `elastro/core/*` managers | DEBUG on request; ERROR with `exc_info` on failure |
| `elastro/health/collectors/*` | DEBUG per collector; WARNING on collector error |
| `elastro/health/assessor.py` | INFO start + complete with score/findings count |
| `elastro/health/remediation/*` | INFO for scan/execute/dry-run; WARNING on unknown action |
| `elastro/cli/commands/*` | INFO on command entry with key flags (not secrets) |
| `elastro/server/routes/*` | ERROR on 500 paths; DEBUG on fix/assess API calls |

## Message format

- Use **%-style** lazy formatting: `logger.info("score=%s findings=%s", score, n)`
- Include **structured context**: cluster, index, action_id, collector name, duration_ms
- **Never log** passwords, API keys, or full auth tuples — redact like existing client logs

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `ELASTRO_LOG_LEVEL` | `INFO` | Console + file level |
| `ELASTRO_LOG_FILE` | `elastro.log` | Rotating text log |
| `ELASTRO_LOGLOOM_FILE` | `elastro-logloom.ndjson` | LogLoom-enriched JSON |

Suppress CLI noise for demos: `export ELASTRO_LOG_LEVEL=ERROR`

## Checklist before finishing a PR

1. New module with I/O or branching → `get_logger(__name__)` added
2. Every `except` that re-raises → `logger.error(..., exc_info=True)` first
3. Long-running orchestration → INFO at start and end with timing/counts
4. Run `pytest tests/unit/core/test_logger.py` and relevant health tests
5. Confirm logs go to **stderr** (stdout reserved for CLI data output)

## Anti-patterns (reject in review)

- Per-module `logging.basicConfig()` or duplicate handlers
- `logging.getLogger()` without going through `elastro.core.logger`
- Logging inside tight loops at INFO (use DEBUG or aggregate)
- Mixing user-facing remediation results into logs only — still render via CLI