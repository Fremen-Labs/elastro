"""Unit tests for GUI cluster inventory metrics."""

from unittest.mock import MagicMock

from elastro.server.cluster_inventory import fetch_cluster_inventory


def _mock_es():
    es = MagicMock()
    es.cluster.health.return_value = {"status": "yellow"}
    es.nodes.info.return_value = {
        "_nodes": {"total": 3},
        "nodes": {
            "n1": {"roles": ["data", "master"]},
            "n2": {"roles": ["data"]},
            "n3": {"roles": ["ingest"]},
        },
    }
    es.cat.indices.return_value = [
        {"health": "green", "index": "logs-1"},
        {"health": "yellow", "index": "metrics-1"},
        {"health": "red", "index": "broken-1"},
    ]
    es.cat.shards.return_value = [
        {"index": "logs-1", "shard": "0", "state": "STARTED"},
        {"index": "logs-1", "shard": "1", "state": "UNASSIGNED"},
    ]
    es.cluster.stats.return_value = {
        "indices": {
            "docs": {"count": 1250000},
            "store": {"size_in_bytes": 5 * 1024**3},
        }
    }
    es.indices.get_data_stream.return_value = {
        "data_streams": [{"name": "logs"}, {"name": "metrics"}]
    }
    es.ilm.get_lifecycle.return_value = {"policy-a": {}, "policy-b": {}}
    es.indices.get_index_template.return_value = {
        "index_templates": [{"name": "logs-template"}]
    }
    es.indices.get_template.return_value = {"legacy-template": {}}
    es.snapshot.get_repository.return_value = {
        "repo1": {"type": "fs"},
    }

    def _cat_indices(**kwargs):
        if kwargs.get("index") == ".kibana*":
            return [{"index": ".kibana_1"}]
        return [
            {"health": "green", "index": "logs-1"},
            {"health": "yellow", "index": "metrics-1"},
            {"health": "red", "index": "broken-1"},
        ]

    es.cat.indices.side_effect = _cat_indices
    es.count.return_value = {"count": 12}
    return es


class TestClusterInventory:
    def test_fetch_cluster_inventory_aggregates_metrics(self):
        inventory = fetch_cluster_inventory(_mock_es())

        assert inventory["health"] == "yellow"
        assert inventory["nodes"]["total"] == 3
        assert inventory["indices"]["total"] == 3
        assert inventory["indices"]["green"] == 1
        assert inventory["indices"]["yellow"] == 1
        assert inventory["indices"]["red"] == 1
        assert inventory["shards"]["total"] == 2
        assert inventory["shards"]["unassigned"] == 1
        assert inventory["data_streams"]["total"] == 2
        assert inventory["ilm"]["policy_count"] == 2
        assert inventory["index_templates"]["total"] == 2
        assert inventory["documents"]["total"] == 1250000
        assert inventory["storage"]["total_bytes"] == 5 * 1024**3
        assert inventory["kibana"]["dashboards"] == 12
        assert inventory["backups"]["repository_count"] == 1
