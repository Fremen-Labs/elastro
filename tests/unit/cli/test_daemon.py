"""CLI daemon command defaults and status wiring."""

from click.testing import CliRunner

from elastro.cli.commands.daemon import daemon_group, start, status


def test_start_host_option_defaults_to_loopback():
    host_opt = next(opt for opt in start.params if opt.name == "host")
    assert host_opt.default == "127.0.0.1"


def test_start_rejects_non_loopback():
    runner = CliRunner()
    result = runner.invoke(daemon_group, ["start", "--host", "0.0.0.0"])
    assert result.exit_code != 0
    assert "Refusing to bind" in result.output


def test_status_uses_probe_not_http_health(monkeypatch):
    calls = []

    def fake_probe(host="127.0.0.1", port=9201, timeout=1.0):
        calls.append((host, port))
        return True, "online"

    monkeypatch.setattr("elastro.core.daemon.probe_daemon", fake_probe)
    runner = CliRunner()
    result = runner.invoke(status, ["--port", "9333"])
    assert result.exit_code == 0
    assert "ONLINE" in result.output
    assert calls == [("127.0.0.1", 9333)]
    assert "/health" not in result.output
