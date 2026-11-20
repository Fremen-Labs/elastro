"""Coverage and readiness CLI commands."""

from __future__ import annotations

from typing import Any, List, Optional

import rich_click as click

from elastro.cli.context import require_client
from elastro.cli.errors import confirm_or_exit, exit_from_exception, usage_error
from elastro.cli.output import format_output
from elastro.core.errors import ValidationError
from elastro.core.logger import get_logger
from elastro.coverage.templates import TemplateManager
from elastro.coverage.validators import (
    CoverageReport,
    CoverageValidator,
    default_coverage_window,
)

logger = get_logger(__name__)


@click.group("coverage")
def coverage_group() -> None:
    """APM and Beats coverage checks, templates, and readiness."""


@coverage_group.group("templates")
def templates_group() -> None:
    """List and apply opinionated APM/Beats ILM + index templates."""


@templates_group.command("list")
@click.pass_context
def templates_list(ctx: click.Context) -> None:
    """
    List shipped coverage templates.

    Examples:

    ```bash
    elastro coverage templates list
    elastro -o json coverage templates list
    ```
    """
    logger.info("coverage.templates.list")
    try:
        rows = [
            info.model_dump(mode="json")
            for info in TemplateManager().list(include_applied=False)
        ]
        _echo(rows, ctx)
    except Exception as exc:
        exit_from_exception(exc, logger=logger, action="list coverage templates")


@templates_group.command("apply", no_args_is_help=True)
@click.argument("name", type=str)
@click.option("--policy-name", type=str, default=None, help="Override ILM policy name")
@click.option("--retention-days", type=int, default=None, help="Delete phase min age")
@click.option(
    "--rollover-size",
    type=str,
    default=None,
    help="Hot rollover max_primary_shard_size (e.g. 50gb)",
)
@click.option("--hot-max-age", type=str, default=None, help="Hot rollover max_age")
@click.option("--warm-min-age", type=str, default=None, help="Warm phase min_age")
@click.option("--dry-run", is_flag=True, default=False, help="Print bodies without PUT")
@click.option("--yes", is_flag=True, default=False, help="Skip confirmation")
@click.pass_context
def templates_apply(
    ctx: click.Context,
    name: str,
    policy_name: Optional[str],
    retention_days: Optional[int],
    rollover_size: Optional[str],
    hot_max_age: Optional[str],
    warm_min_age: Optional[str],
    dry_run: bool,
    yes: bool,
) -> None:
    """
    Apply an ILM policy and matching index template.

    Examples:

    ```bash
    elastro coverage templates apply apm-traces --dry-run
    elastro coverage templates apply metricbeat --policy-name custom-metrics --yes
    ```
    """
    logger.info(
        "coverage.templates.apply name=%s dry_run=%s policy=%s",
        name,
        dry_run,
        policy_name or "-",
    )
    if not dry_run:
        confirm_or_exit(
            f"Apply coverage template '{name}' (ILM policy + index template)?",
            yes=yes,
        )
        client = require_client(ctx)
        manager = TemplateManager(client)
    else:
        manager = TemplateManager()
    try:
        result = manager.apply(
            name,
            dry_run=dry_run,
            ilm_policy_name=policy_name,
            retention_days=retention_days,
            rollover_max_size=rollover_size,
            hot_max_age=hot_max_age,
            warm_min_age=warm_min_age,
        )
        _echo(result.model_dump(mode="json"), ctx)
    except ValidationError as exc:
        usage_error(str(exc))
    except Exception as exc:
        exit_from_exception(exc, logger=logger, action="apply coverage template")


