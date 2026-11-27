"""
Elasticsearch client module.

This module provides the core client for connecting to Elasticsearch.
"""

from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlsplit, urlunsplit

from elasticsearch import AsyncElasticsearch, Elasticsearch
from elasticsearch.exceptions import (
    AuthenticationException,
    TransportError,
)
from elasticsearch.exceptions import (
    ConnectionError as ESConnectionError,
)

from elastro.config import get_config
from elastro.core.errors import AuthenticationError, ConnectionError, OperationError
from elastro.core.logger import get_logger

logger = get_logger(__name__)


def hosts_for_log(hosts: Union[str, List[str], None]) -> Union[str, List[str], None]:
    """Return hosts with userinfo stripped for log lines."""
    if isinstance(hosts, list):
        return [_strip_userinfo(item) for item in hosts]
    if hosts is None:
        return None
    return _strip_userinfo(hosts)


def _strip_userinfo(host: Any) -> Any:
    if not isinstance(host, str) or "://" not in host:
        return host
    try:
        parts = urlsplit(host)
        if not parts.hostname:
            return host
        netloc = parts.hostname
        if parts.port:
            netloc = f"{netloc}:{parts.port}"
        return urlunsplit(
            (parts.scheme, netloc, parts.path, parts.query, parts.fragment)
        )
    except ValueError:
        return host


