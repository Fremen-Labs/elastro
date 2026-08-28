"""
Elastro Fast-Path Daemon.

Maintains a persistent Elasticsearch client for sub-millisecond agentic queries.

The XML-RPC control plane is localhost-only and authenticated with a shared
secret. Non-loopback binds are refused so the daemon cannot be left open on
0.0.0.0 without auth.
"""

from __future__ import annotations

import argparse
import ipaddress
import os
import secrets
from pathlib import Path
from typing import Any, List, Optional, Tuple
from xmlrpc.client import ServerProxy, Transport
from xmlrpc.server import SimpleXMLRPCServer

from elastro.cli.output import format_output
from elastro.config.loader import get_config
from elastro.core.client import ElasticsearchClient
from elastro.core.document import DocumentManager
from elastro.core.query_builder import QueryBuilder

DAEMON_DEFAULT_HOST = "127.0.0.1"
DAEMON_DEFAULT_PORT = 9201
DAEMON_TOKEN_ENV = "ELASTRO_DAEMON_TOKEN"
_LOOPBACK_NAMES = {"127.0.0.1", "localhost", "::1"}


class DaemonBindError(ValueError):
    """Raised when the daemon is asked to bind to a non-loopback address."""


def is_loopback_bind(host: str) -> bool:
    """Return True if *host* is a loopback name or address."""
    if host in _LOOPBACK_NAMES:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def validate_daemon_bind(host: str) -> None:
    """Refuse non-localhost binds so the XML-RPC plane stays local."""
    if not is_loopback_bind(host):
        raise DaemonBindError(
            f"Refusing to bind the Elastro daemon to {host!r}. "
            "The XML-RPC control plane must not be exposed on a non-loopback "
            "address. Bind to 127.0.0.1 (the default) or ::1."
        )


def daemon_token_path() -> Path:
    """Path to the on-disk shared secret (mode 0600)."""
    return Path.home() / ".elastic" / "daemon.token"


def load_daemon_token() -> Optional[str]:
    """Load the daemon shared secret from env or the token file.

    Does not create a token. Returns None when neither source has one.
    """
    env_token = os.environ.get(DAEMON_TOKEN_ENV)
    if env_token:
        return env_token
    path = daemon_token_path()
    if path.exists():
        token = path.read_text(encoding="utf-8").strip()
        return token or None
    return None


def load_or_create_daemon_token() -> str:
    """Return the daemon shared secret, generating one if needed."""
    existing = load_daemon_token()
    if existing:
        return existing
    path = daemon_token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(32)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(token)
        handle.write("\n")
    return token


class _TimeoutTransport(Transport):
    """xmlrpc transport with a per-connection timeout."""

    def __init__(self, timeout: float) -> None:
        super().__init__()
        self._timeout = timeout

    def make_connection(self, host: Any) -> Any:
        conn = super().make_connection(host)
        conn.timeout = self._timeout
        return conn


class AuthenticatedRPC:
    """XML-RPC dispatcher that requires the shared secret as the first arg."""

    def __init__(self, service: Any, token: str) -> None:
        self._service = service
        self._token = token

    def _dispatch(self, method: str, params: Tuple[Any, ...]) -> Any:
        if method.startswith("_"):
            raise Exception("Unauthorized")
        if not params:
            raise Exception("Unauthorized: missing daemon token")
        provided = str(params[0])
        if not secrets.compare_digest(provided, self._token):
            raise Exception("Unauthorized")
        func = getattr(self._service, method)
        return func(*params[1:])


def probe_daemon(
    host: str = DAEMON_DEFAULT_HOST,
    port: int = DAEMON_DEFAULT_PORT,
    timeout: float = 1.0,
) -> Tuple[bool, str]:
    """Talk to the real XML-RPC daemon (not HTTP /health).

    Returns (online, detail). Never requires a live Elasticsearch cluster —
    it only checks that the daemon process answers health_check().
    """
    token = load_daemon_token()
    if not token:
        return False, "no daemon token found"
    try:
        proxy = ServerProxy(
            f"http://{host}:{port}",
            allow_none=True,
            transport=_TimeoutTransport(timeout),
        )
        ok = bool(proxy.health_check(token))
        if ok:
            return True, "online"
        return False, "health_check returned false"
    except Exception as exc:
        return False, str(exc)