@coverage_group.command("check")
@click.option("--service", type=str, default=None, help="Filter by service.name")
@click.option("--pattern", type=str, default=None, help="Index or data stream pattern")
@click.option(
    "--all",
    "check_all",
    is_flag=True,
    default=False,
    help=(
        "AND-gate: fail unless all of traces-apm*, metrics-apm*, logs-apm*, "
        "filebeat-*, metricbeat-* and data-stream aliases logs-filebeat*, "
        "metrics-metricbeat* are present and passing"
    ),
)
@click.option(
    "--window",
    type=str,
    default=None,
    help="Query window (default: coverage.default_window or 15m)",
)
@click.option("--min-docs", type=int, default=1, show_default=True)
@click.option(
    "--max-age",
    type=str,
    default=None,
    help="Maximum age of the newest document (defaults to --window)",
)
@click.option(
    "--max-cardinality",
    type=int,
    default=None,
    help="Fail when unique service.name values exceed this count",
)
@click.pass_context
def coverage_check(
    ctx: click.Context,
    service: Optional[str],
    pattern: Optional[str],
    check_all: bool,
    window: Optional[str],
    min_docs: int,
    max_age: Optional[str],
    max_cardinality: Optional[int],
) -> None:
    """
    Validate that APM or Beats data is arriving.

    `--all` is an AND-gate: every default pattern must be present and pass
    (`traces-apm*`, `metrics-apm*`, `logs-apm*`, `filebeat-*`, `metricbeat-*`,
    and data-stream aliases `logs-filebeat*`, `metrics-metricbeat*`).

    Examples:

    ```bash
    elastro coverage check --service my-app --window 15m
    elastro coverage check --pattern "traces-apm*" --min-docs 100 --max-age 5m
    elastro -o table coverage check --all
    ```
    """
    selected = [bool(service), bool(pattern), bool(check_all)]
    if sum(selected) != 1:
        usage_error("Provide exactly one of --service, --pattern, or --all")
    resolved_window = window or default_coverage_window()
    client = require_client(ctx)
    logger.info(
        "coverage.check service=%s pattern=%s all=%s window=%s min_docs=%s",
        service or "-",
        pattern or "-",
        check_all,
        resolved_window,
        min_docs,
    )
    validator = CoverageValidator(client)
    try:
        if service:
            report = validator.check_service(
                service,
                window=resolved_window,
                min_docs=min_docs,
                max_age=max_age,
                max_cardinality=max_cardinality,
            )
        elif pattern:
            report = validator.check_pattern(
                pattern,
                window=resolved_window,
                min_docs=min_docs,
                max_age=max_age,
                max_cardinality=max_cardinality,
            )
        else:
            report = validator.check_all(
                window=resolved_window,
                min_docs=min_docs,
                max_age=max_age,
                max_cardinality=max_cardinality,
            )
    except ValidationError as exc:
        usage_error(str(exc))
    except Exception as exc:
        exit_from_exception(exc, logger=logger, action="coverage check")

    _echo(_check_payload(report, ctx), ctx)
    if not report.passed:
        raise SystemExit(2)


@coverage_group.command("report")
@click.option("--service", type=str, default=None, help="Filter by service.name")
@click.option("--pattern", type=str, default=None, help="Index or data stream pattern")
@click.option(
    "--window",
    type=str,
    default=None,
    help="Query window (default: coverage.default_window or 15m)",
)
@click.option("--min-docs", type=int, default=1, show_default=True)
@click.option("--max-age", type=str, default=None)
@click.option("--max-cardinality", type=int, default=None)
@click.pass_context
def coverage_report(
    ctx: click.Context,
    service: Optional[str],
    pattern: Optional[str],
    window: Optional[str],
    min_docs: int,
    max_age: Optional[str],
    max_cardinality: Optional[int],
) -> None:
    """
    Combined readiness report (templates + coverage + APM/Beats health).

    Examples:

    ```bash
    elastro coverage report
    elastro -o json coverage report --service checkout-service
    ```
    """
    if service and pattern:
        usage_error("Use only one of --service or --pattern")
    resolved_window = window or default_coverage_window()
    client = require_client(ctx)
    logger.info(
        "coverage.report service=%s pattern=%s window=%s",
        service or "-",
        pattern or "-",
        resolved_window,
    )
    from elastro.coverage.readiness import ReadinessReporter

    try:
        report = ReadinessReporter(client).report(
            service=service,
            pattern=pattern,
            window=resolved_window,
            min_docs=min_docs,
            max_age=max_age,
            max_cardinality=max_cardinality,
        )
    except ValidationError as exc:
        usage_error(str(exc))
    except Exception as exc:
        exit_from_exception(exc, logger=logger, action="coverage report")

    payload = _report_payload(report, ctx)
    _echo(payload, ctx)
    if not report.passed:
        raise SystemExit(2)


