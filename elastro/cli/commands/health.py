"""Health assessment and status commands."""

from typing import Callable, Optional, Tuple

import rich_click as click

from elastro.core.client import ElasticsearchClient
from elastro.core.errors import OperationError
from elastro.core.logger import get_logger
from elastro.health.assessor import HealthAssessor
from elastro.health.exit_policy import (
    FAIL_ON_CHOICES,
    FailOn,
    actionable_findings,
    combine_exit_codes,
    resolve_exit_code,
    resolve_fix_exit_code,
)
from elastro.health.formatters.render import render_assessment
from elastro.health.manager import HealthManager
from elastro.health.models import AssessmentReport, FindingStatus
from elastro.cli.output import format_output
from elastro.health.remediation.display import render_fix_run_result
from elastro.health.remediation.dry_run import remediation_result_payload
from elastro.health.remediation.catalog import CATALOG_ACTION_IDS
from elastro.health.remediation.fix import run_health_fix
from elastro.health.remediation.models import FixRunResult

_VALID_WAIT_STATUSES = ("green", "yellow", "red")
logger = get_logger(__name__)


def fail_on_option(f: Callable) -> Callable:
    """Shared ``--fail-on`` option for monitoring-friendly exit codes."""
    return click.option(
        "--fail-on",
        type=click.Choice(FAIL_ON_CHOICES, case_sensitive=False),
        default=FailOn.FAIL.value,
        show_default=True,
        help="Exit 2 when health degrades past this threshold (0=success)",
    )(f)


def _resolve_fail_on(fail_on: str) -> FailOn:
    return FailOn(fail_on.lower())


def _parse_finding_status(value: str) -> FindingStatus:
    try:
        return FindingStatus(value)
    except ValueError:
        return FindingStatus.UNKNOWN


def _output_format(ctx: click.Context) -> str:
    root = ctx
    while root.parent is not None:
        root = root.parent
    return str(root.params.get("output") or "json")


def _render_cluster_health(result: dict) -> None:
    status = result.get("status", "unknown")
    status_colors = {"green": "green", "yellow": "yellow", "red": "red"}

    click.echo(
        click.style(
            f"Cluster: {result.get('cluster_name', 'unknown')} | "
            f"Status: {status} | "
            f"Nodes: {result.get('number_of_nodes', 0)} | "
            f"Data nodes: {result.get('number_of_data_nodes', 0)}",
            fg=status_colors.get(status, "white"),
        )
    )
    click.echo(format_output(result, output_format="json"))


def _client_host(client: ElasticsearchClient) -> str:
    hosts = getattr(client, "hosts", None)
    if isinstance(hosts, list) and hosts:
        return str(hosts[0])
    if isinstance(hosts, str):
        return hosts
    return "unknown"


def _cli_profile(ctx: click.Context) -> str:
    root = ctx
    while root.parent is not None:
        root = root.parent
    return str(root.params.get("profile") or "default")


def _run_assessment(
    client: ElasticsearchClient,
    ctx: click.Context,
    *,
    timeout: str,
    verbose_report: bool,
    feature: Optional[Tuple[str, ...]],
    enable_history: bool = False,
    history_index: Optional[str] = None,
) -> AssessmentReport:
    from elastro.health.config import DEFAULT_HISTORY_INDEX

    assessor = HealthAssessor(client)
    feature_name = feature[0] if feature else None
    return assessor.run(
        timeout=timeout,
        verbose_report=verbose_report,
        feature=feature_name,
        enable_history=enable_history,
        history_index=history_index or DEFAULT_HISTORY_INDEX,
        profile=_cli_profile(ctx),
        host=_client_host(client),
    )


@click.group("health")
def health_group() -> None:
    """Elasticsearch cluster health assessment and diagnostics."""


