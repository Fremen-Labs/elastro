"""
Elasticsearch Management Module.

A module for managing Elasticsearch operations within a pipeline process.
"""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("elastro-client")
except PackageNotFoundError:
    # Fallback for editable installs or when metadata is unavailable
    __version__ = "0.0.0-dev"

# Core component imports
from elastro.core.client import ElasticsearchClient
from elastro.core.index import IndexManager
from elastro.core.document import DocumentManager
from elastro.core.datastream import DatastreamManager

__all__ = [
    "ElasticsearchClient",
    "IndexManager",
    "DocumentManager",
    "DatastreamManager",
]
