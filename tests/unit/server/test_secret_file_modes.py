"""Secret local files are written 0o600; looser modes are chmod'd on read."""

import json
import os
from unittest.mock import MagicMock, patch

from elastro import __version__
from elastro.config.loader import _load_from_file, save_config
from elastro.server import ElastroGUI, launch_gui_process


def _mode(path):
    return path.stat().st_mode & 0o777


class TestSecretFileModes:
    def test_gui_config_created_0600(self, tmp_path):
        gui = ElastroGUI()
        gui.config_dir = tmp_path
        gui.config_file = tmp_path / "gui_config.json"
        gui._ensure_config()
        assert gui.config_file.exists()
        assert _mode(gui.config_file) == 0o600

    def test_write_config_0600(self, tmp_path):
        gui = ElastroGUI()
        gui.config_dir = tmp_path
        gui.config_file = tmp_path / "gui_config.json"
        gui._write_config({"clusters": []})
        assert _mode(gui.config_file) == 0o600

    def test_save_config_0600(self, tmp_path):
        path = tmp_path / "config.yaml"
        save_config(
            {"elasticsearch": {"hosts": ["http://localhost:9200"]}}, path=str(path)
        )
        assert path.exists()
        assert _mode(path) == 0o600

    def test_gui_state_written_0600(self, tmp_path):
        mock_proc = MagicMock(pid=4242)
        with (
            patch("elastro.server.Path.home", return_value=tmp_path),
            patch("elastro.server._wait_for_server_ready", return_value=True),
            patch("subprocess.Popen", return_value=mock_proc),
        ):
            url = launch_gui_process()
        state_file = tmp_path / ".elastic" / ".gui_state.json"
        assert state_file.exists()
        assert _mode(state_file) == 0o600
        assert url.startswith("http://127.0.0.1:")

    def test_looser_gui_config_chmod_on_read(self, tmp_path):
        gui = ElastroGUI()
        gui.config_dir = tmp_path
        gui.config_file = tmp_path / "gui_config.json"
        gui.config_file.write_text('{"clusters": []}')
        os.chmod(gui.config_file, 0o644)
        assert _mode(gui.config_file) == 0o644
        payload = gui._read_config()
        assert payload == {"clusters": []}
        assert _mode(gui.config_file) == 0o600

    def test_looser_config_yaml_chmod_on_read(self, tmp_path):
        path = tmp_path / "config.yaml"
        save_config(
            {"elasticsearch": {"hosts": ["http://localhost:9200"]}}, path=str(path)
        )
        os.chmod(path, 0o644)
        assert _mode(path) == 0o644
        loaded = _load_from_file(str(path))
        assert loaded["elasticsearch"]["hosts"] == ["http://localhost:9200"]
        assert _mode(path) == 0o600

    def test_looser_gui_state_chmod_on_read(self, tmp_path):
        elastic = tmp_path / ".elastic"
        elastic.mkdir()
        state_file = elastic / ".gui_state.json"
        state_file.write_text(
            json.dumps(
                {
                    "pid": 4242,
                    "port": 8080,
                    "token": "tok",
                    "version": __version__,
                }
            )
        )
        os.chmod(state_file, 0o644)
        with (
            patch("elastro.server.Path.home", return_value=tmp_path),
            patch("elastro.server._should_reuse_gui_server", return_value=True),
            patch("elastro.server._refresh_gui_claim", return_value="claim"),
        ):
            url = launch_gui_process()
        assert _mode(state_file) == 0o600
        assert "claim" in url

    def test_chmod_failure_logged_and_startup_continues(self, tmp_path):
        gui = ElastroGUI()
        gui.config_dir = tmp_path
        gui.config_file = tmp_path / "gui_config.json"
        with (
            patch(
                "elastro.config.loader.os.chmod",
                side_effect=OSError("chmod not supported"),
            ),
            patch("elastro.config.loader.logger.warning") as mock_warn,
        ):
            payload = gui._read_config()
        assert payload["clusters"] == []
        assert gui.config_file.exists()
        mock_warn.assert_called()
        assert "Failed to restrict mode" in mock_warn.call_args.args[0]

    def test_chmod_failure_does_not_block_gui_launch(self, tmp_path):
        mock_proc = MagicMock(pid=99)
        with (
            patch("elastro.server.Path.home", return_value=tmp_path),
            patch("elastro.server._wait_for_server_ready", return_value=True),
            patch("subprocess.Popen", return_value=mock_proc),
            patch(
                "elastro.config.loader.os.chmod",
                side_effect=OSError("chmod not supported"),
            ),
            patch("elastro.config.loader.logger.warning") as mock_warn,
        ):
            url = launch_gui_process()
        assert url.startswith("http://127.0.0.1:")
        assert (tmp_path / ".elastic" / ".gui_state.json").exists()
        mock_warn.assert_called()
        assert "Failed to restrict mode" in mock_warn.call_args.args[0]

    def test_save_config_chmod_failure_still_writes(self, tmp_path):
        path = tmp_path / "config.yaml"
        with (
            patch(
                "elastro.config.loader.os.chmod",
                side_effect=OSError("chmod not supported"),
            ),
            patch("elastro.config.loader.logger.warning") as mock_warn,
        ):
            save_config(
                {"elasticsearch": {"hosts": ["http://localhost:9200"]}},
                path=str(path),
            )
        assert path.exists()
        mock_warn.assert_called()