@health_group.command("assess")
@click.option("--timeout", type=str, default="30s", help="Per-collector timeout")
@click.option(
    "--feature",
    "features",
    multiple=True,
    help="Limit health report to specific indicator(s); only first is used today",
)
@click.option(
    "--verbose-report/--no-verbose-report",
    default=True,
    help="Request verbose root-cause analysis from _health_report",
)
@click.option(
    "--include-raw",
    is_flag=True,
    default=False,
    help="Include raw _health_report in JSON/YAML output",
)
@click.option(
    "--fix",
    is_flag=True,
    default=False,
    help="After assessment, run the unified remediation workflow (prefer 'health fix')",
)
@click.option(
    "--plan",
    is_flag=True,
    default=False,
    help="After assessment, show remediation runbook without executing",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="With --fix, show planned API calls without executing",
)
@click.option("--yes", is_flag=True, default=False, help="With --fix, auto-confirm CONFIRM actions")
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="With --fix and --yes, allow DESTRUCTIVE actions in non-interactive mode",
)
@click.option("--index", "index_pattern", type=str, default=None, help="Limit fixes to an index pattern")
@click.option(
    "--action",
    "action_filter",
    type=click.Choice(CATALOG_ACTION_IDS, case_sensitive=False),
    default=None,
    help="Limit fixes to a single remediation action",
)
@click.option("--target-replicas", type=int, default=None, help="Explicit replica target for reduce_replicas")
@click.option(
    "--history/--no-history",
    default=False,
    help="Index assessment report to elastro-health-assessments",
)
@click.option(
    "--history-index",
    type=str,
    default=None,
    help="Assessment history index name",
)
@fail_on_option
@click.pass_context
def health_assess(
    ctx: click.Context,
    timeout: str,
    features: Tuple[str, ...],
    verbose_report: bool,
    include_raw: bool,
    fix: bool,
    plan: bool,
    dry_run: bool,
    yes: bool,
    force: bool,
    index_pattern: Optional[str],
    action_filter: Optional[str],
    target_replicas: Optional[int],
    history: bool,
    history_index: Optional[str],
    fail_on: str,
) -> None:
    """
    Run a full cluster health assessment with score and findings.

    Combines Elasticsearch _health_report indicators, cluster health, and
    pending tasks into a weighted score with actionable findings.

    Examples:

    Table assessment (recommended):
    ```bash
    elastro health assess -o table
    ```

    JSON assessment:
    ```bash
    elastro health assess -o json
    ```

    Disk indicator only:
    ```bash
    elastro health assess --feature disk -o table
    ```

    Preview index fixes after assessment:
    ```bash
    elastro health assess --fix --dry-run -o table
    ```
    """
    if dry_run and not fix:
        click.echo("Error: --dry-run requires --fix", err=True)
        raise SystemExit(2)
    if plan and fix:
        click.echo("Error: --plan and --fix are mutually exclusive", err=True)
        raise SystemExit(2)
    if (yes or force) and not fix:
        click.echo("Error: --yes and --force require --fix", err=True)
        raise SystemExit(2)

    client: ElasticsearchClient = ctx.obj
    logger.info(
        "health assess invoked fix=%s dry_run=%s verbose_report=%s history=%s",
        fix,
        dry_run,
        verbose_report,
        history,
    )
    try:
        report = _run_assessment(
            client,
            ctx,
            timeout=timeout,
            verbose_report=verbose_report,
            feature=features,
            enable_history=history,
            history_index=history_index,
        )
        output = render_assessment(
            report,
            _output_format(ctx),
            include_raw=include_raw,
        )
        click.echo(output, nl=not output.endswith("\n"))

        fix_result: Optional[FixRunResult] = None
        if plan or fix or dry_run:
            fix_result = _render_health_fix(
                ctx,
                client,
                dry_run=dry_run,
                plan_only=plan,
                auto_yes=yes,
                force=force,
                index_pattern=index_pattern,
                action_filter=action_filter,
                target_replicas=target_replicas,
                session_id=report.session_id,
                cluster_name=report.cluster_name,
                interactive=fix and not dry_run and not yes,
            )

        assess_exit = resolve_exit_code(
            fail_on=_resolve_fail_on(fail_on),
            overall_status=report.overall_status,
            overall_score=report.overall_score,
            findings=report.findings,
        )
        fix_exit = resolve_fix_exit_code(fix_result) if fix_result else 0
        exit_code = combine_exit_codes(assess_exit, fix_exit)
        if exit_code:
            raise SystemExit(exit_code)
    except OperationError as e:
        click.echo(f"Error running health assessment: {str(e)}", err=True)
        raise SystemExit(1) from e


