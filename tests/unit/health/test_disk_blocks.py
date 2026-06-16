"""Unit tests for flood-stage read_only block discovery."""

from unittest.mock import MagicMock

from elastro.core.client import ElasticsearchClient
from elastro.core.index import IndexManager
from elastro.health.disk_blocks import discover_read_only_blocked_indices


class TestDiscoverReadOnlyBlockedIndices:
    def test_returns_blocked_indices(self):
        client = MagicMock(spec=ElasticsearchClient)
        es = MagicMock()
        client.get_client.return_value = es
        client.is_connected.return_value = True
        es.indices.get_settings.return_value = {
            "logs-000001": {
                "settings": {
                    "index": {
                        "blocks": {"read_only_allow_delete": "true"},
                    }
                }
            },
            "healthy": {
                "settings": {
                    "index": {
                        "blocks": {"read_only_allow_delete": "false"},
                    }
                }
            },
        }

        manager = IndexManager(client)
        blocked = discover_read_only_blocked_indices(manager)

        assert blocked == ["logs-000001"]
