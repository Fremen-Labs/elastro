"""CLI tests for memory prune and telemetry ingest."""

import json
from unittest.mock import MagicMock

from click.testing import CliRunner

from elastro.agent.models import AGENT_TELEMETRY_DEEP, TelemetryDocument
from elastro.cli.commands.memory import memory_group
from elastro.cli.commands.telemetry import telemetry_group


def _client() -> MagicMock:
    client = MagicMock()
    client.is_connected.return_value = True
    client.get_client.return_value = client.client
    return client


def test_prune_dry_run_does_not_call_delete_by_query() -> None:
    client = _client()
    result = CliRunner().invoke(memory_group, ["prune", "--dry-run"], obj=client)

    assert result.exit_code == 0, result.stderr
    client.client.delete_by_query.assert_not_called()
    client.get_client.assert_not_called()
    body = json.loads(result.stdout)
    assert body["query"]["bool"]["must"][0] == {"term": {"note_type": "tactical"}}
    assert "timestamp" in body["query"]["bool"]["must"][1]["range"]


def test_prune_without_yes_non_tty_exits_2_zero_client_calls() -> None:
    client = _client()
    result = CliRunner().invoke(memory_group, ["prune"], obj=client)

    assert result.exit_code == 2
    assert "--yes" in result.stderr
    assert result.stdout == ""
    client.get_client.assert_not_called()
    client.client.delete_by_query.assert_not_called()
    client.client.index.assert_not_called()
    client.client.search.assert_not_called()


def test_prune_interactive_decline_exits_0(monkeypatch) -> None:
    monkeypatch.setattr("elastro.cli.errors.stdin_is_tty", lambda: True)
    client = _client()
    result = CliRunner().invoke(memory_group, ["prune"], obj=client, input="n\n")

    assert result.exit_code == 0
    assert "Aborted" in result.stderr
    client.get_client.assert_not_called()
    client.client.delete_by_query.assert_not_called()


def test_prune_with_yes_calls_delete_by_query() -> None:
    client = _client()
    client.client.delete_by_query.return_value = {"deleted": 4}
    result = CliRunner().invoke(
        memory_group, ["prune", "--yes", "--days", "3"], obj=client
    )

    assert result.exit_code == 0, result.stderr
    client.client.delete_by_query.assert_called_once()
    kwargs = client.client.delete_by_query.call_args.kwargs
    assert kwargs["index"] == "agent_semantic_memory"
    assert kwargs["body"]["query"]["bool"]["must"][0] == {
        "term": {"note_type": "tactical"}
    }


def test_prune_transport_error_exits_1() -> None:
    client = _client()
    client.client.delete_by_query.side_effect = Exception("No node reached")
    result = CliRunner().invoke(memory_group, ["prune", "--yes"], obj=client)

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "No node reached" in result.stderr


def test_telemetry_ingest_builds_pydantic_model_and_indexes_once() -> None:
    client = _client()
    client.client.index.return_value = {"_id": "tel-1"}
    result = CliRunner().invoke(
        telemetry_group,
        [
            "ingest",
            "session-1",
            "--elastro-q-ms",
            "15",
            "--in-tokens",
            "9",
            "--out-tokens",
            "3",
        ],
        obj=client,
    )

    assert result.exit_code == 0, result.stderr
    client.client.index.assert_called_once()
    kwargs = client.client.index.call_args.kwargs
    assert kwargs["index"] == AGENT_TELEMETRY_DEEP
    document = kwargs["document"]
    parsed = TelemetryDocument.model_validate(document)
    assert parsed.workload_reference == "session-1"
    assert parsed.t_elastro_query_ms == 15
    assert parsed.token_count_query.input_tokens == 9
    assert parsed.token_count_query.output_tokens == 3


def test_telemetry_ingest_transport_error_exits_1() -> None:
    client = _client()
    client.client.index.side_effect = Exception("No node reached")
    result = CliRunner().invoke(telemetry_group, ["ingest", "session-1"], obj=client)

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "No node reached" in result.stderr
