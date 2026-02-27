import os
import secrets
import json
import logging
import multiprocessing
from pathlib import Path
from typing import Dict, Any, List, Optional
import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Header, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from elastro.core.client import ElasticsearchClient

# Optional Pydantic based schema since Elastro uses Pydantic
from pydantic import BaseModel

class AuthSchema(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    api_key: Optional[str] = None

class ClusterConfigSchema(BaseModel):
    name: str
    host: str
    auth: AuthSchema

class ElastroGUI:
    def __init__(self):
        self.config_dir = Path.home() / ".elastro"
        self.config_file = self.config_dir / "config.json"
        self.token = secrets.token_urlsafe(32)
        self.app = FastAPI(title="Elastro Local GUI API")
        
        # Setup static dir
        self.static_dir = Path(__file__).parent / "gui"
        
        self._setup_routes()

    def _ensure_config(self):
        if not self.config_dir.exists():
            self.config_dir.mkdir(parents=True)
        if not self.config_file.exists():
            with open(self.config_file, "w") as f:
                json.dump({"clusters": []}, f)
                
    def _read_config(self) -> Dict[str, Any]:
        self._ensure_config()
        try:
            with open(self.config_file, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {"clusters": []}

    def _write_config(self, config: Dict[str, Any]):
        self._ensure_config()
        with open(self.config_file, "w") as f:
            json.dump(config, f, indent=4)

    def verify_token(self, authorization: str = Header(None)):
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid token")
        token = authorization.split(" ")[1]
        
        # Prevent timing attacks
        if not secrets.compare_digest(token, self.token):
            raise HTTPException(status_code=401, detail="Unauthorized")
        return token

    def _setup_routes(self):
        # Enable CORS for local dev logic
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        @self.app.get("/api/config")
        def get_config(token: str = Depends(self.verify_token)):
            config = self._read_config()
            # Mask secrets
            safe_clusters = []
            for c in config.get("clusters", []):
                safe_c = c.copy()
                if "auth" in safe_c:
                    if "password" in safe_c["auth"]:
                        safe_c["auth"]["password"] = "******"
                    if "api_key" in safe_c["auth"]:
                        safe_c["auth"]["api_key"] = "******"
                safe_clusters.append(safe_c)
                
            return {"clusters": safe_clusters}

        @self.app.post("/api/config/clusters")
        def add_cluster(cluster: ClusterConfigSchema, token: str = Depends(self.verify_token)):
            config = self._read_config()
            
            # Check for existing
            clusters = config.get("clusters", [])
            for c in clusters:
                if c["name"] == cluster.name:
                    raise HTTPException(status_code=400, detail="Cluster name already exists")
                    
            clusters.append(cluster.model_dump())
            config["clusters"] = clusters
            self._write_config(config)
            
            return {"status": "success"}

        @self.app.get("/api/clusters")
        def get_clusters_health(token: str = Depends(self.verify_token)):
            config = self._read_config()
            results = []
            
            for c in config.get("clusters", []):
                try:
                    # Initialize Elastro Client
                    auth_conf = c.get("auth", {})
                    
                    auth_kwargs = {}
                    if "api_key" in auth_conf and auth_conf["api_key"]:
                         auth_kwargs["api_key"] = auth_conf["api_key"]
                    elif "username" in auth_conf:
                         auth_kwargs["basic_auth"] = (auth_conf["username"], auth_conf.get("password", ""))

                    # Ensure scheme is present
                    host = c["host"]
                    if not host.startswith("http://") and not host.startswith("https://"):
                        host = "http://" + host

                    client = ElasticsearchClient(
                        hosts=[host],
                        **auth_kwargs
                    )
                    
                    client.connect()
                    
                    # Get index stats
                    es = client.client
                    health = es.cluster.health()
                    
                    # Get index stats
                    # Omit bytes="b" so we get standard ES string formats like '35.6mb' safely
                    idx_res = es.cat.indices(format="json")
                    
                    unstable = []
                    largest_idx_name = "N/A"
                    largest_idx_size = -1
                    largest_idx_raw = "0B"
                    
                    for idx in idx_res:
                        if idx.get("health") in ("yellow", "red") and not idx.get("index", "").startswith("."):
                            unstable.append({
                                "index": idx.get("index"),
                                "health": idx.get("health"),
                                "status": idx.get("status")
                            })
                            
                        try:
                            raw_size = str(idx.get("store.size", "0b")).strip().lower()
                            val_str = raw_size
                            mult = 1
                            if raw_size.endswith("pb"): mult = 1024**5; val_str = raw_size[:-2]
                            elif raw_size.endswith("tb"): mult = 1024**4; val_str = raw_size[:-2]
                            elif raw_size.endswith("gb"): mult = 1024**3; val_str = raw_size[:-2]
                            elif raw_size.endswith("mb"): mult = 1024**2; val_str = raw_size[:-2]
                            elif raw_size.endswith("kb"): mult = 1024; val_str = raw_size[:-2]
                            elif raw_size.endswith("b"): mult = 1; val_str = raw_size[:-1]
                            
                            size_bytes = int(float(val_str) * mult) if val_str else 0
                            
                            if size_bytes > largest_idx_size:
                                largest_idx_size = size_bytes
                                largest_idx_name = idx.get("index", "Unknown")
                                largest_idx_raw = idx.get("store.size", "0b")
                        except (ValueError, TypeError):
                            pass
                            
                    results.append({
                        "name": c["name"],
                        "host": c["host"],
                        "health": health["status"],
                        "index_count": len(idx_res),
                        "largest_index": {"name": largest_idx_name, "size": largest_idx_raw},
                        "unstable_indices": unstable
                    })
                    
                except Exception as e:
                    logging.error(f"Failed to connect to {c['name']}: {str(e)}")
                    results.append({
                        "name": c["name"],
                        "host": c["host"],
                        "health": "offline",
                        "index_count": 0,
                        "largest_index": {"name": "N/A", "size": "0B"},
                        "unstable_indices": []
                    })
                    
            return {"clusters": results}

        # Mount static GUI files
        if self.static_dir.exists():
            self.app.mount("/assets", StaticFiles(directory=self.static_dir / "assets"), name="assets")
            
            @self.app.get("/{full_path:path}")
            def serve_gui(full_path: str):
                index_path = self.static_dir / "index.html"
                if index_path.exists():
                    with open(index_path, "r") as f:
                        return HTMLResponse(content=f.read())
                return HTMLResponse("GUI not built. Run npm run build in packages/gui.", status_code=404)

def run_server(port: int = 8080, token: str = ""):
    gui = ElastroGUI()
    if token:
        gui.token = token # Override for the process
        
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
            s.bind(('127.0.0.1', port))
    except OSError:
        # Port is in use (by something else), get a random free port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', 0))
            port = s.getsockname()[1]
    
    # We use multiprocessing to detach the server
    p = multiprocessing.Process(target=run_server, args=(port, gui.token))
    p.daemon = False # We want it to run after CLI exits
    p.start()
    
    if p.pid:
        with open(state_file, "w") as f:
            json.dump({"pid": p.pid, "port": port, "token": gui.token}, f)
            
    url = f"http://127.0.0.1:{port}?token={gui.token}"
    return url