def _render_health_fix(
    ctx: click.Context,
    client: ElasticsearchClient,
    *,
    dry_run: bool,
    plan_only: bool,
    auto_yes: bool,
    force: bool,
    index_pattern: Optional[str],
    action_filter: Optional[str],
    target_replicas: Optional[int],
    session_id: Optional[str],
    cluster_name: Optional[str],
    interactive: bool,
) -> FixRunResult:
    from rich.prompt import Confirm, Prompt

    from elastro.health.audit import HealthAuditLogger

    logger.info(
        "Health fix flow invoked dry_run=%s plan_only=%s auto_yes=%s force=%s",
        dry_run,
        plan_only,
        auto_yes,
        force,
    )
    audit = HealthAuditLogger(
        client,
        profile=_cli_profile(ctx),
        host=_client_host(client),
    )
    fix_result = run_health_fix(
        client,
        dry_run=dry_run,
        plan_only=plan_only,
        auto_yes=auto_yes,
        force=force,
        index_pattern=index_pattern,
        action_filter=action_filter,
        target_replicas=target_replicas,
        interactive=interactive,
        session_id=session_id,
        cluster_name=cluster_name,
        audit_logger=audit,
        confirm=lambda prompt, default: Confirm.ask(prompt, default=default),
        prompt=lambda message: Prompt.ask(message),
    )
    render_fix_run_result(fix_result, output_format=_output_format(ctx))
    return fix_result


@health_group.command("fix")
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Preview planned API calls without executing",
)
@click.option(
    "--yes",
    is_flag=True,
    default=False,
    help="Auto-confirm CONFIRM-level actions (non-interactive)",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="With --yes, allow DESTRUCTIVE actions in non-interactive mode",
)
@click.option("--index", "index_pattern", type=str, default=None, help="Limit fixes to an index pattern")
@click.option(
    "--action",
    "action_filter",
    type=click.Choice(CATALOG_ACTION_IDS, case_sensitive=False),
    default=None,
    help="Limit fixes to a single remediation action",
)
@click.option(
    "--target-replicas",
    type=int,
    default=None,
    help="Explicit replica target for reduce_replicas",
)
@click.pass_context
def health_fix(
    ctx: click.Context,
    dry_run: bool,
    yes: bool,
    force: bool,
    index_pattern: Optional[str],
    action_filter: Optional[str],
    target_replicas: Optional[int],
) -> None:
    """
    Diagnose unhealthy indices and apply safe, confirmed remediations.

    Shows impact and consequences before destructive changes. Use ``--dry-run``
    to preview, ``--yes`` for automation-friendly CONFIRM actions, and
    ``--force`` with ``--yes`` for DESTRUCTIVE actions.

    Examples:

    Interactive fix workflow:
    ```bash
    elastro health fix -o table
    ```

    Preview without changes:
    ```bash
    elastro health fix --dry-run -o table
    ```

    CI-safe reroute retry:
    ```bash
    elastro health fix --yes --action reroute_failed
    ```
    """
    client: ElasticsearchClient = ctx.obj
    logger.info(
        "health fix invoked dry_run=%s yes=%s force=%s index=%s action=%s",
        dry_run,
        yes,
        force,
        index_pattern,
        action_filter,
    )
    try:
        fix_result = _render_health_fix(
            ctx,
            client,
            dry_run=dry_run,
            plan_only=False,
            auto_yes=yes,
            force=force,
            index_pattern=index_pattern,
            action_filter=action_filter,
            target_replicas=target_replicas,
            session_id=None,
            cluster_name=None,
            interactive=not (yes or dry_run),
        )
        exit_code = combine_exit_codes(resolve_fix_exit_code(fix_result))
        if exit_code:
            raise SystemExit(exit_code)
    except OperationError as exc:
        click.echo(f"Error running health fix: {exc}", err=True)
        raise SystemExit(1) from exc


