"""HTTP fix routes require force for CONFIRM and DESTRUCTIVE."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from elastro.health.models import RemediationSafety
from elastro.health.remediation.catalog import RemediationCatalog
from elastro.health.remediation.fix import run_health_fix
from elastro.health.remediation.models import IndexDiagnosis
from elastro.server import ElastroGUI
from elastro.server.health_cache import clear_cache


def _gui_client(tmp_path):
    clear_cache()
    gui = ElastroGUI()
    gui.token = "test-token"
    gui.config_dir = tmp_path
    gui.config_file = tmp_path / "gui_config.json"
    gui.config_file.write_text(
        '{"clusters": [{"name": "docker-cluster", '
        '"host": "http://localhost:9205", "auth": {}}]}'
    )
    return TestClient(gui.app)


def _auth_headers():
    return {"Authorization": "Bearer test-token"}


def _assert_confirmation_required(payload, *, action, safety):
    detail = payload["detail"]
    assert detail["code"] == "confirmation_required"
    assert detail["action"] == action
    assert detail["safety"] == safety
    expected = RemediationCatalog.planned_call(
        action,
        "logs-000001",
        api_payload=True,
    )
    assert detail["planned_api_call"] == expected


class TestHealthFixRouteSafety:
    def test_reduce_replicas_without_force_returns_409_before_execute(self, tmp_path):
        client = _gui_client(tmp_path)
        with (
            patch(
                "elastro.server.routes.health.RemediationExecutor"
            ) as mock_executor_cls,
            patch(
                "elastro.health.remediation.executor.resolve_replica_target"
            ) as mock_resolve,
            patch("elastro.core.index.IndexManager.update") as mock_update,
            patch("elastro.server.routes.health.build_es_client") as mock_build,
        ):
            mock_es = MagicMock()
            mock_build.return_value = mock_es
            response = client.post(
                "/api/clusters/docker-cluster/health/fix",
                headers=_auth_headers(),
                json={
                    "action": "reduce_replicas",
                    "index_name": "logs-000001",
                    "dry_run": False,
                    "force": False,
                },
            )

        assert response.status_code == 409
        _assert_confirmation_required(
            response.json(),
            action="reduce_replicas",
            safety=RemediationSafety.DESTRUCTIVE.value,
        )
        mock_executor_cls.assert_not_called()
        mock_executor_cls.return_value.execute_action.assert_not_called()
        mock_resolve.assert_not_called()
        mock_update.assert_not_called()
        mock_build.assert_not_called()
        mock_es.indices.put_settings.assert_not_called()

    def test_reduce_replicas_with_force_runs_executor(self, tmp_path):
        client = _gui_client(tmp_path)
        with (
            patch(
                "elastro.server.routes.health.RemediationExecutor"
            ) as mock_executor_cls,
            patch("elastro.server.routes.health.build_es_client") as mock_build,
        ):
            mock_build.return_value = MagicMock()
            mock_executor = MagicMock()
            mock_executor.execute_action.return_value = MagicMock(
                dry_run=False,
                success=True,
                message="Replicas reduced to 0",
                rollback_id=None,
            )
            mock_executor_cls.return_value = mock_executor
            response = client.post(
                "/api/clusters/docker-cluster/health/fix",
                headers=_auth_headers(),
                json={
                    "action": "reduce_replicas",
                    "index_name": "logs-000001",
                    "dry_run": False,
                    "force": True,
                },
            )

        assert response.status_code == 200
        assert response.json()["status"] == "success"
        mock_executor.execute_action.assert_called_once_with(
            "reduce_replicas", "logs-000001"
        )

    def test_dry_run_previews_without_force(self, tmp_path):
        client = _gui_client(tmp_path)
        with (
            patch(
                "elastro.server.routes.health.RemediationExecutor"
            ) as mock_executor_cls,
            patch("elastro.server.routes.health.build_es_client") as mock_build,
        ):
            mock_build.return_value = MagicMock()
            mock_executor = MagicMock()
            mock_executor.execute_action.return_value = MagicMock(
                dry_run=True,
                success=True,
                message="Reduce replicas to safe target",
                planned_api_call="PUT /logs-000001/_settings",
                rollback_id=None,
            )
            mock_executor_cls.return_value = mock_executor
            response = client.post(
                "/api/clusters/docker-cluster/health/fix",
                headers=_auth_headers(),
                json={
                    "action": "reduce_replicas",
                    "index_name": "logs-000001",
                    "dry_run": True,
                    "force": False,
                },
            )

        assert response.status_code == 200
        assert response.json()["status"] == "dry_run"
        mock_executor.execute_action.assert_called_once()


class TestIndexFixRouteSafety:
    def test_reduce_replicas_without_force_returns_409_before_execute(self, tmp_path):
        client = _gui_client(tmp_path)
        with (
            patch(
                "elastro.health.remediation.executor.RemediationExecutor"
            ) as mock_executor_cls,
            patch(
                "elastro.health.remediation.executor.resolve_replica_target"
            ) as mock_resolve,
            patch("elastro.core.index.IndexManager.update") as mock_update,
            patch("elastro.server.routes.indices.build_es_client") as mock_build,
        ):
            mock_es = MagicMock()
            mock_build.return_value = mock_es
            response = client.post(
                "/api/clusters/docker-cluster/indices/logs-000001/fix",
                headers=_auth_headers(),
                json={
                    "action": "reduce_replicas",
                    "dry_run": False,
                    "force": False,
                },
            )

        assert response.status_code == 409
        _assert_confirmation_required(
            response.json(),
            action="reduce_replicas",
            safety=RemediationSafety.DESTRUCTIVE.value,
        )
        mock_executor_cls.assert_not_called()
        mock_executor_cls.return_value.execute_action.assert_not_called()
        mock_resolve.assert_not_called()
        mock_update.assert_not_called()
        mock_build.assert_not_called()
        mock_es.indices.put_settings.assert_not_called()

    def test_reduce_replicas_with_force_runs_executor(self, tmp_path):
        client = _gui_client(tmp_path)
        with (
            patch(
                "elastro.health.remediation.executor.RemediationExecutor"
            ) as mock_executor_cls,
            patch("elastro.server.routes.indices.build_es_client") as mock_build,
        ):
            mock_build.return_value = MagicMock()
            mock_executor = MagicMock()
            mock_executor.execute_action.return_value = MagicMock(
                dry_run=False,
                success=True,
                message="Replicas reduced to 0",
                rollback_id=None,
            )
            mock_executor_cls.return_value = mock_executor
            response = client.post(
                "/api/clusters/docker-cluster/indices/logs-000001/fix",
                headers=_auth_headers(),
                json={
                    "action": "reduce_replicas",
                    "dry_run": False,
                    "force": True,
                },
            )

        assert response.status_code == 200
        assert response.json()["status"] == "success"
        mock_executor.execute_action.assert_called_once_with(
            "reduce_replicas", "logs-000001"
        )


class TestCliFixGateUnchanged:
    @patch(
        "elastro.health.remediation.catalog.RemediationCatalog.execute",
        return_value="done",
    )
    @patch("elastro.health.remediation.fix.diagnose_unhealthy_indices")
    def test_confirm_with_yes_without_force_executes(self, mock_diagnose, mock_execute):
        mock_diagnose.return_value = [
            IndexDiagnosis(
                index_name="logs-2024",
                health="red",
                suggested_action_id="reroute_failed",
            )
        ]
        result = run_health_fix(
            MagicMock(),
            dry_run=False,
            auto_yes=True,
            force=False,
            interactive=False,
        )
        assert any(item.executed for item in result.results)
        mock_execute.assert_called()

    @patch("elastro.health.remediation.catalog.RemediationCatalog.execute")
    @patch(
        "elastro.health.remediation.planner.resolve_replica_target",
        return_value=0,
    )
    @patch("elastro.health.remediation.fix.diagnose_unhealthy_indices")
    def test_destructive_with_yes_without_force_blocked(
        self, mock_diagnose, mock_resolve, mock_execute
    ):
        mock_diagnose.return_value = [
            IndexDiagnosis(
                index_name="logs-2024",
                health="yellow",
                suggested_action_id="reduce_replicas",
            )
        ]
        result = run_health_fix(
            MagicMock(),
            dry_run=False,
            auto_yes=True,
            force=False,
            interactive=False,
        )
        assert not any(item.executed for item in result.results)
        assert result.blocked
        mock_execute.assert_not_called()
        mock_resolve.assert_called()
