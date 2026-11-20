"""GUI session cookie / claim-code auth tests (no live ES)."""

from fastapi.responses import Response
from fastapi.testclient import TestClient

from elastro.server import (
    GUI_TOKEN_COOKIE,
    ElastroGUI,
    gui_claim_url,
    set_gui_session_cookie,
)


def test_gui_claim_url_does_not_embed_session_token():
    url = gui_claim_url(8080, "one-time-code")
    assert "token=" not in url
    assert url.startswith("http://127.0.0.1:8080/auth/claim")
    assert "one-time-code" in url


def test_run_server_command_line_does_not_include_secret():
    """The child argv must not contain the session token (env is used instead)."""
    import inspect

    from elastro.server import launch_gui_process

    source = inspect.getsource(launch_gui_process)
    assert "run_server({port})" in source
    assert "GUI_TOKEN_ENV" in source
    assert "run_server({port}, '{gui.token}')" not in source


def test_verify_token_accepts_cookie():
    gui = ElastroGUI()
    client = TestClient(gui.app)
    denied = client.get("/api/clusters")
    assert denied.status_code == 401

    via_header = client.get(
        "/api/clusters", headers={"Authorization": f"Bearer {gui.token}"}
    )
    # 200 or 500 depending on cluster config; must not be 401
    assert via_header.status_code != 401

    via_cookie = client.get("/api/clusters", cookies={GUI_TOKEN_COOKIE: gui.token})
    assert via_cookie.status_code != 401


def test_claim_sets_cookie_and_is_single_use():
    gui = ElastroGUI()
    client = TestClient(gui.app, follow_redirects=False)
    code = gui.claim_code
    first = client.get(f"/auth/claim?code={code}")
    assert first.status_code == 302
    assert GUI_TOKEN_COOKIE in first.cookies
    assert first.cookies[GUI_TOKEN_COOKIE] == gui.token
    set_cookie = first.headers.get("set-cookie") or ""
    lower = set_cookie.lower()
    assert "httponly" in lower
    assert "samesite=strict" in lower
    assert "path=/" in lower
    assert "max-age=86400" in lower
    assert "domain=" not in lower

    replay = client.get(f"/auth/claim?code={code}")
    assert replay.status_code == 401


def test_set_gui_session_cookie_is_httponly():
    response = Response()
    set_gui_session_cookie(response, "secret-token")
    header = response.headers.get("set-cookie") or ""
    lower = header.lower()
    assert GUI_TOKEN_COOKIE in header
    assert "httponly" in lower
    assert "samesite=strict" in lower
    assert "path=/" in lower
    assert "max-age=86400" in lower
    assert "domain=" not in lower


def test_served_html_does_not_contain_token_shim():
    gui = ElastroGUI()
    client = TestClient(gui.app)
    response = client.get("/")
    assert response.status_code == 200
    assert "URLSearchParams.prototype.get" not in response.text