@health_group.command("score")
@click.option("--timeout", type=str, default="30s", help="Per-collector timeout")
@click.option(
    "--history",
    is_flag=True,
    default=False,
    help="Read scores from assessment history index instead of re-assessing",
)
@click.option(
    "--last",
    type=int,
    default=10,
    show_default=True,
    help="Number of historical assessments to show with --history",
)
@click.option(
    "--history-index",
    type=str,
    default=None,
    help="Assessment history index name",
)
@fail_on_option
@click.pass_context
def health_score(
    ctx: click.Context,
    timeout: str,
    history: bool,
    last: int,
    history_index: Optional[str],
    fail_on: str,
) -> None:
    """
    Print the current cluster health score (0-100).

    Examples:

    ```bash
    elastro health score
    elastro health score -o json
    elastro health score --history --last 5 -o table
    ```
    """
    from elastro.health.config import DEFAULT_HISTORY_INDEX
    from elastro.health.history import query_assessment_history

    client: ElasticsearchClient = ctx.obj
    logger.info(
        "health score invoked timeout=%s history=%s last=%s",
        timeout,
        history,
        last,
    )
    try:
        output_fmt = _output_format(ctx)
        if history:
            records = query_assessment_history(
                client,
                history_index=history_index or DEFAULT_HISTORY_INDEX,
                limit=last,
            )
            if output_fmt == "table":
                from elastro.health.formatters.history_table import (
                    format_score_history_table,
                )

                click.echo(format_score_history_table(records), nl=False)
            else:
                click.echo(
                    format_output(
                        {"assessments": records},
                        output_format=output_fmt,
                    )
                )
            if records:
                latest = records[0]
                exit_code = resolve_exit_code(
                    fail_on=_resolve_fail_on(fail_on),
                    overall_status=_parse_finding_status(
                        str(latest.get("overall_status", "unknown"))
                    ),
                    overall_score=int(latest.get("overall_score") or 0),
                )
                if exit_code:
                    raise SystemExit(exit_code)
            return

        report = _run_assessment(
            client,
            ctx,
            timeout=timeout,
            verbose_report=False,
            feature=None,
        )
        if output_fmt == "json":
            click.echo(
                format_output(
                    {
                        "cluster_name": report.cluster_name,
                        "overall_score": report.overall_score,
                        "overall_status": report.overall_status.value,
                        "elasticsearch_version": report.elasticsearch_version,
                        "findings_count": len(report.findings),
                    },
                    output_format="json",
                )
            )
        elif output_fmt == "yaml":
            click.echo(
                format_output(
                    {
                        "cluster_name": report.cluster_name,
                        "overall_score": report.overall_score,
                        "overall_status": report.overall_status.value,
                    },
                    output_format="yaml",
                )
            )
        else:
            from elastro.health.formatters.table import score_label

            label = score_label(report.overall_score)
            click.echo(
                f"{report.cluster_name}: {report.overall_score}/100 ({label}) "
                f"- {len(report.findings)} finding(s)"
            )

        exit_code = resolve_exit_code(
            fail_on=_resolve_fail_on(fail_on),
            overall_status=report.overall_status,
            overall_score=report.overall_score,
            findings=report.findings,
        )
        if exit_code:
            raise SystemExit(exit_code)
    except OperationError as e:
        click.echo(f"Error fetching health score: {str(e)}", err=True)
        raise SystemExit(1) from e


@health_group.command("trends")
@click.option(
    "--window",
    type=str,
    default="7d",
    show_default=True,
    help="History window (e.g. 7d, 24h, 30d)",
)
@click.option(
    "--cluster",
    "cluster_name",
    type=str,
    default=None,
    help="Limit trends to a single cluster (omit for fleet summary)",
)
@click.option(
    "--finding",
    "finding_id",
    type=str,
    default=None,
    help="Filter recurring findings to a specific finding id",
)
@click.option(
    "--limit",
    type=int,
    default=50,
    show_default=True,
    help="Maximum assessment samples to analyze",
)
@click.option(
    "--history-index",
    type=str,
    default=None,
    help="Assessment history index name",
)
@click.pass_context
def health_trends(
    ctx: click.Context,
    window: str,
    cluster_name: Optional[str],
    finding_id: Optional[str],
    limit: int,
    history_index: Optional[str],
) -> None:
    """
    Show score trends, recurring findings, and persistent yellow signals.

    Examples:

    ```bash
    elastro health trends -o table
    elastro health trends --cluster docker-cluster --window 30d
    elastro health trends --finding shards.oversharded --window 30d -o json
    ```
    """
    from elastro.health.config import DEFAULT_HISTORY_INDEX
    from elastro.health.formatters.history_table import (
        format_fleet_summary_table,
        format_trends_table,
    )
    from elastro.health.history import history_cluster_summary, parse_window
    from elastro.health.trends import compute_trends

    client: ElasticsearchClient = ctx.obj
    output_fmt = _output_format(ctx)
    resolved_index = history_index or DEFAULT_HISTORY_INDEX

    logger.info(
        "health trends invoked window=%s cluster=%s finding=%s limit=%s",
        window,
        cluster_name,
        finding_id,
        limit,
    )

    try:
        parse_window(window)
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(2) from exc

    try:
        if cluster_name:
            report = compute_trends(
                client,
                history_index=resolved_index,
                cluster_name=cluster_name,
                window=window,
                limit=limit,
                finding_id=finding_id,
            )
            if output_fmt == "table":
                click.echo(format_trends_table(report), nl=False)
            else:
                click.echo(format_output(report.to_dict(), output_format=output_fmt))
            return

        summary = history_cluster_summary(
            client,
            history_index=resolved_index,
            window=window,
            limit=limit,
        )
        if output_fmt == "table":
            click.echo(
                format_fleet_summary_table(summary, window=window),
                nl=False,
            )
        else:
            click.echo(
                format_output(
                    {
                        "window": window,
                        "clusters": summary,
                        "count": len(summary),
                    },
                    output_format=output_fmt,
                )
            )
    except OperationError as exc:
        click.echo(f"Error computing health trends: {exc}", err=True)
        raise SystemExit(1) from exc
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(2) from exc


