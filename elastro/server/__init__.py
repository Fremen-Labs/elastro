"""
Elastro GUI server package.

This module is the thin orchestrator for the local GUI. It handles:
- Config file management (read/write/ensure)
- Bearer token authentication
- Router mounting from server/routes/
- Static file serving for the embedded Vue SPA
- Process lifecycle (launch/run)

All API route logic lives in elastro.server.routes.*.
"""

import json
import os
import secrets
import signal
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from elastro import __version__
from elastro.core.logger import get_logger

logger = get_logger(__name__)

GUI_CAPABILITIES: List[str] = ["clusters", "indices", "health", "cli", "config"]
GUI_TOKEN_COOKIE = "elastro_gui_token"
GUI_TOKEN_ENV = "ELASTRO_GUI_TOKEN"
GUI_CLAIM_ENV = "ELASTRO_GUI_CLAIM"

_TOKEN_SHIM = r"""<script>
(function(){
  function readCookie(name){
    var parts = document.cookie.split(';');
    for (var i = 0; i < parts.length; i++) {
      var p = parts[i].replace(/^\s+/, '');
      if (p.indexOf(name + '=') === 0) {
        return decodeURIComponent(p.slice(name.length + 1));
      }
    }
    return '';
  }
  var token = readCookie('elastro_gui_token');
  if (token) {
    var origGet = URLSearchParams.prototype.get;
    URLSearchParams.prototype.get = function(key){
      if (String(key) === 'token') {
        var v = origGet.call(this, key);
        return v || token;
      }
      return origGet.call(this, key);
    };
  }
})();
</script>
"""


def inject_gui_token_shim(html: str) -> str:
    """Inject a cookie-based token shim so the compiled SPA does not need ?token=."""
    if "URLSearchParams.prototype.get" in html and "elastro_gui_token" in html:
        return html
    if "</head>" in html:
        return html.replace("</head>", _TOKEN_SHIM + "</head>", 1)
    return _TOKEN_SHIM + html


def set_gui_session_cookie(response: Response, token: str) -> None:
    """Attach a host-only localhost session cookie (no Domain = host-only)."""
    response.set_cookie(
        key=GUI_TOKEN_COOKIE,
        value=token,
        httponly=False,
        samesite="strict",
        path="/",
        max_age=86400,
    )


def gui_claim_url(port: int, claim_code: str) -> str:
    """Return the one-time claim URL (session token itself is never in the URL)."""
    return f"http://127.0.0.1:{port}/auth/claim?code={claim_code}"


def _wait_for_server_ready(port: int, *, timeout: float = 8.0) -> bool:
    """Poll /api/meta until the detached GUI server accepts connections."""
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/meta",
                timeout=1,
            ):
                return True
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.2)
    return False


