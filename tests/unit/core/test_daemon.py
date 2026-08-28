"""Unit tests for the Fast-Path daemon bind defaults, auth, and status probe."""

import threading
from unittest.mock import patch

import pytest

from elastro.core.daemon import (
    DAEMON_DEFAULT_HOST,
    DAEMON_DEFAULT_PORT,
    DaemonBindError,
    create_daemon_server,
    is_loopback_bind,
    probe_daemon,
    start_daemon,
    validate_daemon_bind,
)


class DummyRPCService:
    def health_check(self) -> bool:
        return True

    def fast_path_search(self, args):
        return "ok:" + ",".join(args)


def test_default_bind_is_loopback():
    assert DAEMON_DEFAULT_HOST == "127.0.0.1"
    assert DAEMON_DEFAULT_PORT == 9201
    assert is_loopback_bind(DAEMON_DEFAULT_HOST) is True


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.1.10", "example.com"])
def test_non_loopback_bind_refused(host):
    with pytest.raises(DaemonBindError):
        validate_daemon_bind(host)


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1", "127.0.0.2"])
def test_loopback_bind_allowed(host):
    validate_daemon_bind(host)


def test_start_daemon_refuses_wildcard_without_serving():
    with pytest.raises(DaemonBindError):
        start_daemon(host="0.0.0.0", port=9201, service=DummyRPCService(), token="t")


def test_status_probe_talks_xmlrpc_not_http_health(tmp_path):
    token = "unit-test-daemon-token"
    server = create_daemon_server(
        host="127.0.0.1",
        port=0,
        service=DummyRPCService(),
        token=token,
    )
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with patch("elastro.core.daemon.load_daemon_token", return_value=token):
            online, detail = probe_daemon(host="127.0.0.1", port=port, timeout=2.0)
        assert online is True
        assert detail == "online"
    finally:
        server.shutdown()
        server.server_close()


def test_status_probe_rejects_missing_token():
    token = "unit-test-daemon-token"
    server = create_daemon_server(
        host="127.0.0.1",
        port=0,
        service=DummyRPCService(),
        token=token,
    )
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with patch("elastro.core.daemon.load_daemon_token", return_value=None):
            online, detail = probe_daemon(host="127.0.0.1", port=port, timeout=1.0)
        assert online is False
        assert "token" in detail
    finally:
        server.shutdown()
        server.server_close()