@health_group.command("nodes")
@click.option(
    "--node-id",
    type=str,
    default=None,
    help="Limit stats to a specific node id",
)
@click.option(
    "--metric",
    "metrics",
    default="jvm,fs,os,breaker",
    show_default=True,
    help="Comma-separated node stats metrics (jvm, fs, os, breaker)",
)
@click.option(
    "--hotspots",
    is_flag=True,
    default=False,
    help="Highlight per-node JVM, disk, and CPU variance hotspots",
)
@click.pass_context
def health_nodes(
    ctx: click.Context,
    node_id: Optional[str],
    metrics: str,
    hotspots: bool,
) -> None:
    """
    Show per-node JVM, disk, OS, and circuit-breaker stats.

    Examples:

    JVM and disk table:
    ```bash
    elastro -o table health nodes --metric jvm,fs
    ```

    JSON output for a single node:
    ```bash
    elastro -o json health nodes --node-id node-1 --metric jvm,fs
    ```
    """
    from elastro.health.collectors.base import CollectContext
    from elastro.health.collectors.nodes import NodesCollector
    from elastro.health.formatters.nodes_table import format_nodes_table

    client: ElasticsearchClient = ctx.obj
    logger.info(
        "health nodes invoked node_id=%s metrics=%s hotspots=%s",
        node_id,
        metrics,
        hotspots,
    )
    collector = NodesCollector()
    result = collector.collect(
        CollectContext(
            client=client,
            options={"node_id": node_id, "metrics": metrics},
        )
    )
    if result.status != "ok":
        click.echo(
            f"Error collecting node stats: {result.error or 'unknown error'}",
            err=True,
        )
        raise SystemExit(1)

    output_fmt = _output_format(ctx)
    nodes = result.data.get("nodes", {})
    metric_list = [part.strip() for part in metrics.split(",") if part.strip()]

    if hotspots:
        from elastro.health.formatters.hotspots_table import format_hotspots_table
        from elastro.health.rules.hotspots import hotspot_variance

        hotspot_rows = hotspot_variance(result.data)
        if output_fmt == "table":
            click.echo(format_hotspots_table(hotspot_rows), nl=False)
        else:
            click.echo(
                format_output(
                    {"hotspots": hotspot_rows},
                    output_format=output_fmt,
                )
            )
        return

    if output_fmt == "table":
        click.echo(format_nodes_table(nodes, metric_list), nl=False)
    elif output_fmt == "yaml":
        click.echo(
            format_output(
                {
                    "node_count": result.data.get("node_count", 0),
                    "metrics": metric_list,
                    "nodes": nodes,
                },
                output_format="yaml",
            )
        )
    else:
        click.echo(
            format_output(
                {
                    "node_count": result.data.get("node_count", 0),
                    "metrics": metric_list,
                    "nodes": nodes,
                },
                output_format="json",
            )
        )


