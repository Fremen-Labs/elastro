# FAANG Python Engineering Synthesis

Research date: 2026-06-15. Focus: production Python suitable for operator CLIs like Elastro.

## Per-company contributions

### Amazon (AWS)
- **aws-cli / botocore**: Session object owns credentials; operations raise structured ClientError; logging at module level.
- **aws-sam-cli**: Click commands; clear separation of `commands/` vs `lib/`.
- **Lambda Powertools**: Structured logging, tracing, idempotent handlers — maps to future `health/audit.py`.

**Thread:** thin CLI, fat library, typed errors, module logger.

### Google
- **python-fire**: Docstring examples ARE the CLI contract.
- **abseil-py**: `app.run(main)`; flags; logging module integration.
- **OpenTelemetry** patterns (industry-wide with Google leadership): correlate logs with trace IDs — Elastro uses LogLoom node IDs similarly.

**Thread:** docstring-driven UX, single entrypoint, observable operations.

### Microsoft
- **knack**: Package-level logging config; verbosity flags; stderr discipline.
- **azure-cli-core/azlogging**: Suppress noisy third-party loggers (Netflix does same for `slack_sdk`).

**Thread:** central logging config; tune library log levels.

### Netflix
- **dispatch**: `configure_logging()` once; SQLAlchemy services; Click groups mirror domain boundaries.
- **metaflow**: Step decorators with explicit logging; fail-fast with context.
- **weep**: Small focused CLI for credentials — single responsibility commands.

**Thread:** domain command groups; configure logging at CLI boundary; service layer.

### Meta
- **Hydra**: Config composition before run; logging configured at startup.
- **Instagram engineering** (public posts): structured metrics + log correlation at scale.

**Thread:** configure once at startup; compose config before execute.

### Apple
- Minimal public Python operator tooling. Elastro follows **CPython stdlib + community best practice** (PEP 8, typing, pytest) as the stand-in.

## Cross-FAANG pattern matrix → Elastro mapping

| Pattern | Elastro implementation |
|---------|------------------------|
| Module logger | `get_logger(__name__)` |
| Central config | `configure_logging()` in `cli.main()` |
| Domain models | Pydantic in `health/models.py` |
| Error taxonomy | `core/errors.py` |
| Command groups | `cli/commands/*.py` |
| Safe mutation | `RemediationExecutor` dry-run + confirm |
| Collector pipeline | `CollectorRegistry` (plugin-like registry) |
| Version gating | `health/version.py` + collector skip |
| Test pyramid | unit → integration (mock) → live (skip) |

## Logging coverage standard (this PR)

Operational modules added since PR-1 must include:

1. `health/remediation/*` — scan, diagnose, execute
2. `health/manager.py` — all ES API wrappers
3. `cli/commands/health.py` — assess/fix entry
4. `health/collectors/base.py` — per-collector timing at DEBUG

## Skills in this repo

| Skill | Use when |
|-------|----------|
| `elastro-logging` | Adding logs, reviewing coverage |
| `elastro-python-cli` | New commands, CLI refactors |
| `elastro-python-faang` | General feature work, PR review |