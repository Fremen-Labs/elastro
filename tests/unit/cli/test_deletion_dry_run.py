"""Unit tests for delete command dry-run previews."""

import json
from unittest.mock import MagicMock, patch

import pytest

from elastro.cli.deletion import (
    DeletePreview,
    delete_preview_payload,
    preview_bulk_document_delete,
    preview_index_delete,
    preview_template_delete,
    should_prompt_for_delete,
)


class TestDeleteDryRunHelpers:
    def test_should_prompt_for_delete(self):
        assert should_prompt_for_delete(dry_run=True, force=True) is False
        assert should_prompt_for_delete(dry_run=False, force=True) is False
        assert should_prompt_for_delete(dry_run=False, yes=True) is False
        assert should_prompt_for_delete(dry_run=False, force=False) is True

    def test_delete_preview_payload_summary(self):
        preview = DeletePreview(
            action="index.delete",
            resource_type="index",
            resource_id="logs-2024",
            exists=True,
            planned_api_call="DELETE /logs-2024",
            message="Would delete",
        )
        payload = delete_preview_payload(preview)
        assert payload["summary"]["preview_only"] is True
        assert payload["summary"]["executed_count"] == 0
        assert payload["summary"]["would_execute"] is True


class TestDeletePreviewBuilders:
    def test_preview_index_delete_exists(self):
        client = MagicMock()
        with patch("elastro.cli.deletion.IndexManager") as mock_mgr_cls:
            mock_mgr_cls.return_value.exists.return_value = True
            preview = preview_index_delete(client, "logs-2024")

        assert preview.exists is True
        assert preview.planned_api_call == "DELETE /logs-2024"
        assert preview.dry_run is True
        assert preview.executed is False

    def test_preview_template_delete_missing(self):
        client = MagicMock()
        with patch("elastro.cli.deletion.TemplateManager") as mock_mgr_cls:
            mock_mgr_cls.return_value.get.return_value = {}
            preview = preview_template_delete(client, "missing-template")

        assert preview.exists is False
        assert "DELETE /_index_template/missing-template" in preview.planned_api_call

    def test_preview_bulk_document_delete_metadata(self):
        client = MagicMock()
        with patch("elastro.cli.deletion.IndexManager") as mock_mgr_cls:
            mock_mgr_cls.return_value.exists.return_value = True
            preview = preview_bulk_document_delete(client, "logs-2024", ["a", "b", "c"])

        assert preview.metadata["id_count"] == 3
        assert "POST /_bulk" in preview.planned_api_call


@pytest.mark.integration
class TestDeleteCommandDryRunCLI:
    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.cli.deletion.preview_index_delete")
    def test_index_delete_dry_run_json(self, mock_preview, mock_connect, runner=None):
        from click.testing import CliRunner

        from elastro.cli.cli import cli
        from elastro.cli.deletion import DeletePreview

        runner = runner or CliRunner()
        mock_connect.return_value = None
        mock_preview.return_value = DeletePreview(
            action="index.delete",
            resource_type="index",
            resource_id="logs-2024",
            exists=True,
            planned_api_call="DELETE /logs-2024",
            message="Would delete index 'logs-2024' and all its data.",
        )

        result = runner.invoke(
            cli,
            ["-h", "http://localhost:9205", "-o", "json", "index", "delete", "logs-2024", "--dry-run"],
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["dry_run"] is True
        assert payload["summary"]["preview_only"] is True
        assert payload["planned_api_call"] == "DELETE /logs-2024"
        mock_preview.assert_called_once()

    @patch("elastro.cli.cli.ElasticsearchClient.connect")
    @patch("elastro.cli.deletion.preview_index_delete")
    def test_index_delete_dry_run_skips_confirm(self, mock_preview, mock_connect):
        from click.testing import CliRunner

        from elastro.cli.cli import cli
        from elastro.cli.deletion import DeletePreview

        runner = CliRunner()
        mock_connect.return_value = None
        mock_preview.return_value = DeletePreview(
            action="index.delete",
            resource_type="index",
            resource_id="logs-2024",
            exists=True,
            planned_api_call="DELETE /logs-2024",
            message="Would delete",
        )

        result = runner.invoke(
            cli,
            [
                "-h",
                "http://localhost:9205",
                "-o",
                "table",
                "index",
                "delete",
                "logs-2024",
                "--dry-run",
            ],
            input="n\n",
        )

        assert result.exit_code == 0, result.output
        assert "Delete preview (dry-run)" in result.output
        assert "DELETE /logs-2024" in result.output