@health_group.command("shards")
@click.option("--index", type=str, default=None, help="Limit to a specific index pattern")
@click.option(
    "--analyze",
    is_flag=True,
    default=False,
    help="Analyze shard sizes for oversharding and undersharding",
)
@click.option(
    "--explain",
    is_flag=True,
    default=False,
    help="Explain shard allocation (optionally for --index)",
)
@click.option(
    "--overshard-mb",
    type=float,
    default=1.0,
    show_default=True,
    help="Overshard threshold in megabytes",
)
@click.option(
    "--undershard-gb",
    type=float,
    default=50.0,
    show_default=True,
    help="Undershard threshold in gigabytes",
)
@fail_on_option
@click.pass_context
def health_shards(
    ctx: click.Context,
    index: Optional[str],
    analyze: bool,
    explain: bool,
    overshard_mb: float,
    undershard_gb: float,
    fail_on: str,
) -> None:
    """
    Inspect cluster shards, analyze shard sizes, or explain allocation.

    Examples:

    Analyze shard sizing:
    ```bash
    elastro -o table health shards --analyze
    ```

    Explain allocation for an index:
    ```bash
    elastro health shards --explain --index logs-000001
    ```
    """
    from elastro.health.collectors.base import CollectContext
    from elastro.health.collectors.shards import ShardsCollector, explain_allocation
    from elastro.health.formatters.shards_table import (
        format_shard_analyze_summary,
        format_shard_analyze_table,
    )

    client: ElasticsearchClient = ctx.obj
    logger.info(
        "health shards invoked index=%s analyze=%s explain=%s",
        index,
        analyze,
        explain,
    )
    output_fmt = _output_format(ctx)
    collect_ctx = CollectContext(
        client=client,
        options={
            "index": index,
            "overshard_threshold_mb": overshard_mb,
            "undershard_threshold_gb": undershard_gb,
        },
    )

    if explain:
        try:
            payload = explain_allocation(collect_ctx, index_name=index)
        except OperationError as exc:
            click.echo(f"Error explaining allocation: {exc}", err=True)
            raise SystemExit(1) from exc
        click.echo(format_output(payload, output_format=output_fmt))
        return

    collector = ShardsCollector()
    result = collector.collect(collect_ctx)
    if result.status != "ok":
        click.echo(
            f"Error collecting shard stats: {result.error or 'unknown error'}",
            err=True,
        )
        raise SystemExit(1)

    analysis = result.data.get("analysis", {})
    if analyze:
        if output_fmt == "table":
            click.echo(format_shard_analyze_table(analysis), nl=False)
        elif output_fmt == "yaml":
            click.echo(format_output(analysis, output_format="yaml"))
        else:
            click.echo(format_output(analysis, output_format="json"))
    else:
        summary = {
            "total_shards": analysis.get("total_shards", 0),
            "unassigned_shards": analysis.get("unassigned_count", 0),
            "index": index,
        }
        if output_fmt == "table":
            click.echo(format_shard_analyze_summary(analysis))
        else:
            click.echo(format_output(summary, output_format=output_fmt))

    exit_code = resolve_exit_code(
        fail_on=_resolve_fail_on(fail_on),
        extra_signals={
            "unassigned_shards": analysis.get("unassigned_count", 0),
        },
    )
    if exit_code:
        raise SystemExit(exit_code)


@health_group.command("ilm")
@click.option(
    "--stuck-only",
    is_flag=True,
    default=False,
    help="Show only indices with failed or stuck ILM lifecycle steps",
)
@click.option("--index", "index_pattern", type=str, default=None, help="Limit to an index pattern")
@click.pass_context
def health_ilm(
    ctx: click.Context,
    stuck_only: bool,
    index_pattern: Optional[str],
) -> None:
    """
    Inspect ILM lifecycle status and list stuck indices.

    Examples:

    ```bash
    elastro -o table health ilm --stuck-only
    elastro health ilm --index logs-* --stuck-only -o json
    elastro health fix --dry-run --action ilm_retry --index logs-000042
    ```
    """
    from elastro.health.formatters.ilm_table import format_stuck_ilm_table
    from elastro.health.ilm_status import list_ilm_indices

    client: ElasticsearchClient = ctx.obj
    logger.info(
        "health ilm invoked stuck_only=%s index=%s",
        stuck_only,
        index_pattern,
    )
    output_fmt = _output_format(ctx)

    try:
        rows = list_ilm_indices(
            client,
            index_pattern=index_pattern,
            stuck_only=stuck_only,
        )

        if output_fmt == "table":
            click.echo(format_stuck_ilm_table(rows), nl=False)
        else:
            payload = {
                "stuck_only": stuck_only,
                "index_pattern": index_pattern,
                "indices": [item.model_dump(mode="json") for item in rows],
                "count": len(rows),
            }
            click.echo(format_output(payload, output_format=output_fmt))
    except OperationError as exc:
        click.echo(f"Error inspecting ILM status: {exc}", err=True)
        raise SystemExit(1) from exc