class ElasticsearchClient:
    """
    Client for interacting with Elasticsearch.

    This class handles connection, authentication, and provides
    the base client instance for all operations.
    """

    def __init__(
        self,
        hosts: Optional[Union[str, List[str]]] = None,
        auth: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        retry_on_timeout: Optional[bool] = None,
        max_retries: Optional[int] = None,
        use_config: bool = True,
        username: Optional[str] = None,
        password: Optional[str] = None,
        api_key: Optional[str] = None,
        verify_certs: Optional[bool] = None,
        **kwargs: Any,
    ):
        """
        Initialize the Elasticsearch client.

        Args:
            hosts: Elasticsearch host or list of hosts
            auth: Authentication parameters (api_key or username/password)
            timeout: Connection timeout in seconds
            retry_on_timeout: Whether to retry on connection timeout
            max_retries: Maximum number of retries
            use_config: Whether to load settings from configuration
            username: Elasticsearch username (alternative to auth)
            password: Elasticsearch password (alternative to auth)
            api_key: Elasticsearch API key (alternative to auth)
            verify_certs: Whether to verify SSL certificates
            **kwargs: Additional parameters to pass to the Elasticsearch client
        """
        if use_config:
            # Load configuration
            config = get_config()
            es_config = config.get("elasticsearch", {})

            # Apply configuration with explicit parameters taking precedence
            self.hosts = hosts or es_config.get("hosts")
            _auth_config = auth or es_config.get("auth") or {}
            self.auth = (
                dict(_auth_config) if isinstance(_auth_config, dict) else _auth_config
            )
            self.timeout = timeout or es_config.get("timeout")
            self.retry_on_timeout = (
                retry_on_timeout
                if retry_on_timeout is not None
                else es_config.get("retry_on_timeout")
            )
            self.max_retries = (
                max_retries if max_retries is not None else es_config.get("max_retries")
            )
            self.verify_certs = (
                verify_certs
                if verify_certs is not None
                else es_config.get("verify_certs", True)
            )
        else:
            # Use only explicitly provided parameters
            self.hosts = hosts
            self.auth = dict(auth) if auth else {}
            self.timeout = timeout
            self.retry_on_timeout = retry_on_timeout
            self.max_retries = max_retries
            self.verify_certs = verify_certs if verify_certs is not None else True

        # Handle direct username/password/api_key parameters
        if username and password:
            if isinstance(self.auth, dict):
                self.auth["username"] = username
                self.auth["password"] = password
            else:
                self.auth = {"username": username, "password": password}

        if api_key:
            if isinstance(self.auth, dict):
                self.auth["api_key"] = api_key
            else:
                self.auth = {"api_key": api_key}

        self.client_kwargs = kwargs
        self._client: Optional[Elasticsearch] = None
        self._connected = False

        logger.debug(
            "Initialized ElasticsearchClient with hosts: %s", hosts_for_log(self.hosts)
        )

    @property
    def auth_type(self) -> Optional[str]:
        """Get the authentication type."""
        if not self.auth:
            return None
        if "type" in self.auth:
            return self.auth["type"]
        if "api_key" in self.auth:
            return "api_key"
        if "username" in self.auth and "password" in self.auth:
            return "basic"
        if "cloud_id" in self.auth:
            return "cloud"
        return None

    def _get_client_params(self) -> Dict[str, Any]:
        """Generate the parameters dictionary for the Elasticsearch client."""
        client_params = {
            "hosts": self.hosts,
        }

        # Only add SSL params for HTTPS URLs
        if isinstance(self.hosts, list):
            uses_https = any(
                h.startswith("https://") for h in self.hosts if isinstance(h, str)
            )
        else:
            uses_https = str(self.hosts).startswith("https://")

        if uses_https:
            client_params["verify_certs"] = self.verify_certs
            # Additional SSL settings when verify_certs is False
            if self.verify_certs is False:
                logger.warning(
                    "SSL certificate verification is disabled. This is not secure for production."
                )
                import urllib3

                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                client_params["ssl_assert_hostname"] = False
                client_params["ssl_show_warn"] = False

        # Add client kwargs
        client_params.update(self.client_kwargs)

        # Add optional parameters if they are not None
        # elasticsearch-py 8.x uses request_timeout (not timeout)
        if self.timeout is not None:
            client_params["request_timeout"] = self.timeout
        if self.retry_on_timeout is not None:
            client_params["retry_on_timeout"] = self.retry_on_timeout
        if self.max_retries is not None:
            client_params["max_retries"] = self.max_retries

        # Handle authentication
        if self.auth:
            # Add basic_auth directly if username and password are present
            if self.auth.get("username") and self.auth.get("password"):
                client_params["basic_auth"] = (
                    self.auth["username"],
                    self.auth["password"],
                )
            # Handle API key
            elif "api_key" in self.auth:
                client_params["api_key"] = self.auth["api_key"]
            # Handle cloud ID
            elif "cloud_id" in self.auth:
                client_params["cloud_id"] = self.auth["cloud_id"]

        return client_params

    def connect(self) -> bool:
        """
        Establish connection to Elasticsearch.

        Returns:
            True if the connection was established.

        Raises:
            ConnectionError: If unable to connect to Elasticsearch
            AuthenticationError: If authentication fails
        """
        logger.debug("Connecting to Elasticsearch at %s...", hosts_for_log(self.hosts))

        client_params = self._get_client_params()

        try:
            self._client = Elasticsearch(**client_params)
            assert self._client is not None
            # Verify connection by making a ping request
            ping_result = self._client.ping()
            if not ping_result:
                # Differentiate auth failure (401) from network failure
                detail = self._diagnose_ping_failure(client_params)
                logger.error("Ping failed during connection attempt: %s", detail)
                if "401" in detail or "authentication" in detail.lower():
                    raise AuthenticationError(detail)
                raise ConnectionError(detail)
            self._connected = True
            logger.debug("Successfully connected to Elasticsearch")
            return True
        except ESConnectionError as e:
            self._connected = False
            self._client = None
            logger.error("Connection failed: %s", e)
            raise ConnectionError(f"Failed to connect to Elasticsearch: {str(e)}")
        except AuthenticationException as e:
            self._connected = False
            self._client = None
            logger.error("Authentication failed: %s", e)
            raise AuthenticationError(f"Authentication failed: {str(e)}")
        except (ConnectionError, AuthenticationError):
            self._connected = False
            self._client = None
            raise
        except Exception as e:
            self._connected = False
            self._client = None
            logger.exception("Unexpected connection error: %s", e)
            raise ConnectionError(
                f"Unexpected error connecting to Elasticsearch: {str(e)}"
            )

    @staticmethod
    def _diagnose_ping_failure(client_params: Dict[str, Any]) -> str:
        """Probe the cluster root to distinguish auth failures from network issues."""
        import urllib.error
        import urllib.request

        hosts = client_params.get("hosts", [])
        url = hosts[0] if isinstance(hosts, list) and hosts else str(hosts)

        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as _resp:
                # Reachable without auth — security is likely disabled
                return "Failed to connect to Elasticsearch"
        except urllib.error.HTTPError as http_err:
            if http_err.code == 401:
                has_creds = "basic_auth" in client_params or "api_key" in client_params
                if has_creds:
                    return (
                        "Security is enabled and returned HTTP 401 — "
                        "the configured username/password or API key is invalid. "
                        "Check your Elastro configuration."
                    )
                return (
                    "Security is enabled (HTTP 401) but no credentials were provided. "
                    "Configure username/password via `elastro connect` or set "
                    "ELASTIC_USERNAME and ELASTIC_PASSWORD (or ELASTIC_API_KEY). "
                    "ELASTIC_AUTH_USERNAME / ELASTIC_AUTH_PASSWORD are also honored. "
                    "Host: ELASTIC_URL, or ELASTIC_HOST + ELASTIC_PORT + ELASTIC_PROTOCOL."
                )
            if http_err.code == 403:
                return (
                    "Security returned HTTP 403 Forbidden — the user lacks "
                    "sufficient privileges."
                )
            return f"Elasticsearch returned HTTP {http_err.code}"
        except Exception:
            return "Failed to connect to Elasticsearch (host unreachable)"

    def disconnect(self) -> None:
        """Disconnect from Elasticsearch and clean up resources."""
        if self._client:
            self._client.close()
            logger.info("Disconnected from Elasticsearch")
        self._client = None
        self._connected = False

    def get_client(self) -> Elasticsearch:
        """
        Get the underlying Elasticsearch client instance.

        Returns:
            Elasticsearch client instance

        Raises:
            ConnectionError: If client is not connected
        """
        if not self._connected or self._client is None:
            raise ConnectionError("Client is not connected. Call connect() first.")
        return self._client

    @property
    def native_client(self) -> Elasticsearch:
        """Alias for the underlying elasticsearch-py client (docs / ScrollHelper)."""
        return self.get_client()

    def info(self) -> Dict[str, Any]:
        """
        Return cluster information (name, version, tagline).

        Returns:
            Dictionary containing cluster info.

        Raises:
            ConnectionError: If client is not connected
            OperationError: If the info request fails
        """
        if self._client is None:
            raise ConnectionError("Client is not connected. Call connect() first.")
        try:
            response = self._client.info()
            if hasattr(response, "body"):
                return dict(response.body)
            return dict(response)
        except Exception as e:
            logger.error("Failed to fetch cluster info: %s", e)
            raise OperationError(f"Failed to fetch cluster info: {str(e)}") from e

    def get_async_client(self) -> AsyncElasticsearch:
        """
        Get a new AsyncElasticsearch client instance using the same connection parameters.

        Returns:
            AsyncElasticsearch client instance
        """
        return AsyncElasticsearch(**self._get_client_params())

    def is_connected(self) -> bool:
        """
        Check if the client is connected to Elasticsearch.

        Returns:
            True if connected, False otherwise
        """
        if self._client is None:
            return False

        try:
            return self._client.ping()
        except Exception:
            self._connected = False
            return False

    def health_check(self) -> Dict[str, Any]:
        """
        Check the health of the Elasticsearch cluster.

        Returns:
            Dict[str, Any]: Dictionary containing cluster health metrics:
                - cluster_name (str): Name of the cluster
                - status (str): Cluster health status (green, yellow, red)
                - number_of_nodes (int): Total number of nodes
                - active_shards (int): Number of active primary and replica shards
                - elasticsearch_version (str): The version of the cluster
                - active_primary_shards (int): Number of active primary shards
                - relocating_shards (int): Number of shards currently relocating
                - initializing_shards (int): Number of shards currently initializing
                - unassigned_shards (int): Number of unassigned shards

        Raises:
            ConnectionError: If unable to connect to Elasticsearch
            OperationError: If the health check operation fails
        """
        if self._client is None:
            raise ConnectionError("Client is not connected. Call connect() first.")

        try:
            health = self._client.cluster.health()
            info = self._client.info()

            result = {
                "cluster_name": health.get("cluster_name"),
                "status": health.get("status"),
                "number_of_nodes": health.get("number_of_nodes"),
                "active_shards": health.get("active_shards"),
                "elasticsearch_version": info.get("version", {}).get("number"),
                "active_primary_shards": health.get("active_primary_shards"),
                "relocating_shards": health.get("relocating_shards"),
                "initializing_shards": health.get("initializing_shards"),
                "unassigned_shards": health.get("unassigned_shards"),
            }

            logger.debug("Cluster health check: %s", result.get("status"))
            return result
        except ESConnectionError:
            logger.error("Lost connection during health check")
            raise ConnectionError(
                "Lost connection to Elasticsearch during health check"
            )
        except TransportError as e:
            logger.error("Transport error during health check: %s", e)
            raise OperationError(f"Failed to retrieve cluster health: {str(e)}")
        except Exception as e:
            logger.exception("Unexpected error during health check")
            raise OperationError(f"Unexpected error during health check: {str(e)}")

    @property
    def client(self) -> Elasticsearch:
        """
        Get the underlying Elasticsearch client instance.

        Returns:
            Elasticsearch client instance

        Raises:
            ConnectionError: If client is not connected
        """
        if self._client is None:
            raise ConnectionError("Client is not connected. Call connect() first.")
        return self._client
