"""
Elasticsearch client module.

This module provides the core client for connecting to Elasticsearch.
"""

from typing import Dict, List, Optional, Union, Any
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import (
    ConnectionError as ESConnectionError,
    AuthenticationException,
    TransportError,
)
from elastro.core.errors import ConnectionError, AuthenticationError, OperationError
from elastro.config import get_config
from elastro.core.logger import get_logger

logger = get_logger(__name__)


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
        **kwargs
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
            self.auth = auth or es_config.get("auth") or {}
            self.timeout = timeout or es_config.get("timeout")
            self.retry_on_timeout = retry_on_timeout if retry_on_timeout is not None else es_config.get("retry_on_timeout")
            self.max_retries = max_retries if max_retries is not None else es_config.get("max_retries")
            self.verify_certs = verify_certs if verify_certs is not None else es_config.get("verify_certs", True)
        else:
            # Use only explicitly provided parameters
            self.hosts = hosts
            self.auth = auth or {}
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
        self._client = None
        self._connected = False
        
        logger.debug(f"Initialized ElasticsearchClient with hosts: {self.hosts}")

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

    def connect(self) -> None:
        """
        Establish connection to Elasticsearch.

        Raises:
            ConnectionError: If unable to connect to Elasticsearch
            AuthenticationError: If authentication fails
        """
        logger.info(f"Connecting to Elasticsearch at {self.hosts}...")
        
        client_params = {
            "hosts": self.hosts,
        }
        
        # Only add SSL params for HTTPS URLs
        if isinstance(self.hosts, list):
            uses_https = any(h.startswith('https://') for h in self.hosts if isinstance(h, str))
        else:
            uses_https = str(self.hosts).startswith('https://')
            
        if uses_https:
            client_params["verify_certs"] = self.verify_certs
            # Additional SSL settings when verify_certs is False
            if self.verify_certs is False:
                logger.warning("SSL certificate verification is disabled. This is not secure for production.")
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                client_params["ssl_assert_hostname"] = False
                client_params["ssl_show_warn"] = False
        
        # Add client kwargs
        client_params.update(self.client_kwargs)
        
        # Add optional parameters if they are not None
        if self.retry_on_timeout is not None:
            client_params["retry_on_timeout"] = self.retry_on_timeout
        if self.max_retries is not None:
            client_params["max_retries"] = self.max_retries
        # Note: timeout is handled in request_config in newer versions

        # Handle authentication
        if self.auth:
            # Add basic_auth directly if username and password are present
            if self.auth.get("username") and self.auth.get("password"):
                client_params["basic_auth"] = (self.auth["username"], self.auth["password"])
            # Handle API key 
            elif "api_key" in self.auth:
                client_params["api_key"] = self.auth["api_key"]
            # Handle cloud ID
            elif "cloud_id" in self.auth:
                client_params["cloud_id"] = self.auth["cloud_id"]

        # Prepare safe loggable params
        log_params = client_params.copy()
        if "basic_auth" in log_params:
            user = log_params["basic_auth"][0]
            log_params["basic_auth"] = (user, "******")
            
        log_auth = self.auth.copy() if self.auth else {}
        if "password" in log_auth:
            log_auth["password"] = "******"
            
        logger.info(f"Connecting with params: hosts={client_params.get('hosts')}, auth={log_auth}, basic_auth={log_params.get('basic_auth')}")

        try:
            self._client = Elasticsearch(**client_params)  # type: ignore
            # Verify connection by making a ping request
            ping_result = self._client.ping()
            if not ping_result:
                logger.error("Ping failed during connection attempt")
                raise ConnectionError("Failed to connect to Elasticsearch")
            self._connected = True
            logger.info("Successfully connected to Elasticsearch")
        except ESConnectionError as e:
            self._connected = False
            self._client = None
            logger.error(f"Connection failed: {str(e)}")
            raise ConnectionError(f"Failed to connect to Elasticsearch: {str(e)}")
        except AuthenticationException as e:
            self._connected = False
            self._client = None
            logger.error(f"Authentication failed: {str(e)}")
            raise AuthenticationError(f"Authentication failed: {str(e)}")
        except Exception as e:
            self._connected = False
            self._client = None
            logger.exception(f"Unexpected connection error: {str(e)}")
            raise ConnectionError(f"Unexpected error connecting to Elasticsearch: {str(e)}")

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
            Dict containing cluster health information

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
            
            logger.debug(f"Cluster health check: {result.get('status')}")
            return result
        except ESConnectionError:
            logger.error("Lost connection during health check")
            raise ConnectionError("Lost connection to Elasticsearch during health check")
        except TransportError as e:
            logger.error(f"Transport error during health check: {str(e)}")
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