@health_group.command("hotspots")
@click.option(
    "--variance",
    type=float,
    default=30.0,
    show_default=True,
    help="Minimum spread (percentage points) to flag a hotspot",
)
@click.pass_context
def health_hotspots(ctx: click.Context, variance: float) -> None:
    """
    Detect per-node JVM, disk, and CPU hotspots.

    Alias for `elastro health nodes --hotspots`.

    Examples:

    ```bash
    elastro -o table health hotspots
    elastro health hotspots --variance 25 -o json
    ```
    """
    from elastro.health.collectors.base import CollectContext
    from elastro.health.collectors.nodes import NodesCollector
    from elastro.health.formatters.hotspots_table import format_hotspots_table
    from elastro.health.rules.hotspots import hotspot_variance

    client: ElasticsearchClient = ctx.obj
    logger.info("health hotspots invoked variance=%s", variance)
    output_fmt = _output_format(ctx)
    result = NodesCollector().collect(CollectContext(client=client))
    if result.status != "ok":
        click.echo(
            f"Error collecting node stats: {result.error or 'unknown error'}",
            err=True,
        )
        raise SystemExit(1)

    hotspots = hotspot_variance(result.data, variance_threshold=variance)
    if output_fmt == "table":
        click.echo(format_hotspots_table(hotspots), nl=False)
    else:
        click.echo(format_output({"hotspots": hotspots}, output_format=output_fmt))


@health_group.command("lint")
@click.option(
    "--category",
    "categories",
    multiple=True,
    type=click.Choice(["settings", "mappings", "shards", "security"]),
    help="Lint category to run; repeatable (default: all)",
)
@click.option(
    "--index",
    type=str,
    default=None,
    help="Limit lint to an index pattern (settings, mappings, shards)",
)
@click.option("--timeout", type=str, default="30s", help="Per-request timeout")
@click.option(
    "--max-indices",
    type=int,
    default=50,
    show_default=True,
    help="Maximum user indices to scan for settings/mappings lint",
)
@fail_on_option
@click.pass_context
def health_lint(
    ctx: click.Context,
    categories: Tuple[str, ...],
    index: Optional[str],
    timeout: str,
    max_indices: int,
    fail_on: str,
) -> None:
    """
    Lint index settings, mappings, and shard layout against best practices.

    Examples:

    ```bash
    elastro health lint -o table
    elastro health lint --category mappings --category shards -o json
    elastro health lint --category shards --index logs-* -o table
    ```
    """
    from elastro.health.formatters.lint_table import format_lint_table
    from elastro.health.lint import run_lint

    client: ElasticsearchClient = ctx.obj
    selected = list(categories) if categories else None
    logger.info(
        "health lint invoked categories=%s index=%s",
        selected or "all",
        index,
    )
    try:
        findings = run_lint(
            client,
            categories=selected,
            index_pattern=index,
            timeout=timeout,
            max_indices=max_indices,
        )
        output_fmt = _output_format(ctx)
        if output_fmt == "table":
            click.echo(format_lint_table(findings), nl=False)
        else:
            payload = {
                "findings": [item.model_dump(mode="json") for item in findings],
                "issue_count": len(findings),
            }
            click.echo(format_output(payload, output_format=output_fmt))

        actionable = actionable_findings(findings)
        overall_status = FindingStatus.PASS
        if any(item.status == FindingStatus.FAIL for item in actionable):
            overall_status = FindingStatus.FAIL
        elif any(item.status == FindingStatus.WARN for item in actionable):
            overall_status = FindingStatus.WARN

        exit_code = resolve_exit_code(
            fail_on=_resolve_fail_on(fail_on),
            overall_status=overall_status,
            findings=actionable,
        )
        if exit_code:
            raise SystemExit(exit_code)
    except OperationError as exc:
        click.echo(f"Error running health lint: {exc}", err=True)
        raise SystemExit(1) from exc


@health_group.group("rollback")
def health_rollback_group() -> None:
    """Manage remediation rollback snapshots."""


@health_rollback_group.command("list")
@click.option(
    "--last",
    type=int,
    default=20,
    show_default=True,
    help="Number of recent rollback records to show",
)
@click.pass_context
def health_rollback_list(ctx: click.Context, last: int) -> None:
    """
    List saved remediation rollback snapshots.

    Examples:

    ```bash
    elastro -o table health rollback list
    elastro health rollback list --last 5 -o json
    ```
    """
    from elastro.health.remediation.rollback import RollbackStore

    logger.info("health rollback list invoked last=%s", last)
    records = RollbackStore().list_records(limit=last)
    output_fmt = _output_format(ctx)
    if output_fmt == "table":
        if not records:
            click.echo("No rollback snapshots found.")
            return
        for record in records:
            click.echo(
                f"{record.rollback_id}  {record.index_name}  "
                f"{record.action_id}  {record.applied_at.isoformat()}"
            )
    else:
        payload = {
            "rollbacks": [record.model_dump(mode="json") for record in records]
        }
        click.echo(format_output(payload, output_format=output_fmt))