@coverage_group.group("fleet")
def fleet_group() -> None:
    """Read-only Elastic Fleet agent status (Kibana API)."""


@fleet_group.command("status")
@click.pass_context
def fleet_status(ctx: click.Context) -> None:
    """
    Show Fleet agent status counts.

    Examples:

    ```bash
    elastro coverage fleet status
    elastro -o json coverage fleet status
    ```
    """
    logger.info("coverage.fleet.status")
    from elastro.coverage.fleet import FleetClient

    try:
        status = FleetClient.from_config().status()
        _echo(status.model_dump(mode="json"), ctx)
    except ValidationError as exc:
        usage_error(str(exc))
    except Exception as exc:
        exit_from_exception(exc, logger=logger, action="fleet status")


@fleet_group.command("agents")
@click.option(
    "--policy",
    type=str,
    default=None,
    help="Filter by Fleet policy id or name",
)
@click.pass_context
def fleet_agents(ctx: click.Context, policy: Optional[str]) -> None:
    """
    List Fleet agents (last check-in, policy, upgrade status).

    Examples:

    ```bash
    elastro coverage fleet agents
    elastro coverage fleet agents --policy apm-apps
    ```
    """
    logger.info("coverage.fleet.agents policy=%s", policy or "-")
    from elastro.coverage.fleet import FleetClient

    try:
        agents = FleetClient.from_config().list_agents(policy_id=policy)
        _echo([agent.model_dump(mode="json") for agent in agents], ctx)
    except ValidationError as exc:
        usage_error(str(exc))
    except Exception as exc:
        exit_from_exception(exc, logger=logger, action="list fleet agents")


def _output_format(ctx: click.Context) -> str:
    root = ctx
    while root.parent is not None:
        root = root.parent
    return str(root.params.get("output") or "json")


def _echo(data: Any, ctx: click.Context) -> None:
    output = format_output(data, output_format=_output_format(ctx))
    click.echo(output, nl=not output.endswith("\n"))


def _check_payload(report: CoverageReport, ctx: click.Context) -> Any:
    if _output_format(ctx) == "table":
        return [
            {
                "check": item.name,
                "passed": item.passed,
                "summary": item.summary,
                "docs": item.doc_count,
                "latest": item.latest_timestamp or "",
            }
            for item in report.checks
        ]
    return report.model_dump(mode="json")


def _report_payload(report: Any, ctx: click.Context) -> Any:
    if _output_format(ctx) != "table":
        return report.model_dump(mode="json")
    rows: List[dict] = []
    for template in report.templates:
        rows.append(
            {
                "section": "template",
                "name": template.name,
                "ok": bool(template.applied),
                "detail": template.description,
            }
        )
    for check in report.coverage.checks:
        rows.append(
            {
                "section": "coverage",
                "name": check.name,
                "ok": check.passed,
                "detail": check.summary,
            }
        )
    for finding in report.health_findings:
        rows.append(
            {
                "section": "health",
                "name": finding.id,
                "ok": finding.status.value == "pass",
                "detail": finding.summary,
            }
        )
    if not rows:
        rows.append(
            {
                "section": "readiness",
                "name": "report",
                "ok": report.passed,
                "detail": "No template, coverage, or health rows",
            }
        )
    return rows