def _server_supports_health_api(port: int) -> bool:
    """Return True when the running GUI server exposes the health API."""
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/meta",
            timeout=2,
        ) as response:
            payload = json.loads(response.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return False
    capabilities = payload.get("capabilities") or []
    return "health" in capabilities


def _stop_gui_process(pid: int) -> None:
    """Terminate a detached GUI server process."""
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except OSError:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            return


def _should_reuse_gui_server(state: Dict[str, Any]) -> bool:
    """Reuse only when pid is alive, version matches, and health API is available."""
    pid = state.get("pid")
    port = state.get("port")
    token = state.get("token")
    if not pid or not port or not token:
        return False
    if state.get("version") != __version__:
        logger.info(
            "GUI server version mismatch (running=%s, installed=%s); restarting",
            state.get("version"),
            __version__,
        )
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    if not _server_supports_health_api(int(port)):
        logger.info("GUI server on port %s lacks health API; restarting", port)
        return False
    return True


class ElastroGUI:
    def __init__(self) -> None:
        self.config_dir = Path.home() / ".elastic"
        self.config_file = self.config_dir / "gui_config.json"
        self.app = FastAPI(title="Elastro Local GUI API")
        self.token = secrets.token_urlsafe(32)
        self.claim_code = secrets.token_urlsafe(24)

        # Setup static dir — points to the embedded Vue build
        self.static_dir = Path(__file__).parent.parent / "gui"

        self._setup_routes()

    @property
    def token(self) -> str:
        return str(getattr(self.app.state, "gui_token", ""))

    @token.setter
    def token(self, value: str) -> None:
        self.app.state.gui_token = value

    @property
    def claim_code(self) -> str:
        return str(getattr(self.app.state, "gui_claim", ""))

    @claim_code.setter
    def claim_code(self, value: str) -> None:
        self.app.state.gui_claim = value

    @staticmethod
    def _has_usable_auth(auth: Dict[str, Any]) -> bool:
        """Return True when the auth dict contains at least one usable credential."""
        if not auth or not isinstance(auth, dict):
            return False
        if auth.get("api_key"):
            return True
        if auth.get("username") and auth.get("password"):
            return True
        return False

    def _read_cli_auth(self) -> Dict[str, Any]:
        """Read auth credentials from the CLI config.yaml, if available."""
        cli_config_path = self.config_dir / "config.yaml"
        if not cli_config_path.exists():
            return {}
        try:
            import yaml

            with open(cli_config_path, "r") as f:
                cli_cfg = yaml.safe_load(f)
            if cli_cfg and "elasticsearch" in cli_cfg:
                es_cfg = cli_cfg["elasticsearch"]
                auth = es_cfg.get("auth", {})
                if isinstance(auth, dict) and self._has_usable_auth(auth):
                    # Return only credential keys (strip 'type' and nulls)
                    return {
                        k: v for k, v in auth.items() if v is not None and k != "type"
                    }
        except Exception:
            pass
        return {}

    def _ensure_config(self) -> None:
        if not self.config_dir.exists():
            self.config_dir.mkdir(parents=True, exist_ok=True)
        if not self.config_file.exists():
            initial_clusters = []
            # Try to auto-import from CLI config for a smooth UX
            cli_config_path = self.config_dir / "config.yaml"
            if cli_config_path.exists():
                try:
                    import yaml

                    with open(cli_config_path, "r") as f:
                        cli_cfg = yaml.safe_load(f)

                    if cli_cfg and "elasticsearch" in cli_cfg:
                        es_cfg = cli_cfg["elasticsearch"]
                        host = (
                            es_cfg.get("hosts", [""])[0] if es_cfg.get("hosts") else ""
                        )
                        auth = es_cfg.get("auth", {})

                        if host:
                            initial_clusters.append(
                                {"name": "default-cli", "host": host, "auth": auth}
                            )
                except Exception:
                    pass

            with open(self.config_file, "w") as f:
                json.dump({"clusters": initial_clusters}, f)
        else:
            # Back-fill: if gui_config.json exists but clusters have empty auth,
            # attempt to populate from CLI config.yaml so the GUI self-heals
            # when security is enabled or credentials change.
            self._backfill_auth_from_cli()

    def _backfill_auth_from_cli(self) -> None:
        """Populate empty GUI cluster auth blocks from CLI config.yaml."""
        try:
            with open(self.config_file, "r") as f:
                gui_cfg = json.load(f)
        except (json.JSONDecodeError, OSError):
            return

        clusters = gui_cfg.get("clusters", [])
        if not clusters:
            return

        cli_auth = self._read_cli_auth()
        if not cli_auth:
            return

        changed = False
        for cluster in clusters:
            existing_auth = cluster.get("auth", {})
            if not self._has_usable_auth(existing_auth):
                cluster["auth"] = cli_auth.copy()
                changed = True
                logger.info(
                    "Back-filled auth for GUI cluster '%s' from CLI config",
                    cluster.get("name", "unknown"),
                )

        if changed:
            with open(self.config_file, "w") as f:
                json.dump(gui_cfg, f, indent=4)

    def _read_config(self) -> Dict[str, Any]:
        self._ensure_config()
        try:
            with open(self.config_file, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {"clusters": []}

    def _write_config(self, config: Dict[str, Any]) -> None:
        self._ensure_config()
        with open(self.config_file, "w") as f:
            json.dump(config, f, indent=4)

    def verify_token(self, request: Request) -> str:
        """Authenticate via Bearer header or localhost session cookie.

        Implemented as an instance method so tests can still call it, but the
        expected secret is read from ``request.app.state`` so concurrent GUI
        instances (and FastAPI dependency caching) cannot mix tokens.
        """
        expected = str(getattr(request.app.state, "gui_token", ""))
        authorization = request.headers.get("authorization")
        cookie_token = request.cookies.get(GUI_TOKEN_COOKIE)
        token: Optional[str] = None
        if authorization and authorization.startswith("Bearer "):
            token = authorization.split(" ", 1)[1]
        elif cookie_token:
            token = cookie_token

        if not expected or not token or not secrets.compare_digest(token, expected):
            raise HTTPException(status_code=401, detail="Unauthorized")
        return token

    def _setup_routes(self) -> None:
        # Enable CORS — locked to localhost only (OWASP hardened)
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://127.0.0.1"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Mount modular routers — each route module binds to our shared
        # config accessor and token verifier via a factory function.
        from elastro.server.routes.cli import cli_routes
        from elastro.server.routes.clusters import cluster_routes
        from elastro.server.routes.config import config_routes
        from elastro.server.routes.health import health_routes
        from elastro.server.routes.indices import index_routes

        self.app.include_router(
            config_routes(self._read_config, self._write_config, self.verify_token)
        )
        self.app.include_router(cluster_routes(self._read_config, self.verify_token))
        self.app.include_router(index_routes(self._read_config, self.verify_token))
        self.app.include_router(cli_routes(self._read_config, self.verify_token))
        self.app.include_router(health_routes(self._read_config, self.verify_token))

        @self.app.get("/api/meta")
        def api_meta() -> Dict[str, Any]:
            """Lightweight capability probe for GUI process reuse decisions."""
            return {
                "version": __version__,
                "capabilities": GUI_CAPABILITIES,
            }

        @self.app.get("/auth/claim")
        def claim_session(code: str = "") -> RedirectResponse:
            """Exchange a one-time claim code for a localhost session cookie."""
            if not code or not secrets.compare_digest(code, self.claim_code):
                raise HTTPException(
                    status_code=401, detail="Invalid or expired claim code"
                )
            self.claim_code = secrets.token_urlsafe(24)
            redirect = RedirectResponse(url="/", status_code=302)
            set_gui_session_cookie(redirect, self.token)
            return redirect

        @self.app.post("/auth/refresh-claim")
        def refresh_claim(
            authorization: Optional[str] = Header(None),
        ) -> Dict[str, str]:
            """Mint a fresh one-time claim code for CLI reuse of a running GUI."""
            if not authorization or not authorization.startswith("Bearer "):
                raise HTTPException(status_code=401, detail="Unauthorized")
            provided = authorization.split(" ", 1)[1]
            if not secrets.compare_digest(provided, self.token):
                raise HTTPException(status_code=401, detail="Unauthorized")
            self.claim_code = secrets.token_urlsafe(24)
            return {"code": self.claim_code}

        # Mount static GUI files
        if self.static_dir.exists():
            self.app.mount(
                "/assets",
                StaticFiles(directory=self.static_dir / "assets"),
                name="assets",
            )

            @self.app.get("/{full_path:path}")
            def serve_gui(full_path: str) -> HTMLResponse:
                # Never serve SPA HTML for API paths — avoids silent axios parse failures
                if full_path.startswith("api/"):
                    raise HTTPException(status_code=404, detail="API route not found")
                index_path = self.static_dir / "index.html"
                if index_path.exists():
                    with open(index_path, "r") as f:
                        html = inject_gui_token_shim(f.read())
                    return HTMLResponse(content=html)
                return HTMLResponse(
                    "GUI not built. Run npm run build in packages/gui.",
                    status_code=404,
                )


def run_server(port: int = 8080, token: str = "") -> None:
    gui = ElastroGUI()
    env_token = os.environ.get(GUI_TOKEN_ENV, "")
    chosen_token = token or env_token
    if chosen_token:
        gui.token = chosen_token
    env_claim = os.environ.get(GUI_CLAIM_ENV, "")
    if env_claim:
        gui.claim_code = env_claim

    # We use log_level warning to keep the detached CLI clean
    uvicorn.run(gui.app, host="127.0.0.1", port=port, log_level="warning")


def launch_gui_process() -> str:
    """Launches the server in a separate process and returns the access URL."""
    import socket

    gui = ElastroGUI()
    state_file = gui.config_dir / ".gui_state.json"

    # Reuse only a compatible, healthy GUI server process
    if state_file.exists():
        try:
            with open(state_file, "r") as f:
                state = json.load(f)

            if _should_reuse_gui_server(state):
                refreshed = _refresh_gui_claim(int(state["port"]), str(state["token"]))
                if refreshed:
                    return gui_claim_url(int(state["port"]), refreshed)
                return f"http://127.0.0.1:{state['port']}"

            pid = state.get("pid")
            if pid:
                _stop_gui_process(int(pid))
            state_file.unlink(missing_ok=True)
        except Exception:
            state_file.unlink(missing_ok=True)

    # Find an open port
    port = 8080
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", port))
    except OSError:
        # Port is in use (by something else), get a random free port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]

    # We use a detached subprocess instead of multiprocessing to survive CLI exit
    import subprocess
    import sys

    claim_code = secrets.token_urlsafe(24)
    gui.claim_code = claim_code
    cmd = [
        sys.executable,
        "-c",
        f"from elastro.server import run_server; run_server({port})",
    ]

    child_env = os.environ.copy()
    child_env[GUI_TOKEN_ENV] = gui.token
    child_env[GUI_CLAIM_ENV] = claim_code

    kwargs: Dict[str, Any] = {}
    if os.name == "posix":
        kwargs["start_new_session"] = True

    p = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=child_env,
        **kwargs,
    )

    if p.pid:
        gui.config_dir.mkdir(parents=True, exist_ok=True)
        if not _wait_for_server_ready(port):
            _stop_gui_process(p.pid)
            raise RuntimeError(
                "Elastro GUI server failed to start. Check that port "
                f"{port} is available and retry `elastro gui`."
            )
        with open(state_file, "w") as f:
            json.dump(
                {
                    "pid": p.pid,
                    "port": port,
                    "token": gui.token,
                    "version": __version__,
                },
                f,
            )

    return gui_claim_url(port, claim_code)


def _refresh_gui_claim(port: int, token: str) -> Optional[str]:
    """Ask a running GUI server for a fresh one-time claim code."""
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/auth/refresh-claim",
            method="POST",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(req, timeout=2) as response:
            payload = json.loads(response.read().decode())
        code = payload.get("code")
        return str(code) if code else None
    except (
        urllib.error.URLError,
        TimeoutError,
        json.JSONDecodeError,
        OSError,
        KeyError,
    ):
        return None
