"""
CLI proxy routes — /api/cluster/{cluster_name}/cli endpoint.
"""

import os
import shlex
import subprocess
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException

from elastro.server.schemas import ClusterCLIRequestSchema

router = APIRouter(prefix="/api", tags=["cli"])


def cli_routes(read_config: Any, verify_token: Any) -> APIRouter:
    """Bind CLI proxy routes to shared config accessor and auth functions."""

    @router.post("/cluster/{cluster_name}/cli")
    def execute_cli_command(
        cluster_name: str,
        req: ClusterCLIRequestSchema,
        token: str = Depends(verify_token),
    ) -> Dict[str, Any]:
        config = read_config()
        target_c = None

        for c in config.get("clusters", []):
            if c["name"] == cluster_name:
                target_c = c
                break

        if not target_c:
            raise HTTPException(
                status_code=404,
                detail=f"Cluster '{cluster_name}' not found in configuration.",
            )

        user_cmd = req.command.strip()
        if not user_cmd:
            raise HTTPException(status_code=400, detail="Command cannot be empty")

        # Strip out "elastro" prefix if the user typed it naturally
        if user_cmd == "elastro":
            user_cmd = ""
        elif user_cmd.startswith("elastro "):
            user_cmd = user_cmd[8:]

        # Safely split user string into bash args
        try:
            args = shlex.split(user_cmd) if user_cmd else []
        except ValueError as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid shell command formatting: {e}"
            )

        # Ensure scheme is present for subprocess execution
        host = target_c["host"]
        if not host.startswith("http://") and not host.startswith("https://"):
            host = "http://" + host

        # Construct strict elastro command base
        cmd = ["elastro", "--host", host]
        cmd.extend(args)

        # Clone env and inject cluster credentials securely
        run_env = os.environ.copy()
        run_env["FORCE_COLOR"] = "1"
        run_env["COLUMNS"] = "400"
        run_env["ELASTRO_LOG_LEVEL"] = "WARNING"
        run_env["ELASTRO_GUI_MODE"] = "1"

        auth_conf = target_c.get("auth", {})
        if "api_key" in auth_conf and auth_conf["api_key"]:
            run_env["ELASTIC_API_KEY"] = auth_conf["api_key"]
        elif "username" in auth_conf:
            run_env["ELASTIC_USERNAME"] = auth_conf["username"]
            run_env["ELASTIC_PASSWORD"] = auth_conf.get("password", "")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                input=req.stdin,
                timeout=30,
                env=run_env,
            )

            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += "\n" + result.stderr

            return {"exit_code": result.returncode, "output": output}
        except subprocess.TimeoutExpired:
            raise HTTPException(
                status_code=408,
                detail="Command execution timed out after 30 seconds",
            )
        except FileNotFoundError:
            raise HTTPException(
                status_code=500,
                detail="The 'elastro' executable was not found on the system path.",
            )
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to execute native CLI: {str(e)}"
            )

    return router
