"""CLI tests for the coverage command group."""

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from elastro.cli.cli import cli
from elastro.cli.commands.coverage import coverage_group
from elastro.core.errors import OperationError
from elastro.coverage.readiness import ReadinessReport
from elastro.coverage.templates import TemplateApplyResult, TemplateInfo
from elastro.coverage.validators import CoverageCheck, CoverageReport


def _client() -> MagicMock:
    client = MagicMock()
    client.is_connected.return_value = True
    client.get_client.return_value = client.client
    return client


def _pass_report() -> CoverageReport:
    return CoverageReport(
        passed=True,
        target="pattern:traces-apm*",
        window="15m",
        checks=[
            CoverageCheck(
                name="doc_count", passed=True, summary="150 docs", doc_count=150
            )
        ],
        doc_count=150,
    )


def _fail_report() -> CoverageReport:
    return CoverageReport(
        passed=False,
        target="pattern:traces-apm*",
        window="15m",
        checks=[
            CoverageCheck(name="doc_count", passed=False, summary="0 docs", doc_count=0)
        ],
        doc_count=0,
    )


def test_check_failed_exits_2() -> None:
    client = _client()
    with patch("elastro.cli.commands.coverage.CoverageValidator") as cls:
        cls.return_value.check_pattern.return_value = _fail_report()
        result = CliRunner().invoke(
            coverage_group, ["check", "--pattern", "traces-apm*"], obj=client
        )
    assert result.exit_code == 2
    assert "doc_count" in result.output


def test_check_success_exits_0() -> None:
    client = _client()
    with patch("elastro.cli.commands.coverage.CoverageValidator") as cls:
        cls.return_value.check_pattern.return_value = _pass_report()
        result = CliRunner().invoke(
            coverage_group, ["check", "--pattern", "traces-apm*"], obj=client
        )
    assert result.exit_code == 0, result.output


def test_check_operation_error_exits_1() -> None:
    client = _client()
    with patch("elastro.cli.commands.coverage.CoverageValidator") as cls:
        cls.return_value.check_pattern.side_effect = OperationError("cluster down")
        result = CliRunner().invoke(
            coverage_group, ["check", "--pattern", "traces-apm*"], obj=client
        )
    assert result.exit_code == 1
    assert "cluster down" in result.stderr


def test_check_requires_selector() -> None:
    result = CliRunner().invoke(coverage_group, ["check"], obj=_client())
    assert result.exit_code == 2
    assert "--service" in result.stderr


def test_templates_apply_dry_run_does_not_put() -> None:
    client = _client()
    planned = TemplateApplyResult(
        name="apm-traces",
        dry_run=True,
        ilm_policy_name="elastro-apm-traces",
        ilm_policy={"policy": {"phases": {}}},
        index_template_name="elastro-apm-traces",
        index_template={"index_patterns": ["traces-apm*"]},
        applied=False,
    )
    with patch("elastro.cli.commands.coverage.TemplateManager") as cls:
        cls.return_value.apply.return_value = planned
        result = CliRunner().invoke(
            coverage_group,
            ["templates", "apply", "apm-traces", "--dry-run"],
            obj=client,
        )
    assert result.exit_code == 0, result.output
    cls.assert_called_once_with()
    cls.return_value.apply.assert_called_once()
    assert cls.return_value.apply.call_args.kwargs["dry_run"] is True
    client.client.ilm.put_lifecycle.assert_not_called()
    client.client.indices.put_index_template.assert_not_called()


def test_templates_apply_without_yes_non_tty_exits_2() -> None:
    client = _client()
    with patch("elastro.cli.commands.coverage.TemplateManager") as cls:
        result = CliRunner().invoke(
            coverage_group, ["templates", "apply", "apm-traces"], obj=client
        )
    assert result.exit_code == 2
    assert "--yes" in result.stderr
    cls.return_value.apply.assert_not_called()


def test_templates_apply_yes_calls_apply() -> None:
    client = _client()
    applied = TemplateApplyResult(
        name="apm-traces",
        dry_run=False,
        ilm_policy_name="elastro-apm-traces",
        ilm_policy={"policy": {"phases": {}}},
        index_template_name="elastro-apm-traces",
        index_template={"index_patterns": ["traces-apm*"]},
        applied=True,
    )
    with patch("elastro.cli.commands.coverage.TemplateManager") as cls:
        cls.return_value.apply.return_value = applied
        result = CliRunner().invoke(
            coverage_group,
            ["templates", "apply", "apm-traces", "--yes"],
            obj=client,
        )
    assert result.exit_code == 0, result.output
    cls.return_value.apply.assert_called_once()
    assert cls.return_value.apply.call_args.kwargs["dry_run"] is False


def test_templates_list_outputs_names() -> None:
    with patch("elastro.cli.commands.coverage.TemplateManager") as cls:
        cls.return_value.list.return_value = [
            TemplateInfo(name="apm-traces", description="traces")
        ]
        result = CliRunner().invoke(
            coverage_group, ["templates", "list"], obj=_client()
        )
    assert result.exit_code == 0, result.output
    assert "apm-traces" in result.output


def test_root_cli_check_honors_output_json() -> None:
    with patch("elastro.cli.cli.ElasticsearchClient.connect"):
        with patch("elastro.cli.commands.coverage.CoverageValidator") as cls:
            cls.return_value.check_all.return_value = _pass_report()
            result = CliRunner().invoke(
                cli, ["-o", "json", "coverage", "check", "--all"]
            )
    assert result.exit_code == 0, result.output
    assert '"passed"' in result.output


def test_coverage_report_failed_exits_2() -> None:
    client = _client()
    failed = ReadinessReport(
        passed=False,
        templates=[],
        coverage=_fail_report(),
        health_findings=[],
    )
    with patch("elastro.coverage.readiness.ReadinessReporter") as cls:
        cls.return_value.report.return_value = failed
        result = CliRunner().invoke(coverage_group, ["report"], obj=client)
    assert result.exit_code == 2


def test_check_all_help_documents_and_gate() -> None:
    result = CliRunner().invoke(coverage_group, ["check", "--help"])
    assert result.exit_code == 0, result.output
    help_text = result.output
    assert "AND-gate" in help_text or "AND-gate" in help_text.replace("`", "")
    assert "traces-apm*" in help_text
    assert "metrics-apm*" in help_text
    assert "filebeat-*" in help_text
    assert "metricbeat-*" in help_text
    assert "logs-filebeat*" in help_text
    assert "metrics-metricbeat*" in help_text


def test_fleet_status_imports_on_demand() -> None:
    from elastro.coverage.fleet import FleetStatus

    with patch("elastro.coverage.fleet.FleetClient") as cls:
        cls.from_config.return_value.status.return_value = FleetStatus(
            total=2, online=2
        )
        result = CliRunner().invoke(coverage_group, ["fleet", "status"], obj=_client())
    assert result.exit_code == 0, result.output
    assert cls.from_config.called
