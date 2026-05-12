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

import os
import secrets
import json
from pathlib import Path
from typing import Dict, Any, Optional

import uvicorn
from fastapi import FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from elastro.core.logger import get_logger

logger = get_logger(__name__)


class ElastroGUI:
    def __init__(self) -> None:
        self.config_dir = Path.home() / ".elastic"
        self.config_file = self.config_dir / "gui_config.json"
        self.token = secrets.token_urlsafe(32)
        self.app = FastAPI(title="Elastro Local GUI API")

        # Setup static dir — points to the embedded Vue build
        self.static_dir = Path(__file__).parent.parent / "gui"

        self._setup_routes()

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

    def verify_token(self, authorization: Optional[str] = Header(None)) -> str:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Unauthorized")
        token = authorization.split(" ")[1]

        # Prevent timing attacks
        if not secrets.compare_digest(token, self.token):
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
        from elastro.server.routes.config import config_routes
        from elastro.server.routes.clusters import cluster_routes
        from elastro.server.routes.indices import index_routes
        from elastro.server.routes.cli import cli_routes

        self.app.include_router(
            config_routes(self._read_config, self._write_config, self.verify_token)
        )
        self.app.include_router(cluster_routes(self._read_config, self.verify_token))
        self.app.include_router(index_routes(self._read_config, self.verify_token))
        self.app.include_router(cli_routes(self._read_config, self.verify_token))

        # Mount static GUI files
        if self.static_dir.exists():
            self.app.mount(
                "/assets",
                StaticFiles(directory=self.static_dir / "assets"),
                name="assets",
            )

            @self.app.get("/{full_path:path}")
            def serve_gui(full_path: str) -> HTMLResponse:
                index_path = self.static_dir / "index.html"
                if index_path.exists():
                    with open(index_path, "r") as f:
                        return HTMLResponse(content=f.read())
                return HTMLResponse(
                    "GUI not built. Run npm run build in packages/gui.",
                    status_code=404,
                )


def run_server(port: int = 8080, token: str = "") -> None:
    gui = ElastroGUI()
    if token:
        gui.token = token  # Override for the process

    # We use log_level warning to keep the detached CLI clean
    uvicorn.run(gui.app, host="127.0.0.1", port=port, log_level="warning")


def launch_gui_process() -> str:
    """Launches the server in a separate process and returns the access URL."""
    import socket

    gui = ElastroGUI()
    state_file = gui.config_dir / ".gui_state.json"

    # Check if process is already running
    if state_file.exists():
        try:
            with open(state_file, "r") as f:
                state = json.load(f)
                pid = state.get("pid")
                port = state.get("port")
                token = state.get("token")

            if pid and port and token:
                try:
                    os.kill(pid, 0)
                    # Process is still alive, reuse it!
                    return f"http://127.0.0.1:{port}?token={token}"
                except OSError:
                    # Process is dead, delete state file
                    state_file.unlink(missing_ok=True)
        except Exception:
            pass

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
    import sys
    import subprocess

    cmd = [
        sys.executable,
        "-c",
        f"from elastro.server import run_server; run_server({port}, '{gui.token}')",
    ]

    kwargs: Dict[str, Any] = {}
    if os.name == "posix":
        kwargs["start_new_session"] = True

    p = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **kwargs,
    )

    if p.pid:
        gui.config_dir.mkdir(parents=True, exist_ok=True)
        with open(state_file, "w") as f:
            json.dump({"pid": p.pid, "port": port, "token": gui.token}, f)

    url = f"http://127.0.0.1:{port}?token={gui.token}"
    return url
