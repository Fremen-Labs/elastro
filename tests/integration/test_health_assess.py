"""Integration tests for elastro health assess CLI."""

import json
import os
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from elastro.cli.cli import cli
from elastro.health.models import (
    AssessmentReport,
    Finding,
    FindingStatus,
    Severity,
)


def _mock_report() -> AssessmentReport:
    return AssessmentReport(
        session_id="test-session",
        cluster_name="docker-cluster",
        elasticsearch_version="8.15.2",
        assessed_at=datetime(2026, 6, 15, tzinfo=timezone.utc),
        duration_ms=45,
        overall_score=88,
        overall_status=FindingStatus.WARN,
        findings=[
            Finding(
                id="indicator.shards_availability",
                category="shards",
                title="Shards Availability yellow",
                status=FindingStatus.WARN,
                severity=Severity.HIGH,
                summary="15 unavailable replica shards",
                indicator="shards_availability",
            )
        ],
        collectors_run=["health_report", "cluster_health", "pending_tasks"],
    )


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.mark.integration
class TestHealthAssessCLI:
    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.cli.commands.health.HealthAssessor")
    def test_assess_json_output(self, mock_assessor_cls, mock_connect, runner):
        mock_connect.return_value = None
        mock_assessor_cls.return_value.run.return_value = _mock_report()

        result = runner.invoke(
            cli,
            ["-h", "http://localhost:9205", "-o", "json", "health", "assess"],
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output.strip())
        assert payload["cluster_name"] == "docker-cluster"
        assert payload["overall_score"] == 88
        assert payload["schema_version"] == "1.0"
        assert len(payload["findings"]) == 1
        AssessmentReport.model_validate(payload)

    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.cli.commands.health.HealthAssessor")
    def test_assess_table_output(self, mock_assessor_cls, mock_connect, runner):
        mock_connect.return_value = None
        mock_assessor_cls.return_value.run.return_value = _mock_report()

        result = runner.invoke(
            cli,
            ["-h", "http://localhost:9205", "-o", "table", "health", "assess"],
        )

        assert result.exit_code == 0, result.output
        assert "docker-cluster" in result.output
        assert "88/100" in result.output
        assert "Shards Availability" in result.output
        assert "15 unavailable replica shards" in result.output

    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.cli.commands.health.HealthAssessor")
    def test_assess_completes_under_five_seconds(
        self, mock_assessor_cls, mock_connect, runner
    ):
        mock_connect.return_value = None
        report = _mock_report()
        report.duration_ms = 120
        mock_assessor_cls.return_value.run.return_value = report

        start = time.monotonic()
        result = runner.invoke(
            cli,
            ["-h", "http://localhost:9205", "-o", "json", "health", "assess"],
        )
        elapsed = time.monotonic() - start

        assert result.exit_code == 0
        assert elapsed < 5.0

    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.cli.commands.health.HealthAssessor")
    def test_assess_exits_two_on_fail_status(
        self, mock_assessor_cls, mock_connect, runner
    ):
        mock_connect.return_value = None
        report = _mock_report()
        report.overall_score = 30
        report.overall_status = FindingStatus.FAIL
        mock_assessor_cls.return_value.run.return_value = report

        result = runner.invoke(
            cli,
            ["-h", "http://localhost:9205", "-o", "json", "health", "assess"],
        )

        assert result.exit_code == 2
        assert "docker-cluster" in result.output

    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.cli.commands.health.HealthAssessor")
    def test_assess_passes_first_feature_only(
        self, mock_assessor_cls, mock_connect, runner
    ):
        mock_connect.return_value = None
        mock_assessor_cls.return_value.run.return_value = _mock_report()

        runner.invoke(
            cli,
            [
                "-h",
                "http://localhost:9205",
                "health",
                "assess",
                "--feature",
                "disk",
                "--feature",
                "shards_availability",
            ],
        )

        mock_assessor_cls.return_value.run.assert_called_once()
        assert mock_assessor_cls.return_value.run.call_args.kwargs["feature"] == "disk"

    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.cli.commands.health.HealthAssessor")
    @patch("elastro.health.remediation.diagnosis.diagnose_unhealthy_indices")
    def test_assess_fix_dry_run_prints_planned_calls(
        self,
        mock_diagnose,
        mock_assessor_cls,
        mock_connect,
        runner,
    ):
        from elastro.health.remediation.models import IndexDiagnosis

        mock_connect.return_value = None
        mock_assessor_cls.return_value.run.return_value = _mock_report()
        mock_diagnose.return_value = [
            IndexDiagnosis(
                index_name="logs-2024",
                health="yellow",
                suggested_action_id="reduce_replicas",
                suggestion_text="Reduce replicas",
            )
        ]

        with patch(
            "elastro.health.remediation.executor.RemediationExecutor.remediate_diagnosis",
            return_value=MagicMock(
                action_id="reduce_replicas",
                index_name="logs-2024",
                success=True,
                executed=False,
                dry_run=True,
                planned_api_call="PUT /logs-2024/_settings body={'index': {'number_of_replicas': 0}}",
                message="Reduce replicas to 0",
            ),
        ):
            result = runner.invoke(
                cli,
                [
                    "-h",
                    "http://localhost:9205",
                    "-o",
                    "table",
                    "health",
                    "assess",
                    "--fix",
                    "--dry-run",
                ],
            )

        assert result.exit_code == 0, result.output
        assert "Planned remediations (dry-run)" in result.output
        assert "logs-2024" in result.output
        assert "PUT /logs-2024/_settings" in result.output

    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.cli.commands.health.HealthAssessor")
    def test_dry_run_requires_fix(self, mock_assessor_cls, mock_connect, runner):
        mock_connect.return_value = None
        mock_assessor_cls.return_value.run.return_value = _mock_report()

        result = runner.invoke(
            cli,
            ["-h", "http://localhost:9205", "health", "assess", "--dry-run"],
        )

        assert result.exit_code == 2
        assert "--dry-run requires --fix" in result.output

    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.cli.commands.health.HealthAssessor")
    def test_score_command(self, mock_assessor_cls, mock_connect, runner):
        mock_connect.return_value = None
        mock_assessor_cls.return_value.run.return_value = _mock_report()

        result = runner.invoke(
            cli,
            ["-h", "http://localhost:9205", "-o", "table", "health", "score"],
        )

        assert result.exit_code == 0, result.output
        assert "docker-cluster: 88/100" in result.output
        assert "1 finding" in result.output


