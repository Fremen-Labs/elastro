---
name: elastro-python-cli
description: >
  FAANG-synthesized Python CLI patterns for Elastro: Click/rich-click command
  groups, global flags, stderr logging, dry-run/fix flows, fast-path startup,
  and testable command handlers. Use when adding CLI commands, refactoring
  elastro/cli, or implementing health/remediation UX.
---

# Elastro Python CLI Patterns (FAANG-synthesized)

Elastro uses **rich-click** (Click + Rich). Match these patterns from AWS CLI, Azure CLI (Knack), Netflix Dispatch, and Google Fire/Abseil ecosystems.

## Architecture

```
elastro/cli/cli.py          # Root group, global opts, configure_logging() in main()
elastro/cli/commands/*.py     # One module per domain (health, index, cluster)
elastro/cli/output.py       # format_output() for json/yaml/table
elastro/<domain>/             # Library logic — CLI is thin wrapper
```

**Rule:** CLI commands parse args → call library → format output. No ES logic in CLI beyond wiring.

## Command structure (AWS + Netflix pattern)

```python
@click.group("health")
def health_group() -> None:
    """One-line summary for --help."""

@health_group.command("assess")
@click.option("--fix", is_flag=True)
@click.option("--dry-run", is_flag=True)
@click.pass_context
def health_assess(ctx, fix, dry_run, ...) -> None:
    client = ctx.obj
    logger.info("health assess invoked fix=%s", fix)
    report = HealthAssessor(client).run(...)
    click.echo(render_assessment(report, _output_format(ctx)))
    if fix:
        ...
```

## Global flags (Azure Knack pattern)

| Flag | Behavior |
|------|----------|
| `-h/--host` | ES connection (root group) |
| `-o/--output` | `json`, `yaml`, `table` — read from **root** ctx |
| `--verbose` | Maps to log level INFO (future) |
| `--debug` | Maps to log level DEBUG (future) |

`_output_format(ctx)` must walk to root context (already in `health.py`).

## UX conventions

- **stdout** = machine/human command output (JSON, tables)
- **stderr** = logs only (Knack + AWS convention)
- **Exit codes:** `0` success, `1` operational error, `2` degraded health / validation
- **Destructive ops:** require `--fix` or interactive `Confirm.ask()` — never silent writes
- **Dry-run:** `--fix --dry-run` prints planned API calls, never executes

## Docstrings (Google Fire / AWS style)

Use markdown in docstrings — rich-click renders them:

```python
"""
Run a full cluster health assessment.

Examples:

Table output:
```bash
elastro -o table health assess
```
"""
```

## Startup performance (Elastro fast-path)

`cli.py` intercepts `elastro doc search` before heavy imports. New commands must NOT break this guard. Avoid top-level imports of heavy deps in `cli.py`; import inside command functions when needed.

## Testing (Netflix Dispatch pattern)

```python
from click.testing import CliRunner
from elastro.cli.cli import cli

@patch("elastro.cli.cli.ElasticsearchClient.connect")
@patch("elastro.health.assessor.HealthAssessor")
def test_assess(mock_assessor, mock_connect, runner):
    result = runner.invoke(cli, ["-h", "http://localhost:9205", "health", "assess"])
    assert result.exit_code == 0
```

- Patch at **import boundary** used by command module
- Put `-o` before subcommand: `["-o", "table", "health", "assess"]`
- Live tests gate on ES reachability with `pytest.skip`

## Adding a new command checklist

1. Library implementation in `elastro/<domain>/`
2. Thin command in `elastro/cli/commands/<domain>.py`
3. Register on group in `cli.py`
4. INFO log at command entry with non-secret params
5. Unit/integration test with mocked ES
6. Example in docstring with fenced `bash` block

## Reference

See `references/faang-cli-synthesis.md` for source repos and rationale.