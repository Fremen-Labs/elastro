"""Unit tests for ClusterManager."""

import pytest

from elastro.core.cluster import ClusterManager
from elastro.core.errors import OperationError, ValidationError


class TestClusterManager:
    def test_get_settings(self, es_client) -> None:
        payload = {
            "persistent": {"cluster.routing.allocation.enable": "all"},
            "transient": {},
        }
        es_client.client.cluster.get_settings.return_value = payload

        result = ClusterManager(es_client).get_settings()

        assert result == payload
        es_client.client.cluster.get_settings.assert_called_once_with(
            flat_settings=True
        )

    def test_get_settings_transport_error(self, es_client) -> None:
        es_client.client.cluster.get_settings.side_effect = Exception("No node reached")

        with pytest.raises(OperationError, match="Failed to get cluster settings"):
            ClusterManager(es_client).get_settings()

    def test_enable_routing_payload(self, es_client) -> None:
        es_client.client.cluster.put_settings.return_value = {"acknowledged": True}

        result = ClusterManager(es_client).enable_routing("primaries")

        assert result == {"acknowledged": True}
        es_client.client.cluster.put_settings.assert_called_once_with(
            body={"transient": {"cluster.routing.allocation.enable": "primaries"}}
        )

    def test_enable_routing_transport_error(self, es_client) -> None:
        es_client.client.cluster.put_settings.side_effect = Exception("No node reached")

        with pytest.raises(OperationError, match="Failed to update cluster settings"):
            ClusterManager(es_client).enable_routing("all")

    def test_enable_routing_invalid_value(self, es_client) -> None:
        with pytest.raises(ValidationError, match="Invalid routing allocation enable"):
            ClusterManager(es_client).enable_routing("sometimes")
        es_client.client.cluster.put_settings.assert_not_called()

    def test_allocation_explain_cluster(self, es_client) -> None:
        payload = {
            "index": "logs",
            "shard": 0,
            "primary": True,
            "current_state": "unassigned",
        }
        es_client.client.cluster.allocation_explain.return_value = payload

        result = ClusterManager(es_client).allocation_explain()

        assert result == payload
        es_client.client.cluster.allocation_explain.assert_called_once_with()
        es_client.client.cat.shards.assert_not_called()

    def test_allocation_explain_no_unassigned_shards(self, es_client) -> None:
        class BadRequest(Exception):
            status_code = 400

            def __str__(self) -> str:
                return "No shard was specified"

        es_client.client.cluster.allocation_explain.side_effect = BadRequest()

        result = ClusterManager(es_client).allocation_explain()

        assert result == {"message": "no unassigned shards to explain"}

    def test_allocation_explain_other_400_is_error(self, es_client) -> None:
        class BadRequest(Exception):
            status_code = 400
            body = {"error": {"reason": "invalid allocation request"}}

            def __str__(self) -> str:
                return "invalid allocation request"

        es_client.client.cluster.allocation_explain.side_effect = BadRequest()

        with pytest.raises(OperationError, match="Failed to explain allocation"):
            ClusterManager(es_client).allocation_explain()
