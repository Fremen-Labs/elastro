"""
Shared services for the Elastro GUI API.

Provides reusable cluster client construction and index size parsing
to eliminate duplication across route modules.
"""

from typing import Dict, Any, Tuple
from elastro.core.client import ElasticsearchClient
from elastro.core.logger import get_logger

logger = get_logger(__name__)


def build_es_client(cluster_config: Dict[str, Any]) -> ElasticsearchClient:
    """
    Construct and connect an ElasticsearchClient from a GUI cluster config entry.

    This is the single, canonical factory for constructing ES clients within
    the GUI server. All route modules MUST use this instead of inlining
    client construction logic.

    Args:
        cluster_config: A dict from gui_config.json with 'host' and 'auth' keys.

    Returns:
        A connected ElasticsearchClient instance.

    Raises:
        elastro.core.errors.ConnectionError: If the cluster is unreachable.
    """
    auth_conf = cluster_config.get("auth", {})

    auth_kwargs: Dict[str, Any] = {}
    if "api_key" in auth_conf and auth_conf["api_key"]:
        auth_kwargs["api_key"] = auth_conf["api_key"]
    elif "username" in auth_conf:
        auth_kwargs["basic_auth"] = (
            auth_conf["username"],
            auth_conf.get("password", ""),
        )

    host = cluster_config["host"]
    if not host.startswith("http://") and not host.startswith("https://"):
        host = "http://" + host

    client = ElasticsearchClient(hosts=[host], **auth_kwargs)
    client.connect()
    return client


def parse_index_size(raw_size: str) -> Tuple[int, str]:
    """
    Parse an Elasticsearch human-readable size string (e.g. '35.6mb') into bytes.

    Returns:
        A tuple of (size_in_bytes, raw_size_string).
    """
    if not raw_size:
        return 0, "0b"

    val_str = ""
    mult = 1

    lower = raw_size.lower().strip()
    if lower.endswith("tb"):
        mult = 1024**4
        val_str = lower[:-2]
    elif lower.endswith("gb"):
        mult = 1024**3
        val_str = lower[:-2]
    elif lower.endswith("mb"):
        mult = 1024**2
        val_str = lower[:-2]
    elif lower.endswith("kb"):
        mult = 1024
        val_str = lower[:-2]
    elif lower.endswith("b"):
        mult = 1
        val_str = lower[:-1]

    try:
        size_bytes = int(float(val_str) * mult) if val_str else 0
    except (ValueError, TypeError):
        size_bytes = 0

    return size_bytes, raw_size
