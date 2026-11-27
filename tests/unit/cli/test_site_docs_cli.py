"""CLI copy-paste contract for elastro.fremenlabs.com examples."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from elastro.cli.cli import _hoist_root_output_option, cli


def test_hoist_output_after_subcommand() -> None:
    assert _hoist_root_output_option(["health", "assess", "-o", "table"]) == [
        "-o",
        "table",
        "health",
        "assess",
    ]
    assert _hoist_root_output_option(
        ["health", "assess", "--fail-on", "warn", "-o", "json"]
    ) == ["-o", "json", "health", "assess", "--fail-on", "warn"]


def test_hoist_skips_non_format_dash_o() -> None:
    args = ["ingest", "grok-builder", "-o", "pipeline.json"]
    assert _hoist_root_output_option(args) == args


def test_health_assess_accepts_output_after_subcommand() -> None:
    result = CliRunner().invoke(cli, ["health", "assess", "-o", "table", "--help"])
    assert result.exit_code == 0, result.output
    assert "No such option" not in result.output


def test_ingest_import_sql_does_not_require_source() -> None:
    runner = CliRunner()
    with patch("elastro.cli.commands.ingest.require_client"):
        with patch("elastro.core.ingest.engine.IngestEngine") as engine_cls:
            with patch("elastro.core.ingest.readers.SQLReader") as sql_reader:
                engine = MagicMock()
                engine.ingest.return_value = MagicMock(
                    total_read=0,
                    total_indexed=0,
                    total_failed=0,
                    success_rate=0.0,
                    elapsed_seconds=0.01,
                    dlq_path=None,
                )
                engine_cls.return_value = engine
                sql_reader.return_value.read.return_value = iter([])
                result = runner.invoke(
                    cli,
                    [
                        "ingest",
                        "import",
                        "--sql",
                        "SELECT * FROM users",
                        "--dsn",
                        "postgresql://user:pass@localhost/db",
                        "--index",
                        "users",
                    ],
                )
    assert "Missing argument 'SOURCE'" not in result.output
    assert result.exit_code != 2 or "Missing argument" not in result.output
