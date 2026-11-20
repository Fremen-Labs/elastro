"""Unit tests for FleetClient."""

from unittest.mock import MagicMock, patch

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
    http.request.return_value = _response(
        200,
        b'{"items":[{"id":"agent-1","status":"online","policy_id":"p1",'
        b'"last_checkin":"2026-11-20T00:00:00Z","local_metadata":'
        b'{"host":{"hostname":"web-1"}},"upgrade_details":{"state":"UPG_IDLE"}}]}',
    )
    with patch("elastro.coverage.fleet.urllib3.PoolManager", return_value=http):
        agents = FleetClient("https://kibana:5601", "secret-key").list_agents(
            policy_id="p1"
        )
    assert len(agents) == 1
    assert agents[0].id == "agent-1"
    assert agents[0].name == "web-1"
    assert agents[0].status == "online"
    http.request.assert_called_once()
    args, kwargs = http.request.call_args
    assert args[0] == "GET"
    assert "/api/fleet/agents" in args[1]
    assert "policyId=p1" in args[1]
    assert "secret-key" not in str(args)
    logged_headers = kwargs["headers"]
    assert logged_headers["Authorization"].startswith("ApiKey ")


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
