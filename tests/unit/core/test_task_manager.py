"""Unit tests for TaskManager."""

import pytest
from elastic_transport import ApiResponseMeta
from elasticsearch import NotFoundError

from elastro.core.errors import OperationError, ValidationError
from elastro.core.tasks import TaskManager


def _not_found_error() -> NotFoundError:
    meta = ApiResponseMeta(
        status=404, http_version="1.1", headers={}, duration=0.0, node=None
    )
    return NotFoundError(
        "not found",
        meta,
        {"error": {"type": "resource_not_found_exception", "reason": "task not found"}},
    )


def _cancel_ok(task_id: str = "node-1:42") -> dict:
    node_id, _, numeric_id = task_id.partition(":")
    return {
        "nodes": {
            node_id: {
                "tasks": {
                    task_id: {
                        "id": int(numeric_id) if numeric_id.isdigit() else numeric_id,
                        "cancelled": True,
                    }
                }
            }
        }
    }


class TestTaskManager:
    def test_list_tasks_success(self, es_client) -> None:
        payload = {"nodes": {"node-1": {"tasks": {}}}}
        es_client.client.tasks.list.return_value = payload

        result = TaskManager(es_client).list_tasks(action="*reindex*", detailed=True)

        assert result == payload
        es_client.client.tasks.list.assert_called_once_with(
            detailed=True, actions="*reindex*"
        )

    def test_list_tasks_failure_raises_operation_error(self, es_client) -> None:
        es_client.client.tasks.list.side_effect = Exception("No node reached")

        with pytest.raises(OperationError, match="Failed to list tasks"):
            TaskManager(es_client).list_tasks()

    def test_cancel_success(self, es_client) -> None:
        payload = _cancel_ok()
        es_client.client.tasks.cancel.return_value = payload

        result = TaskManager(es_client).cancel("node-1:42")

        assert result == payload
        es_client.client.tasks.cancel.assert_called_once_with(task_id="node-1:42")

    def test_cancel_empty_task_id_raises_validation_error(self, es_client) -> None:
        with pytest.raises(ValidationError, match="Task ID is required"):
            TaskManager(es_client).cancel("")
        es_client.client.tasks.cancel.assert_not_called()

    def test_cancel_not_found_http_raises_operation_error(self, es_client) -> None:
        es_client.client.tasks.cancel.side_effect = _not_found_error()

        with pytest.raises(OperationError, match="Task not found: node-1:42"):
            TaskManager(es_client).cancel("node-1:42")

    def test_cancel_empty_nodes_is_not_found(self, es_client) -> None:
        es_client.client.tasks.cancel.return_value = {"nodes": {}}

        with pytest.raises(OperationError, match="Task not found: node-1:42"):
            TaskManager(es_client).cancel("node-1:42")

    def test_cancel_not_found_node_failures(self, es_client) -> None:
        es_client.client.tasks.cancel.return_value = {
            "node_failures": [
                {
                    "node_id": "node-1",
                    "status": 404,
                    "reason": "task [node-1:42] not found",
                }
            ]
        }

        with pytest.raises(OperationError, match="Task not found: node-1:42"):
            TaskManager(es_client).cancel("node-1:42")

    def test_cancel_node_failures_raises_operation_error(self, es_client) -> None:
        es_client.client.tasks.cancel.return_value = {
            "node_failures": [
                {
                    "node_id": "node-a",
                    "status": 500,
                    "reason": "task cancelled",
                }
            ]
        }

        with pytest.raises(OperationError, match="node-a") as excinfo:
            TaskManager(es_client).cancel("node-1:42")

        assert "500" in str(excinfo.value)
        assert "task cancelled" in str(excinfo.value)

    def test_cancel_transport_error_raises_operation_error(self, es_client) -> None:
        es_client.client.tasks.cancel.side_effect = Exception("No node reached")

        with pytest.raises(OperationError, match="Failed to cancel task"):
            TaskManager(es_client).cancel("node-1:42")
