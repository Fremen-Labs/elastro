"""Unit tests for AgentStore."""

import pytest

from elastro.agent.models import AGENT_SEMANTIC_MEMORY, MemoryNote
from elastro.agent.store import AgentStore
from elastro.core.errors import OperationError, ValidationError


def test_index_search_and_delete_by_query(es_client) -> None:
    store = AgentStore(es_client)
    es_client.client.index.return_value = {"_id": "abc", "result": "created"}
    note = MemoryNote(
        timestamp="2026-11-19T12:00:00Z",
        note_type="strategic",
        subject="s",
        content="c",
    )

    indexed = store.index(AGENT_SEMANTIC_MEMORY, note)
    assert indexed["_id"] == "abc"
    es_client.client.index.assert_called_once_with(
        index=AGENT_SEMANTIC_MEMORY,
        document=note.model_dump(mode="json", exclude_none=True),
    )

    es_client.client.search.return_value = {"hits": {"hits": []}}
    searched = store.search(AGENT_SEMANTIC_MEMORY, {"query": {"match_all": {}}})
    assert searched["hits"]["hits"] == []
    es_client.client.search.assert_called_once_with(
        index=AGENT_SEMANTIC_MEMORY, body={"query": {"match_all": {}}}
    )

    es_client.client.delete_by_query.return_value = {"deleted": 2}
    deleted = store.delete_by_query(
        AGENT_SEMANTIC_MEMORY, {"query": {"term": {"note_type": "tactical"}}}
    )
    assert deleted["deleted"] == 2
    es_client.client.delete_by_query.assert_called_once()


def test_index_with_id(es_client) -> None:
    store = AgentStore(es_client)
    es_client.client.index.return_value = {"_id": "my-tool"}
    store.index("flow_tools", {"tool_name": "my-tool"}, id="my-tool")
    es_client.client.index.assert_called_once_with(
        index="flow_tools", document={"tool_name": "my-tool"}, id="my-tool"
    )


def test_index_empty_name_raises(es_client) -> None:
    with pytest.raises(ValidationError, match="Index name cannot be empty"):
        AgentStore(es_client).index("", {"a": 1})


def test_index_operation_error(es_client) -> None:
    es_client.client.index.side_effect = Exception("No node reached")
    with pytest.raises(OperationError, match="No node reached"):
        AgentStore(es_client).index(AGENT_SEMANTIC_MEMORY, {"a": 1})


def test_search_operation_error(es_client) -> None:
    es_client.client.search.side_effect = Exception("No node reached")
    with pytest.raises(OperationError, match="No node reached"):
        AgentStore(es_client).search(
            AGENT_SEMANTIC_MEMORY, {"query": {"match_all": {}}}
        )


def test_delete_by_query_operation_error(es_client) -> None:
    es_client.client.delete_by_query.side_effect = Exception("No node reached")
    with pytest.raises(OperationError, match="No node reached"):
        AgentStore(es_client).delete_by_query(
            AGENT_SEMANTIC_MEMORY, {"query": {"match_all": {}}}
        )
