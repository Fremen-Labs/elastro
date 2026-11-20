"""Gated live CLI/API smoke. Skips when Elasticsearch is not reachable."""

import pytest

from elastro.core.cluster import ClusterManager
from elastro.health.manager import HealthManager


@pytest.mark.integration
def test_live_allocation_explain_green_or_unassigned(real_es_client) -> None:
    result = ClusterManager(real_es_client).allocation_explain()
    assert isinstance(result, dict)
    if result.get("message"):
        assert "no unassigned shards" in str(result["message"]).lower()
    else:
        assert "index" in result or "current_state" in result


@pytest.mark.integration
def test_live_cluster_health_smoke(real_es_client) -> None:
    health = HealthManager(real_es_client).cluster_health()
    assert health.get("status") in {"green", "yellow", "red"}
