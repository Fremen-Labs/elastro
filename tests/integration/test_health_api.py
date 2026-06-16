"""Integration tests for GUI health API routes."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from elastro.health.models import (
    AssessmentReport,
    Finding,
    FindingStatus,
    Severity,
)
from elastro.server import ElastroGUI
from elastro.server.health_cache import clear_cache, store_report


def _mock_report(cluster_name: str = "docker-cluster") -> AssessmentReport:
    return AssessmentReport(
        session_id="api-test-session",
        cluster_name=cluster_name,
        elasticsearch_version="8.15.2",
        assessed_at=datetime(2026, 6, 15, tzinfo=timezone.utc),
        duration_ms=120,
        overall_score=82,
        overall_status=FindingStatus.WARN,
        findings=[
            Finding(
                id="indicator.shards_availability",
                category="shards",
                title="Shards Availability yellow",
                status=FindingStatus.WARN,
                severity=Severity.HIGH,
                summary="Replica shards unavailable",
                affected_resources=["logs-000001"],
            )
        ],
        collectors_run=["health_report", "cluster_health"],
    )


def _assess_side_effect(cluster_name, target, read_config, **kwargs):
    report = _mock_report(cluster_name)
    store_report(cluster_name, report)
    return report


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    clear_cache()
    gui = ElastroGUI()
    gui.token = "test-token"
    gui.config_dir = tmp_path
    gui.config_file = tmp_path / "gui_config.json"
    gui.config_file.write_text(
        '{"clusters": [{"name": "docker-cluster", "host": "http://localhost:9205", "auth": {}}]}'
    )
    return TestClient(gui.app), gui


@pytest.mark.integration
class TestHealthAPI:
    @patch("elastro.server.routes.health._run_assessment")
    def test_assess_endpoint(self, mock_run, api_client):
        client, _ = api_client
        mock_run.side_effect = _assess_side_effect

        response = client.get(
            "/api/clusters/docker-cluster/health/assess",
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["overall_score"] == 82
        assert payload["cluster_name"] == "docker-cluster"
        assert "raw_health_report" not in payload

    @patch("elastro.server.routes.health._run_assessment")
    def test_score_uses_cache(self, mock_run, api_client):
        client, _ = api_client
        mock_run.side_effect = _assess_side_effect

        first = client.get(
            "/api/clusters/docker-cluster/health/score",
            headers={"Authorization": "Bearer test-token"},
        )
        second = client.get(
            "/api/clusters/docker-cluster/health/score",
            headers={"Authorization": "Bearer test-token"},
        )

        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["cached"] is True
        assert mock_run.call_count == 1

    @patch("elastro.server.routes.health._run_assessment")
    def test_findings_endpoint(self, mock_run, api_client):
        client, _ = api_client
        mock_run.side_effect = _assess_side_effect

        client.get(
            "/api/clusters/docker-cluster/health/score",
            headers={"Authorization": "Bearer test-token"},
        )
        response = client.get(
            "/api/clusters/docker-cluster/health/findings",
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert len(payload["findings"]) == 1
        assert payload["findings"][0]["id"] == "indicator.shards_availability"

    @patch("elastro.server.routes.health.compute_trends_from_records")
    @patch("elastro.server.routes.health._load_cluster_history")
    @patch("elastro.server.routes.health._run_assessment")
    def test_trends_endpoint(
        self,
        mock_run,
        mock_load_history,
        mock_compute_from_records,
        api_client,
    ):
        from datetime import datetime, timedelta, timezone

        from elastro.health.trends import HistoryPoint, TrendReport

        client, _ = api_client
        assessed_at = datetime.now(timezone.utc) - timedelta(hours=2)
        mock_load_history.return_value = [
            {
                "cluster_name": "docker-cluster",
                "assessed_at": assessed_at.isoformat(),
                "overall_score": 70,
                "overall_status": "warn",
                "findings": [],
            },
            {
                "cluster_name": "docker-cluster",
                "assessed_at": (assessed_at - timedelta(hours=1)).isoformat(),
                "overall_score": 82,
                "overall_status": "warn",
                "findings": [],
            },
        ]
        mock_compute_from_records.return_value = TrendReport(
            cluster_name="docker-cluster",
            window="7d",
            sample_count=2,
            points=[
                HistoryPoint("2026-06-14T00:00:00+00:00", 70, "warn"),
                HistoryPoint("2026-06-15T00:00:00+00:00", 82, "warn"),
            ],
            score_delta_7d=12,
            source="cache",
        )

        response = client.get(
            "/api/clusters/docker-cluster/health/trends",
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["cluster_name"] == "docker-cluster"
        assert payload["score_delta_7d"] == 12
        assert len(payload["points"]) == 2
        mock_load_history.assert_called_once()
        mock_compute_from_records.assert_called_once()

    @patch("elastro.server.routes.health._run_assessment")
    def test_history_endpoint(self, mock_run, api_client):
        client, _ = api_client
        mock_run.side_effect = _assess_side_effect

        client.get(
            "/api/clusters/docker-cluster/health/assess",
            headers={"Authorization": "Bearer test-token"},
        )
        response = client.get(
            "/api/clusters/docker-cluster/health/history",
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == 200
        assert len(response.json()["assessments"]) == 1

    @patch("elastro.server.routes.health.NodesCollector.collect")
    @patch("elastro.server.routes.health.build_es_client")
    def test_nodes_endpoint(self, mock_build, mock_collect, api_client):
        client, _ = api_client
        mock_build.return_value = MagicMock()
        mock_collect.return_value = MagicMock(
            status="ok",
            data={
                "node_count": 1,
                "nodes": {
                    "n1": {
                        "name": "node-1",
                        "roles": ["data"],
                        "jvm": {"mem": {"heap_used_percent": 62}},
                        "fs": {
                            "total": {
                                "available_in_bytes": 400,
                                "total_in_bytes": 1000,
                            }
                        },
                    }
                },
            },
        )

        response = client.get(
            "/api/clusters/docker-cluster/health/nodes",
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == 200
        nodes = response.json()["nodes"]
        assert nodes[0]["heap_used_percent"] == 62
        assert nodes[0]["disk_used_percent"] == 60.0

    @patch("elastro.server.routes.health.RemediationExecutor")
    @patch("elastro.server.routes.health.build_es_client")
    def test_fix_dry_run(self, mock_build, mock_executor_cls, api_client):
        client, _ = api_client
        mock_build.return_value = MagicMock()
        mock_executor = MagicMock()
        mock_executor.execute_action.return_value = MagicMock(
            dry_run=True,
            success=True,
            message="Reduce replicas to 0",
            planned_api_call="PUT /index/_settings",
        )
        mock_executor_cls.return_value = mock_executor

        response = client.post(
            "/api/clusters/docker-cluster/health/fix",
            headers={"Authorization": "Bearer test-token"},
            json={
                "finding_id": "indicator.shards_availability",
                "action": "reduce_replicas",
                "index_name": "logs-000001",
                "dry_run": True,
            },
        )

        assert response.status_code == 200
        assert response.json()["status"] == "dry_run"

    def test_unauthorized(self, api_client):
        client, _ = api_client
        response = client.get("/api/clusters/docker-cluster/health/score")
        assert response.status_code == 401

    def test_cluster_not_found(self, api_client):
        client, _ = api_client
        response = client.get(
            "/api/clusters/missing/health/score",
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == 404


@pytest.mark.integration
class TestHealthFixAPI:
    def test_fix_unknown_action_returns_400(self, api_client):
        client, _ = api_client
        response = client.post(
            "/api/clusters/docker-cluster/health/fix",
            headers={"Authorization": "Bearer test-token"},
            json={
                "action": "not_a_real_action",
                "index_name": "logs-000001",
                "dry_run": True,
            },
        )
        assert response.status_code == 400
        assert "Unknown remediation action" in response.json()["detail"]

    def test_fix_missing_index_name_returns_400(self, api_client):
        client, _ = api_client
        response = client.post(
            "/api/clusters/docker-cluster/health/fix",
            headers={"Authorization": "Bearer test-token"},
            json={"action": "reduce_replicas", "dry_run": True},
        )
        assert response.status_code == 400
        assert "index_name is required" in response.json()["detail"]

    @patch("elastro.server.routes.health._run_assessment")
    @patch("elastro.server.routes.health.RemediationExecutor")
    @patch("elastro.server.routes.health.build_es_client")
    def test_fix_resolves_index_from_cached_finding(
        self, mock_build, mock_executor_cls, mock_run, api_client
    ):
        client, _ = api_client
        mock_run.side_effect = _assess_side_effect
        mock_build.return_value = MagicMock()
        mock_executor = MagicMock()
        mock_executor.execute_action.return_value = MagicMock(
            dry_run=True,
            success=True,
            message="Reduce replicas to 0",
            planned_api_call="PUT /logs-000001/_settings",
        )
        mock_executor_cls.return_value = mock_executor

        client.get(
            "/api/clusters/docker-cluster/health/score",
            headers={"Authorization": "Bearer test-token"},
        )
        response = client.post(
            "/api/clusters/docker-cluster/health/fix",
            headers={"Authorization": "Bearer test-token"},
            json={
                "finding_id": "indicator.shards_availability",
                "action": "reduce_replicas",
                "dry_run": True,
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["index_name"] == "logs-000001"
        mock_executor.execute_action.assert_called_once_with(
            "reduce_replicas", "logs-000001"
        )

    @patch("elastro.server.routes.health.RemediationExecutor")
    @patch("elastro.server.routes.health.build_es_client")
    def test_fix_execute_success(self, mock_build, mock_executor_cls, api_client):
        client, _ = api_client
        mock_build.return_value = MagicMock()
        mock_executor = MagicMock()
        mock_executor.execute_action.return_value = MagicMock(
            dry_run=False,
            success=True,
            message="Replicas reduced to 0",
            planned_api_call="PUT /logs-000001/_settings",
        )
        mock_executor_cls.return_value = mock_executor

        response = client.post(
            "/api/clusters/docker-cluster/health/fix",
            headers={"Authorization": "Bearer test-token"},
            json={
                "action": "reduce_replicas",
                "index_name": "logs-000001",
                "dry_run": False,
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "success"
        assert payload["message"] == "Replicas reduced to 0"

    @patch("elastro.server.routes.health.RemediationExecutor")
    @patch("elastro.server.routes.health.build_es_client")
    def test_fix_execute_failure_returns_500(
        self, mock_build, mock_executor_cls, api_client
    ):
        client, _ = api_client
        mock_build.return_value = MagicMock()
        mock_executor = MagicMock()
        mock_executor.execute_action.return_value = MagicMock(
            dry_run=False,
            success=False,
            message="Elasticsearch rejected settings update",
        )
        mock_executor_cls.return_value = mock_executor

        response = client.post(
            "/api/clusters/docker-cluster/health/fix",
            headers={"Authorization": "Bearer test-token"},
            json={
                "action": "reduce_replicas",
                "index_name": "logs-000001",
                "dry_run": False,
            },
        )

        assert response.status_code == 500
        assert "Elasticsearch rejected settings update" in response.json()["detail"]

    @patch("elastro.server.routes.health.RemediationExecutor")
    @patch("elastro.server.routes.health.build_es_client")
    def test_fix_reroute_alias_maps_to_reroute_failed(
        self, mock_build, mock_executor_cls, api_client
    ):
        client, _ = api_client
        mock_build.return_value = MagicMock()
        mock_executor = MagicMock()
        mock_executor.execute_action.return_value = MagicMock(
            dry_run=True,
            success=True,
            message="Retry failed shard allocation",
            planned_api_call="POST /_cluster/reroute",
        )
        mock_executor_cls.return_value = mock_executor

        response = client.post(
            "/api/clusters/docker-cluster/health/fix",
            headers={"Authorization": "Bearer test-token"},
            json={"action": "reroute", "dry_run": True},
        )

        assert response.status_code == 200
        assert response.json()["action"] == "reroute_failed"
        mock_executor.execute_action.assert_called_once_with("reroute_failed", None)


@pytest.mark.integration
class TestUnhealthyIndicesAPI:
    def _allocation_explain(
        self,
        *,
        reason: str = "REPLICA_ADDED",
        routing_filter: bool = False,
    ) -> dict:
        deciders = [
            {
                "decision": "NO",
                "explanation": "too many copies of shard allocated on this node",
            }
        ]
        if routing_filter:
            deciders.append(
                {
                    "decision": "NO",
                    "decider": "filter",
                    "explanation": "index.routing.allocation.require does not match",
                }
            )
        return {
            "allocate_explanation": (
                "Elasticsearch isn't allowed to allocate this shard on any of the nodes"
            ),
            "unassigned_info": {"reason": reason},
            "node_allocation_decisions": [{"deciders": deciders}],
        }

    @patch("elastro.core.index.IndexManager")
    @patch("elastro.server.routes.indices.build_es_client")
    def test_unhealthy_indices_returns_yellow_and_red(
        self, mock_build, mock_index_manager_cls, api_client
    ):
        client, _ = api_client
        mock_build.return_value = MagicMock()
        mock_idx_mgr = MagicMock()
        mock_idx_mgr.list.return_value = [
            {"index": "logs-000001", "health": "yellow", "status": "open"},
            {"index": "healthy-index", "health": "green", "status": "open"},
            {"index": "broken-index", "health": "red", "status": "open"},
        ]
        mock_idx_mgr.allocation_explain.side_effect = [
            self._allocation_explain(),
            self._allocation_explain(reason="ALLOCATION_FAILED", routing_filter=True),
        ]
        mock_index_manager_cls.return_value = mock_idx_mgr

        response = client.get(
            "/api/clusters/docker-cluster/indices/unhealthy",
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == 200
        indices = response.json()["indices"]
        assert len(indices) == 2
        assert indices[0]["index"] == "logs-000001"
        assert indices[0]["reason"] == "REPLICA_ADDED"
        assert "Allocation blocked:" in indices[0]["allocate_explanation"]
        assert indices[1]["index"] == "broken-index"
        assert indices[1]["routing_filter_fault"] is True

    @patch("elastro.core.index.IndexManager")
    @patch("elastro.server.routes.indices.build_es_client")
    def test_unhealthy_indices_empty_when_all_green(
        self, mock_build, mock_index_manager_cls, api_client
    ):
        client, _ = api_client
        mock_build.return_value = MagicMock()
        mock_idx_mgr = MagicMock()
        mock_idx_mgr.list.return_value = [
            {"index": "healthy-index", "health": "green", "status": "open"},
        ]
        mock_index_manager_cls.return_value = mock_idx_mgr

        response = client.get(
            "/api/clusters/docker-cluster/indices/unhealthy",
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == 200
        assert response.json()["indices"] == []

    @patch("elastro.core.index.IndexManager")
    @patch("elastro.server.routes.indices.build_es_client")
    def test_unhealthy_indices_handles_allocation_explain_failure(
        self, mock_build, mock_index_manager_cls, api_client
    ):
        client, _ = api_client
        mock_build.return_value = MagicMock()
        mock_idx_mgr = MagicMock()
        mock_idx_mgr.list.return_value = [
            {"index": "logs-000001", "health": "yellow", "status": "open"},
        ]
        mock_idx_mgr.allocation_explain.side_effect = RuntimeError("explain failed")
        mock_index_manager_cls.return_value = mock_idx_mgr

        response = client.get(
            "/api/clusters/docker-cluster/indices/unhealthy",
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == 200
        payload = response.json()["indices"][0]
        assert payload["allocate_explanation"] == "Failed to fetch explanation"
        assert payload["reason"] == "ERROR"

    def test_unhealthy_indices_unauthorized(self, api_client):
        client, _ = api_client
        response = client.get("/api/clusters/docker-cluster/indices/unhealthy")
        assert response.status_code == 401

    def test_unhealthy_indices_cluster_not_found(self, api_client):
        client, _ = api_client
        response = client.get(
            "/api/clusters/missing/indices/unhealthy",
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == 404


@pytest.mark.integration
class TestIndexFixAPI:
    @patch("elastro.health.remediation.executor.RemediationExecutor")
    @patch("elastro.server.routes.indices.build_es_client")
    def test_index_fix_dry_run(self, mock_build, mock_executor_cls, api_client):
        client, _ = api_client
        mock_build.return_value = MagicMock()
        mock_executor = MagicMock()
        mock_executor.execute_action.return_value = MagicMock(
            dry_run=True,
            success=True,
            planned_api_call="PUT /logs-000001/_settings",
        )
        mock_executor_cls.return_value = mock_executor

        response = client.post(
            "/api/clusters/docker-cluster/indices/logs-000001/fix",
            headers={"Authorization": "Bearer test-token"},
            json={"action": "reduce_replicas", "dry_run": True},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "dry_run"
        assert "PUT /logs-000001/_settings" in response.json()["planned_api_call"]

    @patch("elastro.health.remediation.executor.RemediationExecutor")
    @patch("elastro.server.routes.indices.build_es_client")
    def test_index_fix_execute_success(self, mock_build, mock_executor_cls, api_client):
        client, _ = api_client
        mock_build.return_value = MagicMock()
        mock_executor = MagicMock()
        mock_executor.execute_action.return_value = MagicMock(
            dry_run=False,
            success=True,
            message="Replicas reduced to 0",
        )
        mock_executor_cls.return_value = mock_executor

        response = client.post(
            "/api/clusters/docker-cluster/indices/logs-000001/fix",
            headers={"Authorization": "Bearer test-token"},
            json={"action": "reduce_replicas", "dry_run": False},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "success"

    @patch("elastro.health.remediation.executor.RemediationExecutor")
    @patch("elastro.server.routes.indices.build_es_client")
    def test_index_fix_execute_failure_returns_500(
        self, mock_build, mock_executor_cls, api_client
    ):
        client, _ = api_client
        mock_build.return_value = MagicMock()
        mock_executor = MagicMock()
        mock_executor.execute_action.return_value = MagicMock(
            dry_run=False,
            success=False,
            message="Shard allocation still blocked",
        )
        mock_executor_cls.return_value = mock_executor

        response = client.post(
            "/api/clusters/docker-cluster/indices/logs-000001/fix",
            headers={"Authorization": "Bearer test-token"},
            json={"action": "reroute", "dry_run": False},
        )

        assert response.status_code == 500
        assert "Shard allocation still blocked" in response.json()["detail"]
