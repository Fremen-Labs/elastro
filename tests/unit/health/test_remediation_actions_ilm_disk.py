"""Unit tests for ILM retry and clear_read_only remediation actions."""

from unittest.mock import MagicMock, patch

import pytest

from elastro.core.client import ElasticsearchClient
from elastro.core.index import IndexManager
from elastro.health.remediation.actions.clear_read_only import (
    clear_read_only,
    planned_clear_read_only,
)
from elastro.health.remediation.actions.ilm_retry import ilm_retry, planned_ilm_retry
from elastro.health.remediation.catalog import RemediationCatalog


class TestPlannedCalls:
    def test_planned_ilm_retry(self):
        assert planned_ilm_retry("logs-000001") == "POST /logs-000001/_ilm/retry"

    def test_planned_clear_read_only(self):
        assert "PUT /logs-000001/_settings" in planned_clear_read_only("logs-000001")
        assert "read_only_allow_delete" in planned_clear_read_only("logs-000001")


class TestCatalogEntries:
    def test_catalog_includes_new_actions(self):
        assert RemediationCatalog.get("ilm_retry") is not None
        assert RemediationCatalog.get("clear_read_only") is not None

    def test_catalog_planned_calls(self):
        assert "POST /logs-000001/_ilm/retry" == RemediationCatalog.planned_call(
            "ilm_retry",
            "logs-000001",
        )


class TestExecuteActions:
    @patch("elastro.health.remediation.actions.ilm_retry.IlmManager")
    def test_ilm_retry_executes(self, mock_ilm_cls):
        client = MagicMock(spec=ElasticsearchClient)
        manager = IndexManager(client)
        mock_ilm_cls.return_value.retry_lifecycle.return_value = True

        message = ilm_retry(manager, "logs-000001")

        mock_ilm_cls.return_value.retry_lifecycle.assert_called_once_with("logs-000001")
        assert "logs-000001" in message

    @patch.object(IndexManager, "update")
    def test_clear_read_only_executes(self, mock_update):
        client = MagicMock(spec=ElasticsearchClient)
        manager = IndexManager(client)

        message = clear_read_only(manager, "logs-000001")

        mock_update.assert_called_once()
        assert "logs-000001" in message