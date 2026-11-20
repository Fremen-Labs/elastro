"""Unit tests for FleetClient."""

from unittest.mock import MagicMock, patch
from urllib.parse import unquote

import pytest

from elastro.core.errors import OperationError, ValidationError
from elastro.coverage.fleet import FleetClient


def _response(status: int, payload: bytes) -> MagicMock:
    resp = MagicMock()
    resp.status = status
    resp.data = payload
    return resp


def test_list_agents_happy_path() -> None:
    http = MagicMock()
    http.request.side_effect = [
        _response(200, b'{"items":[{"id":"p1","name":"apm-apps"}]}'),
        _response(
            200,
            b'{"total":1,"items":[{"id":"agent-1","status":"online","policy_id":"p1",'
            b'"last_checkin":"2026-11-20T00:00:00Z","local_metadata":'
            b'{"host":{"hostname":"web-1"}},"upgrade_details":{"state":"UPG_IDLE"}}]}',
        ),
    ]
    with patch("elastro.coverage.fleet.urllib3.PoolManager", return_value=http):
        agents = FleetClient("https://kibana:5601", "secret-key").list_agents(
            policy_id="apm-apps"
        )
    assert len(agents) == 1
    assert agents[0].id == "agent-1"
    assert agents[0].name == "web-1"
    assert agents[0].status == "online"
    assert http.request.call_count == 2
    agents_url = http.request.call_args_list[1][0][1]
    decoded = unquote(agents_url)
    assert "/api/fleet/agents" in agents_url
    assert "kuery=" in agents_url
    assert 'policy_id:"p1"' in decoded
    assert "policyId=" not in agents_url
    assert "secret-key" not in agents_url
    headers = http.request.call_args_list[1][1]["headers"]
    assert headers["Authorization"].startswith("ApiKey ")


def test_list_agents_pages_until_total() -> None:
    http = MagicMock()
    page1_items = ",".join(f'{{"id":"a{i}","status":"online"}}' for i in range(100))
    http.request.side_effect = [
        _response(200, f'{{"total":101,"items":[{page1_items}]}}'.encode()),
        _response(200, b'{"total":101,"items":[{"id":"a100","status":"offline"}]}'),
    ]
    with patch("elastro.coverage.fleet.urllib3.PoolManager", return_value=http):
        agents = FleetClient("https://kibana:5601", "k").list_agents()
    assert len(agents) == 101
    assert http.request.call_count == 2
    assert "page=2" in http.request.call_args_list[1][0][1]


def test_status_reads_results_wrapper() -> None:
    http = MagicMock()
    http.request.return_value = _response(
        200,
        b'{"results":{"online":5,"offline":1,"error":0,"updating":0,'
        b'"inactive":0,"unenrolled":0}}',
    )
    with patch("elastro.coverage.fleet.urllib3.PoolManager", return_value=http):
        status = FleetClient("https://kibana:5601", "k").status()
    assert status.online == 5
    assert status.offline == 1
    assert status.total == 6
    assert "/api/fleet/agent_status" in http.request.call_args[0][1]


def test_status_http_error() -> None:
    http = MagicMock()
    http.request.return_value = _response(500, b'{"message":"boom"}')
    with patch("elastro.coverage.fleet.urllib3.PoolManager", return_value=http):
        with pytest.raises(OperationError, match="HTTP 500") as exc_info:
            FleetClient("https://kibana:5601", "secret-key").status()
    assert "secret-key" not in str(exc_info.value)


def test_missing_url_raises_validation_error() -> None:
    with pytest.raises(ValidationError, match="kibana_url"):
        FleetClient("", "key")


def test_from_config_requires_enabled() -> None:
    with patch(
        "elastro.coverage.fleet.get_config",
        return_value={
            "coverage": {
                "fleet": {
                    "enabled": False,
                    "kibana_url": "https://kibana:5601",
                    "api_key": "k",
                }
            }
        },
    ):
        with pytest.raises(ValidationError, match="Fleet is disabled"):
            FleetClient.from_config()


def test_status_falls_back_on_404() -> None:
    http = MagicMock()
    http.request.side_effect = [
        _response(404, b'{"message":"not found"}'),
        _response(
            200,
            b'{"items":[{"id":"a","status":"online"},{"id":"b","status":"offline"}]}',
        ),
    ]
    with patch("elastro.coverage.fleet.urllib3.PoolManager", return_value=http):
        status = FleetClient("https://kibana:5601", "k").status()
    assert status.total == 2
    assert status.online == 1
    assert status.offline == 1
    assert "/api/fleet/agent_status" in http.request.call_args_list[0][0][1]
