"""Unit tests for ScriptManager."""

from unittest.mock import MagicMock

import pytest

from elastro.core.base import BaseManager
from elastro.core.errors import OperationError, ValidationError
from elastro.core.script import ScriptManager


def _manager() -> tuple[ScriptManager, MagicMock]:
    client = MagicMock()
    client.is_connected.return_value = True
    es = MagicMock()
    client.get_client.return_value = es
    return ScriptManager(client), es


def test_script_manager_is_base_manager() -> None:
    manager, _ = _manager()
    assert isinstance(manager, BaseManager)


def test_list_scripts_returns_stored_scripts() -> None:
    manager, es = _manager()
    es.cluster.state.return_value = {
        "metadata": {"stored_scripts": {"s1": {"lang": "painless"}}}
    }

    assert manager.list_scripts() == {"s1": {"lang": "painless"}}
    es.cluster.state.assert_called_once_with(
        metric="metadata", filter_path="metadata.stored_scripts"
    )


def test_list_scripts_empty() -> None:
    manager, es = _manager()
    es.cluster.state.return_value = {}

    assert manager.list_scripts() == {}


def test_list_scripts_failure_raises_operation_error() -> None:
    manager, es = _manager()
    es.cluster.state.side_effect = Exception("No node reached")

    with pytest.raises(OperationError, match="No node reached"):
        manager.list_scripts()


def test_get_script_success() -> None:
    manager, es = _manager()
    es.get_script.return_value = {"_id": "s1", "found": True}

    assert manager.get_script("s1") == {"_id": "s1", "found": True}
    es.get_script.assert_called_once_with(id="s1")


def test_get_script_empty_id_raises_validation_error() -> None:
    manager, _ = _manager()

    with pytest.raises(ValidationError, match="Script id is required"):
        manager.get_script("")


def test_get_script_failure_raises_operation_error() -> None:
    manager, es = _manager()
    es.get_script.side_effect = Exception("No node reached")

    with pytest.raises(OperationError, match="No node reached"):
        manager.get_script("s1")


def test_put_script_success() -> None:
    manager, es = _manager()
    es.put_script.return_value = {"acknowledged": True}

    result = manager.put_script("s1", "return 1;")

    assert result == {"acknowledged": True}
    es.put_script.assert_called_once_with(
        id="s1",
        body={"script": {"lang": "painless", "source": "return 1;"}},
    )


def test_delete_script_success() -> None:
    manager, es = _manager()
    es.delete_script.return_value = {"acknowledged": True}

    assert manager.delete_script("s1") == {"acknowledged": True}
    es.delete_script.assert_called_once_with(id="s1")


def test_delete_script_failure_raises_operation_error() -> None:
    manager, es = _manager()
    es.delete_script.side_effect = Exception("No node reached")

    with pytest.raises(OperationError, match="No node reached"):
        manager.delete_script("s1")


def test_execute_uses_perform_request() -> None:
    manager, es = _manager()
    es.perform_request.return_value = {"result": 1}
    payload = {"script": {"source": "return 1;"}}

    assert manager.execute(payload) == {"result": 1}
    es.perform_request.assert_called_once_with(
        "POST",
        "/_scripts/painless/_execute",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        body=payload,
    )


def test_execute_failure_raises_operation_error() -> None:
    manager, es = _manager()
    es.perform_request.side_effect = Exception("No node reached")

    with pytest.raises(OperationError, match="No node reached"):
        manager.execute({"script": {"source": "return 1;"}})
