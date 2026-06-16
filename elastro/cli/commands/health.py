"""Health assessment and status commands."""

from typing import Optional, Tuple

import rich_click as click

from elastro.core.client import ElasticsearchClient
from elastro.core.errors import OperationError
from elastro.core.logger import get_logger
from elastro.health.assessor import HealthAssessor
from elastro.health.formatters.render import render_assessment
from elastro.health.manager import HealthManager
from elastro.health.models import AssessmentReport, FindingStatus
from elastro.cli.output import format_output

_VALID_WAIT_STATUSES = ("green", "yellow", "red")
logger = get_logger(__name__)


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
    help="Offer the same interactive index remediations as 'elastro index fix'",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="With --fix, show planned API calls without executing",
)
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
@click.pass_context
def health_assess(
    ctx: click.Context,
    timeout: str,
    features: Tuple[str, ...],
    verbose_report: bool,
    include_raw: bool,
    fix: bool,
    dry_run: bool,
    history: bool,
    history_index: Optional[str],
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

        if fix or dry_run:
            logger.info(
                "Starting post-assessment remediation dry_run=%s",
                dry_run,
            )
            from rich.prompt import Confirm

            from elastro.health.remediation.diagnosis import diagnose_unhealthy_indices
            from elastro.health.remediation.display import render_remediation_summary
            from elastro.health.remediation.executor import RemediationExecutor

            from elastro.health.audit import HealthAuditLogger

            audit = HealthAuditLogger(
                client,
                profile=_cli_profile(ctx),
                host=_client_host(client),
            )
            executor = RemediationExecutor(
                client,
                dry_run=dry_run,
                interactive=fix and not dry_run,
                confirm=lambda prompt, default: Confirm.ask(prompt, default=default),
                session_id=report.session_id,
                audit_logger=audit,
                cluster_name=report.cluster_name,
            )
            diagnoses = diagnose_unhealthy_indices(executor.index_manager)
            results = []
            for diagnosis in diagnoses:
                result = executor.remediate_diagnosis(diagnosis)
                if result is not None:
                    results.append(result)
            render_remediation_summary(diagnoses, results, dry_run=dry_run)

        if report.overall_status.value == "fail":
            raise SystemExit(2)
    except OperationError as e:
        click.echo(f"Error running health assessment: {str(e)}", err=True)
        raise SystemExit(1) from e


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
@click.pass_context
def health_score(
    ctx: click.Context,
    timeout: str,
    history: bool,
    last: int,
    history_index: Optional[str],
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
                for record in records:
                    cluster = record.get("cluster_name", "unknown")
                    score = record.get("overall_score", 0)
                    status = record.get("overall_status", "unknown")
                    assessed_at = record.get("assessed_at", "")
                    click.echo(
                        f"{cluster}: {score}/100 ({status}) @ {assessed_at}"
                    )
            else:
                click.echo(
                    format_output(
                        {"assessments": records},
                        output_format=output_fmt,
                    )
                )
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
    except OperationError as e:
        click.echo(f"Error fetching health score: {str(e)}", err=True)
        raise SystemExit(1) from e


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
@click.pass_context
def health_shards(
    ctx: click.Context,
    index: Optional[str],
    analyze: bool,
    explain: bool,
    overshard_mb: float,
    undershard_gb: float,
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
        return

    summary = {
        "total_shards": analysis.get("total_shards", 0),
        "unassigned_shards": analysis.get("unassigned_count", 0),
        "index": index,
    }
    if output_fmt == "table":
        click.echo(format_shard_analyze_summary(analysis))
    else:
        click.echo(format_output(summary, output_format=output_fmt))


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
    type=click.Choice(["settings", "mappings", "shards"]),
    help="Lint category to run; repeatable (default: all)",
)
@click.option("--index", type=str, default=None, help="Limit shard lint to an index pattern")
@click.option("--timeout", type=str, default="30s", help="Per-request timeout")
@click.pass_context
def health_lint(
    ctx: click.Context,
    categories: Tuple[str, ...],
    index: Optional[str],
    timeout: str,
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

        if any(item.status == FindingStatus.FAIL for item in findings):
            raise SystemExit(2)
        if findings:
            raise SystemExit(1)
    except OperationError as exc:
        click.echo(f"Error running health lint: {exc}", err=True)
        raise SystemExit(1) from exc


@health_group.command("rollback")
@click.option("--id", "rollback_id", required=True, help="Rollback snapshot id")
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Preview restored settings without applying",
)
@click.pass_context
def health_rollback(
    ctx: click.Context,
    rollback_id: str,
    dry_run: bool,
) -> None:
    """
    Restore index settings from a saved remediation rollback snapshot.

    Examples:

    ```bash
    elastro health rollback --id rb-abc123 --dry-run
    elastro health rollback --id rb-abc123
    ```
    """
    from elastro.health.audit import HealthAuditLogger
    from elastro.health.remediation.executor import RemediationExecutor

    client: ElasticsearchClient = ctx.obj
    logger.info(
        "health rollback invoked rollback_id=%s dry_run=%s",
        rollback_id,
        dry_run,
    )
    audit = HealthAuditLogger(
        client,
        profile=_cli_profile(ctx),
        host=_client_host(client),
    )
    executor = RemediationExecutor(
        client,
        dry_run=dry_run,
        interactive=False,
        audit_logger=audit,
    )
    result = executor.rollback(rollback_id, dry_run=dry_run)
    output_fmt = _output_format(ctx)
    payload = result.model_dump(mode="json")
    if output_fmt == "table":
        click.echo(result.message)
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
@click.pass_obj
def health_status(
    client: ElasticsearchClient,
    level: str,
    wait: Optional[str],
    timeout: str,
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
    health_manager = HealthManager(client)
    logger.info(
        "health status invoked level=%s wait=%s timeout=%s",
        level,
        wait,
        timeout,
    )

    try:
        result = health_manager.cluster_health(
            level=level,
            timeout=timeout,
            wait_for_status=wait,
        )
        _render_cluster_health(result)
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