@health_rollback_group.command("apply")
@click.option("--id", "rollback_id", required=True, help="Rollback snapshot id")
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Preview restored settings without applying",
)
@click.pass_context
def health_rollback_apply(
    ctx: click.Context,
    rollback_id: str,
    dry_run: bool,
) -> None:
    """
    Restore index settings from a saved remediation rollback snapshot.

    Examples:

    ```bash
    elastro health rollback apply --id rb-abc123 --dry-run
    elastro health rollback apply --id rb-abc123
    ```
    """
    _run_health_rollback(ctx, rollback_id=rollback_id, dry_run=dry_run)


def _run_health_rollback(
    ctx: click.Context,
    *,
    rollback_id: str,
    dry_run: bool,
) -> None:
    from elastro.health.audit import HealthAuditLogger
    from elastro.health.remediation.executor import RemediationExecutor

    client: ElasticsearchClient = ctx.obj
    logger.info(
        "health rollback apply invoked rollback_id=%s dry_run=%s",
        rollback_id,
        dry_run,
    )
    audit = None if dry_run else HealthAuditLogger(
        client,
        profile=_cli_profile(ctx),
        host=_client_host(client),
    )
    executor = RemediationExecutor(
        client,
        dry_run=dry_run,
        interactive=not dry_run,
        audit_logger=audit,
    )
    result = executor.rollback(rollback_id, dry_run=dry_run)
    output_fmt = _output_format(ctx)
    payload = remediation_result_payload(result)
    if output_fmt == "table":
        click.echo(result.message)
        if result.planned_api_call:
            click.echo(f"Planned: {result.planned_api_call}")
        if result.rollback_id:
            click.echo(f"Rollback id: {result.rollback_id}")
    else:
        click.echo(format_output(payload, output_format=output_fmt))
    if not result.success:
        raise SystemExit(1)


@health_group.command("status")
@click.option(
    "--level",
    type=click.Choice(["cluster", "indices", "shards"]),
    default="cluster",
    help="Health check level",
)
@click.option(
    "--wait",
    type=click.Choice(_VALID_WAIT_STATUSES),
    default=None,
    help="Wait for specified status (green, yellow, red)",
)
@click.option("--timeout", type=str, default="30s", help="Timeout for health check")
@fail_on_option
@click.pass_context
def health_status(
    ctx: click.Context,
    level: str,
    wait: Optional[str],
    timeout: str,
    fail_on: str,
) -> None:
    """
    Check Elasticsearch cluster health.

    Display cluster health status (green, yellow, red).

    Examples:

    Check cluster health:
    ```bash
    elastro health status
    ```

    Wait for green status:
    ```bash
    elastro health status --wait green --timeout 60s
    ```
    """
    client: ElasticsearchClient = ctx.obj
    health_manager = HealthManager(client)
    logger.info(
        "health status invoked level=%s wait=%s timeout=%s fail_on=%s",
        level,
        wait,
        timeout,
        fail_on,
    )

    try:
        result = health_manager.cluster_health(
            level=level,
            timeout=timeout,
            wait_for_status=wait,
        )
        _render_cluster_health(result)

        exit_code = resolve_exit_code(
            fail_on=_resolve_fail_on(fail_on),
            extra_signals={
                "cluster_status": result.get("status"),
                "wait_status": wait,
                "timed_out": result.get("timed_out", False),
            },
        )
        if exit_code:
            raise SystemExit(exit_code)
    except OperationError as e:
        click.echo(f"Error checking health: {str(e)}", err=True)
        raise SystemExit(1) from e


@health_group.command("report")
@click.option(
    "--feature",
    type=str,
    default=None,
    help="Limit to a specific health report feature/indicator",
)
@click.option(
    "--verbose/--no-verbose",
    default=True,
    help="Request verbose root-cause analysis from _health_report",
)
@click.pass_obj
def health_report(
    client: ElasticsearchClient,
    feature: Optional[str],
    verbose: bool,
) -> None:
    """
    Get the Elasticsearch _health_report with indicator diagnoses.

    Examples:

    Full health report:
    ```bash
    elastro health report
    ```

    Disk indicator only:
    ```bash
    elastro health report --feature disk
    ```
    """
    health_manager = HealthManager(client)
    logger.info(
        "health report invoked feature=%s verbose=%s",
        feature,
        verbose,
    )

    try:
        result = health_manager.health_report(verbose=verbose, feature=feature)
        click.echo(format_output(result, output_format="json"))
    except OperationError as e:
        click.echo(f"Error fetching health report: {str(e)}", err=True)
        raise SystemExit(1) from e