@pytest.mark.integration
class TestHealthAssessLive:
    """Live tests against local-elastro-brain (localhost:9205)."""

    @pytest.fixture
    def live_available(self):
        from elasticsearch import Elasticsearch

        password = os.environ.get("ELASTIC_PASSWORD", "GA5UM2tsITwwuelI4JWX")
        try:
            es = Elasticsearch(
                "http://localhost:9205",
                basic_auth=("elastic", password),
                verify_certs=False,
                request_timeout=5,
            )
            es.info()
            return True
        except Exception:
            pytest.skip("local-elastro-brain not available on localhost:9205")

    def test_live_assess_table(self, runner, live_available):
        result = runner.invoke(
            cli,
            [
                "-h",
                "http://localhost:9205",
                "-o",
                "table",
                "health",
                "assess",
                "--no-verbose-report",
            ],
            env={"ELASTRO_LOG_LEVEL": "ERROR"},
        )
        assert result.exit_code == 0, result.output
        assert "docker-cluster" in result.output
        assert "/100" in result.output

    def test_live_assess_json_validates_schema(self, runner, live_available):
        result = runner.invoke(
            cli,
            [
                "-h",
                "http://localhost:9205",
                "-o",
                "json",
                "health",
                "assess",
                "--no-verbose-report",
            ],
            env={"ELASTRO_LOG_LEVEL": "ERROR"},
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output.strip())
        report = AssessmentReport.model_validate(payload)
        assert report.elasticsearch_version.startswith("8.")
        assert report.overall_score > 0