# FAANG Python CLI Synthesis for Elastro

Research date: 2026-06-15. Sources are open-source repos and public engineering docs.

## Companies surveyed

| Company | Representative OSS | CLI stack | Key pattern |
|---------|---------------------|-----------|-------------|
| **Amazon** | [aws-cli](https://github.com/aws/aws-cli) | Custom driver + botocore | `LOG = logging.getLogger(__name__)`; layered command table; plugin events |
| **Microsoft** | [azure-cli](https://github.com/azure/azure-cli) + [knack](https://github.com/microsoft/knack) | Knack on Click | stderr logging; `--verbose`/`--debug`; `get_logger(__name__)` |
| **Google** | [python-fire](https://github.com/google/python-fire) + [abseil-py](https://github.com/abseil/abseil-py) | Fire / Abseil app | Docstring-driven CLI; centralized `app.run()`; flags module |
| **Netflix** | [dispatch](https://github.com/Netflix/dispatch) | Click | `configure_logging()` at group entry; `log = logging.getLogger(__name__)` |
| **Meta** | [Hydra](https://hydra.cc/) (FAIR) | Hydra + Click plugins | Composable config; logging configured in `@hydra.main` |
| **Apple** | Limited public Python CLI | — | No major OSS operator CLI; adopt stdlib + Click norms |

## Convergent threads (use in Elastro)

### 1. Stdlib logging, not print
All mature CLIs use `logging.getLogger(__name__)` with centralized configuration. User-visible styled output is separate (Click `secho`, Rich tables).

### 2. stderr for diagnostics
Knack explicitly documents: all log messages → stderr. Elastro's `get_logger` uses `StreamHandler(sys.stderr)`.

### 3. Command composability
- AWS: `aws <service> <operation>` with shared session
- Azure: `az <group> <command>` with knack context
- Elastro: `elastro -h HOST -o table health assess` — global opts on root group

### 4. Thin command handlers
Netflix Dispatch commands delegate to `service` modules after `configure_logging()`. Elastro mirrors this: `HealthAssessor`, `RemediationExecutor`.

### 5. Testability via CliRunner
Click's `CliRunner` is the common test harness across Netflix, Click ecosystem, and Elastro integration tests.

### 6. Dry-run / confirm for mutations
AWS IAM-style dry-run flags; Elastro `--fix --dry-run` for remediation preview.

## Elastro-specific adaptations

- **rich-click** for markdown docstrings (better than raw Click help)
- **LogLoom** NDJSON enrichment (beyond typical FAANG stdout logging)
- **Fast-path** in `cli.py` for `doc search` daemon bypass
- **Global `-o`** output format resolved from root Click context

## Anti-patterns observed in immature CLIs (avoid)

- `print()` for errors instead of logging + exit code
- Business logic inside `@click.command` functions
- Per-module `basicConfig()` causing duplicate log lines
- Subcommand-local output format flags that ignore global `-o`