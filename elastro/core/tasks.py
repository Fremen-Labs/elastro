"""Cluster task list and cancel operations."""

from typing import Any, Dict, Optional

from elasticsearch import NotFoundError

from elastro.core.base import BaseManager
from elastro.core.errors import OperationError, ValidationError
from elastro.core.logger import get_logger

logger = get_logger(__name__)


def _node_failure_summary(failures: Any) -> str:
    """Compact node/status/reason text from a tasks.cancel node_failures list."""
    items = failures if isinstance(failures, list) else [failures]
    parts: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            parts.append(str(item))
            continue
        node = item.get("node_id") or item.get("node") or item.get("node_name")
        status = item.get("status")
        reason = item.get("reason")
        caused = item.get("caused_by")
        if not reason and isinstance(caused, dict):
            reason = caused.get("reason")
        bits = []
        if node:
            bits.append(f"node={node}")
        if status is not None:
            bits.append(f"status={status}")
        if reason:
            bits.append(f"reason={reason}")
        parts.append(" ".join(bits) if bits else str(item))
    return "; ".join(parts)


def _failure_is_not_found(item: Any) -> bool:
    if not isinstance(item, dict):
        text = str(item).lower()
        return "not found" in text or "not_found" in text
    status = item.get("status")
    type_name = str(item.get("type") or "")
    reason = str(item.get("reason") or "")
    caused = item.get("caused_by")
    if isinstance(caused, dict):
        type_name = type_name or str(caused.get("type") or "")
        reason = reason or str(caused.get("reason") or "")
    combined = f"{type_name} {reason}".lower()
    return status == 404 or "not_found" in combined or "not found" in combined


def _node_failures_are_not_found(failures: Any) -> bool:
    items = failures if isinstance(failures, list) else [failures]
    return bool(items) and all(_failure_is_not_found(item) for item in items)


def _task_present(response: Dict[str, Any], task_id: str) -> bool:
    nodes = response.get("nodes") or {}
    if not isinstance(nodes, dict):
        return False
    for node_id, node_data in nodes.items():
        if not isinstance(node_data, dict):
            continue
        tasks = node_data.get("tasks") or {}
        if not isinstance(tasks, dict):
            continue
        if task_id in tasks:
            return True
        for tid, task in tasks.items():
            if str(tid) == task_id:
                return True
            if isinstance(task, dict) and f"{node_id}:{task.get('id')}" == task_id:
                return True
    return False


class TaskManager(BaseManager):
    """List and cancel long-running cluster tasks."""

    def list_tasks(
        self, *, action: Optional[str] = None, detailed: bool = False
    ) -> Dict[str, Any]:
        """Return the cluster task list payload."""
        logger.debug("tasks.list action=%s detailed=%s", action or "*", detailed)
        try:
            self._ensure_connected()
            response = self._client.get_client().tasks.list(
                detailed=detailed, actions=action
            )
            return self._handle_response(response)
        except Exception as exc:
            logger.error("tasks list failed: %s", exc, exc_info=True)
            raise OperationError(f"Failed to list tasks: {exc}") from exc

    def cancel(self, task_id: str) -> Dict[str, Any]:
        """Request cancellation of ``task_id``.

        Cancellation is not idempotent. A missing task is ``OperationError``,
        not success.
        """
        if not task_id:
            raise ValidationError("Task ID is required")

        logger.info("tasks.cancel task_id=%s", task_id)
        try:
            self._ensure_connected()
            response = self._client.get_client().tasks.cancel(task_id=task_id)
            body = self._handle_response(response)
        except NotFoundError as exc:
            logger.error("task not found task_id=%s: %s", task_id, exc, exc_info=True)
            raise OperationError(f"Task not found: {task_id}") from exc
        except Exception as exc:
            logger.error(
                "task cancel failed task_id=%s: %s", task_id, exc, exc_info=True
            )
            raise OperationError(f"Failed to cancel task {task_id}: {exc}") from exc

        failures = body.get("node_failures")
        if failures and _node_failures_are_not_found(failures):
            logger.error("task not found task_id=%s", task_id)
            raise OperationError(f"Task not found: {task_id}")
        if failures:
            summary = _node_failure_summary(failures)
            logger.error("task cancel node_failures task_id=%s %s", task_id, summary)
            raise OperationError(
                f"Task cancellation encountered node failures for {task_id}: {summary}"
            )
        if not _task_present(body, task_id):
            logger.error("task not found task_id=%s", task_id)
            raise OperationError(f"Task not found: {task_id}")
        return body
