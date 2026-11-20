"""
CLI proxy routes — /api/cluster/{cluster_name}/cli endpoint.
"""

import os
import shlex
import subprocess
import time
from typing import Any, Dict, List, Sequence, Tuple

from fastapi import APIRouter, Depends, HTTPException

from elastro.core.logger import get_logger
from elastro.server.schemas import ClusterCLIRequestSchema

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["cli"])

_CLI_OUTPUT_CAP_BYTES = 256 * 1024

_GLOBAL_OPTION_EXACT = frozenset(
    {"-c", "--config", "-p", "--profile", "-h", "--host", "-o", "--output"}
)
_GLOBAL_OPTION_PREFIXES = ("--config=", "--profile=", "--host=", "--output=")
_VERBOSE_FLAGS = frozenset({"-v", "--verbose"})

# Longer paths first so "snapshot repo delete" wins over a 2-token prefix.
_ALWAYS_DESTRUCTIVE_PATHS: Tuple[Tuple[str, ...], ...] = (
    ("snapshot", "repo", "delete"),
    ("utils", "templates", "delete"),
    ("utils", "aliases", "delete"),
    ("index", "delete"),
    ("index", "fix"),
    ("doc", "delete"),
    ("doc", "bulk-delete"),
    ("datastream", "delete"),
    ("snapshot", "delete"),
    ("snapshot", "restore"),
    ("ilm", "delete"),
    ("template", "delete"),
    ("script", "delete"),
    ("memory", "prune"),
    ("tasks", "cancel"),
)


def _parse_user_argv(command: str) -> List[str]:
    """Split *command* and strip a single leading ``elastro`` token."""
    args = shlex.split(command) if command else []
    if args and args[0] == "elastro":
        return args[1:]
    return args


def _skip_global_options(argv: Sequence[str]) -> List[str]:
    """Drop root CLI options from the front of *argv*.

    A token is global when it is ``-c/--config``, ``-p/--profile``,
    ``-h/--host``, ``-o/--output``, or starts with ``--config=``,
    ``--profile=``, ``--host=``, or ``--output=``. The next token is
    consumed only when the option token has no ``=``. ``-v/--verbose``
    consumes nothing.
    """
    i = 0
    n = len(argv)
    while i < n:
        token = argv[i]
        if token in _VERBOSE_FLAGS:
            i += 1
            continue
        if token in _GLOBAL_OPTION_EXACT:
            i += 1
            if i < n:
                i += 1
            continue
        if token.startswith(_GLOBAL_OPTION_PREFIXES):
            i += 1
            continue
        break
    return list(argv[i:])


def _is_destructive_cli_argv(user_argv: Sequence[str]) -> bool:
    """Return True when *user_argv* (not the prepended subprocess list) mutates."""
    tokens = _skip_global_options(user_argv)
    if not tokens:
        return False
    for path in _ALWAYS_DESTRUCTIVE_PATHS:
        length = len(path)
        if len(tokens) >= length and tuple(tokens[:length]) == path:
            return True
    if len(tokens) >= 2 and tuple(tokens[:2]) == ("health", "fix"):
        return "--dry-run" not in tokens
    if len(tokens) >= 2 and tuple(tokens[:2]) == ("health", "assess"):
        return "--fix" in tokens and "--dry-run" not in tokens
    if len(tokens) >= 2 and tuple(tokens[:2]) == ("cluster", "settings"):
        return any(
            token == "--enable-routing" or token.startswith("--enable-routing=")
            for token in tokens
        )
    return False


def _cap_cli_output(text: str, limit: int = _CLI_OUTPUT_CAP_BYTES) -> Tuple[str, bool]:
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= limit:
        return text, False
    return encoded[:limit].decode("utf-8", errors="ignore"), True


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

        try:
            user_argv = _parse_user_argv(user_cmd)
        except ValueError as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid shell command formatting: {e}"
            )

        # confirm is a trusted-client foot-gun, not authorization.
        if _is_destructive_cli_argv(user_argv) and not req.confirm:
            logger.warning("CLI proxy blocked argv=%s", user_argv)
            raise HTTPException(
                status_code=409,
                detail={"code": "confirmation_required", "argv": user_argv},
            )

        # Ensure scheme is present for subprocess execution
        host = target_c["host"]
        if not host.startswith("http://") and not host.startswith("https://"):
            host = "http://" + host

        # Construct strict elastro command base
        cmd = ["elastro", "--host", host]
        cmd.extend(user_argv)

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

        started = time.monotonic()
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

            output, truncated = _cap_cli_output(output)
            duration_ms = int((time.monotonic() - started) * 1000)
            logger.info(
                "CLI proxy spawn argv=%s exit_code=%s duration_ms=%s truncated=%s",
                user_argv,
                result.returncode,
                duration_ms,
                truncated,
            )
            return {
                "exit_code": result.returncode,
                "output": output,
                "truncated": truncated,
            }
        except subprocess.TimeoutExpired:
            logger.warning(
                "CLI proxy timeout argv=%s duration_ms=%s",
                user_argv,
                int((time.monotonic() - started) * 1000),
            )
            raise HTTPException(
                status_code=408,
                detail="Command execution timed out after 30 seconds",
            )
        except FileNotFoundError:
            logger.error("CLI proxy failed argv=%s", user_argv, exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="The 'elastro' executable was not found on the system path.",
            )
        except Exception as e:
            logger.error("CLI proxy failed argv=%s", user_argv, exc_info=True)
            raise HTTPException(
                status_code=500, detail=f"Failed to execute native CLI: {str(e)}"
            )

    return router
