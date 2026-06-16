"""Unit tests for ILM status helpers."""

from unittest.mock import MagicMock, patch

from elastro.core.client import ElasticsearchClient
from elastro.health.ilm_status import list_stuck_ilm_indices


class TestListStuckIlmIndices:
    @patch("elastro.health.ilm_status.IlmManager")
    @patch("elastro.health.ilm_status.IndexManager")
    def test_returns_stuck_indices(self, mock_index_manager_cls, mock_ilm_manager_cls):
        client = MagicMock(spec=ElasticsearchClient)
        mock_index_manager_cls.return_value.list.return_value = [
            {"index": "logs-000001", "health": "yellow"},
        ]
        mock_ilm_manager_cls.return_value.explain_lifecycle.return_value = {
            "managed": True,
            "step": "ERROR",
            "step_info": "snapshot failed",
        }

        stuck = list_stuck_ilm_indices(client)

        assert len(stuck) == 1
        assert stuck[0].index_name == "logs-000001"
        assert "snapshot failed" in stuck[0].issue
