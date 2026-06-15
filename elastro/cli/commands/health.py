"""Health assessment and status commands."""

from typing import Optional, Tuple

import rich_click as click

from elastro.core.client import ElasticsearchClient
from elastro.core.errors import OperationError
from elastro.health.assessor import HealthAssessor
from elastro.health.formatters.render import render_assessment
from elastro.health.manager import HealthManager
from elastro.health.models import AssessmentReport
from elastro.cli.output import format_output

_VALID_WAIT_STATUSES = ("green", "yellow", "red")


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


def _run_assessment(
    client: ElasticsearchClient,
    *,
    timeout: str,
    verbose_report: bool,
    feature: Optional[Tuple[str, ...]],
) -> AssessmentReport:
    assessor = HealthAssessor(client)
    feature_name = feature[0] if feature else None
    return assessor.run(
        timeout=timeout,
        verbose_report=verbose_report,
        feature=feature_name,
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
@click.pass_context
def health_assess(
    ctx: click.Context,
    timeout: str,
    features: Tuple[str, ...],
    verbose_report: bool,
    include_raw: bool,
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
    """
    client: ElasticsearchClient = ctx.obj
    try:
        report = _run_assessment(
            client,
            timeout=timeout,
            verbose_report=verbose_report,
            feature=features,
        )
        output = render_assessment(
            report,
            _output_format(ctx),
            include_raw=include_raw,
        )
        click.echo(output, nl=not output.endswith("\n"))
        if report.overall_status.value == "fail":
            raise SystemExit(2)
    except OperationError as e:
        click.echo(f"Error running health assessment: {str(e)}", err=True)
        raise SystemExit(1) from e


@health_group.command("score")
@click.option("--timeout", type=str, default="30s", help="Per-collector timeout")
@click.pass_context
def health_score(
    ctx: click.Context,
    timeout: str,
) -> None:
    """
    Print the current cluster health score (0-100).

    Examples:

    ```bash
    elastro health score
    elastro health score -o json
    ```
    """
    client: ElasticsearchClient = ctx.obj
    try:
        report = _run_assessment(
            client,
            timeout=timeout,
            verbose_report=False,
            feature=None,
        )
        output_fmt = _output_format(ctx)
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

    try:
        result = health_manager.health_report(verbose=verbose, feature=feature)
        click.echo(format_output(result, output_format="json"))
    except OperationError as e:
        click.echo(f"Error fetching health report: {str(e)}", err=True)
        raise SystemExit(1) from e