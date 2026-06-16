"""Unit tests for GUI server process reuse logic."""

import json
from unittest.mock import patch

from elastro import __version__
from elastro.server import _should_reuse_gui_server


def test_should_not_reuse_when_version_mismatch():
    state = {
        "pid": 99999,
        "port": 8080,
        "token": "abc",
        "version": "0.0.1",
    }
    with patch("elastro.server.os.kill") as mock_kill:
        mock_kill.return_value = None
        assert _should_reuse_gui_server(state) is False


def test_should_not_reuse_when_health_api_missing():
    state = {
        "pid": 99999,
        "port": 8080,
        "token": "abc",
        "version": __version__,
    }
    with patch("elastro.server.os.kill") as mock_kill, patch(
        "elastro.server._server_supports_health_api",
        return_value=False,
    ):
        mock_kill.return_value = None
        assert _should_reuse_gui_server(state) is False


def test_should_reuse_compatible_server():
    state = {
        "pid": 99999,
        "port": 8080,
        "token": "abc",
        "version": __version__,
    }
    with patch("elastro.server.os.kill") as mock_kill, patch(
        "elastro.server._server_supports_health_api",
        return_value=True,
    ):
        mock_kill.return_value = None
        assert _should_reuse_gui_server(state) is True