def create_daemon_server(
    host: str = DAEMON_DEFAULT_HOST,
    port: int = DAEMON_DEFAULT_PORT,
    service: Optional[Any] = None,
    token: Optional[str] = None,
) -> SimpleXMLRPCServer:
    """Build an authenticated XML-RPC server without connecting to ES unless needed."""
    validate_daemon_bind(host)
    secret = token if token is not None else load_or_create_daemon_token()
    if service is None:
        service = ElastroRPCService()
    server = SimpleXMLRPCServer((host, port), allow_none=True, logRequests=False)
    server.register_instance(AuthenticatedRPC(service, secret))
    return server


class ElastroRPCService:
    def __init__(self) -> None:
        self.client: Optional[ElasticsearchClient] = None
        self._connect()

    def _connect(self) -> None:
        config = get_config()
        self.client = ElasticsearchClient(
            hosts=config["elasticsearch"]["hosts"],
            auth=config["elasticsearch"].get("auth"),
            timeout=config["elasticsearch"].get("timeout", 30),
            retry_on_timeout=config["elasticsearch"].get("retry_on_timeout", True),
            max_retries=config["elasticsearch"].get("max_retries", 3),
        )
        self.client.connect()

    def health_check(self) -> bool:
        if self.client:
            return self.client.is_connected()
        return False

    def fast_path_search(self, args: List[str]) -> str:
        if not self.client:
            return "Error: Elasticsearch client not connected in daemon."

        parser = argparse.ArgumentParser()
        parser.add_argument("index", type=str)
        parser.add_argument("query", type=str, nargs="?", default=None)
        parser.add_argument("--size", type=int, default=10)
        parser.add_argument("--from", type=int, default=0, dest="from_")

        # Query types
        parser.add_argument("--match", action="append", default=[])
        parser.add_argument(
            "--match-phrase", action="append", default=[], dest="match_phrase"
        )
        parser.add_argument("--term", action="append", default=[])
        parser.add_argument("--terms", action="append", default=[])
        parser.add_argument("--range", action="append", default=[])
        parser.add_argument("--prefix", action="append", default=[])
        parser.add_argument("--wildcard", action="append", default=[])
        parser.add_argument("--exists", action="append", default=[])
        parser.add_argument("--ids", action="append", default=[])
        parser.add_argument("--fuzzy", action="append", default=[])

        # Excludes
        parser.add_argument(
            "--exclude-match", action="append", default=[], dest="exclude_match"
        )
        parser.add_argument(
            "--exclude-term", action="append", default=[], dest="exclude_term"
        )

        parser.add_argument("--output", "-o", type=str, default="json")

        try:
            parsed, _ = parser.parse_known_args(args)
        except Exception as e:
            return f"Error parsing arguments: {str(e)}"

        doc_manager = DocumentManager(self.client)

        inner_query = QueryBuilder.build_bool_query(
            must_match=getattr(parsed, "match", None),
            must_match_phrase=getattr(parsed, "match_phrase", None),
            must_term=getattr(parsed, "term", None),
            must_terms=getattr(parsed, "terms", None),
            must_range=getattr(parsed, "range", None),
            must_prefix=getattr(parsed, "prefix", None),
            must_wildcard=getattr(parsed, "wildcard", None),
            must_exists=getattr(parsed, "exists", None),
            must_ids=getattr(parsed, "ids", None),
            must_fuzzy=getattr(parsed, "fuzzy", None),
            exclude_match=getattr(parsed, "exclude_match", None),
            exclude_term=getattr(parsed, "exclude_term", None),
            query_string=getattr(parsed, "query", None),
        )

        query_body = {"query": inner_query}
        options = {
            "size": getattr(parsed, "size", 10),
            "from": getattr(parsed, "from_", 0),
        }

        try:
            results = doc_manager.search(
                getattr(parsed, "index", ""), query_body, options
            )
            output_format = getattr(parsed, "output", "json")
            output_str = format_output(results, output_format=output_format)
            return output_str
        except Exception as e:
            return f"Daemon search error: {str(e)}"


def start_daemon(
    host: str = DAEMON_DEFAULT_HOST,
    port: int = DAEMON_DEFAULT_PORT,
    service: Optional[Any] = None,
    token: Optional[str] = None,
) -> None:
    """Start the Elastro XML-RPC daemon server (localhost + shared secret)."""
    server = create_daemon_server(host=host, port=port, service=service, token=token)
    print(f"Starting Elastro XML-RPC Daemon on {host}:{port}...", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down daemon.")
    finally:
        server.server_close()
