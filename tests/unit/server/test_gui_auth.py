"""GUI session cookie / claim-code auth tests (no live ES)."""

from fastapi.testclient import TestClient

from elastro.server import (
    GUI_TOKEN_COOKIE,
    ElastroGUI,
    gui_claim_url,
    inject_gui_token_shim,
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

    replay = client.get(f"/auth/claim?code={code}")
    assert replay.status_code == 401


def test_token_shim_injected():
    html = "<html><head></head><body></body></html>"
    out = inject_gui_token_shim(html)
    assert "elastro_gui_token" in out
    assert "URLSearchParams.prototype.get" in out
