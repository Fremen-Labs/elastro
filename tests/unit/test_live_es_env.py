"""Unit tests for live Elasticsearch env helpers used by integration tests."""

from tests.conftest import live_client_kwargs, live_es_auth, live_es_hosts


def test_live_es_hosts_default(monkeypatch) -> None:
    monkeypatch.delenv("ELASTIC_URL", raising=False)
    monkeypatch.delenv("ELASTIC_HOSTS", raising=False)
    assert live_es_hosts() == ["http://localhost:9200"]


def test_live_es_hosts_from_elastic_url(monkeypatch) -> None:
    monkeypatch.setenv("ELASTIC_URL", "http://127.0.0.1:9205")
    assert live_es_hosts() == ["http://127.0.0.1:9205"]


def test_live_es_hosts_prefers_url_over_hosts(monkeypatch) -> None:
    monkeypatch.setenv("ELASTIC_URL", "http://127.0.0.1:9205")
    monkeypatch.setenv("ELASTIC_HOSTS", "http://ignored:9200")
    assert live_es_hosts() == ["http://127.0.0.1:9205"]


def test_live_es_auth_from_env(monkeypatch) -> None:
    monkeypatch.delenv("ELASTIC_URL", raising=False)
    monkeypatch.delenv("ELASTIC_HOSTS", raising=False)
    monkeypatch.setenv("ELASTIC_USERNAME", "elastic")
    monkeypatch.setenv("ELASTIC_PASSWORD", "from-env")
    assert live_es_auth() == ("elastic", "from-env")
    kwargs = live_client_kwargs()
    assert kwargs["hosts"] == ["http://localhost:9200"]
    assert kwargs["username"] == "elastic"
    assert kwargs["password"] == "from-env"
    assert kwargs["verify_certs"] is False
