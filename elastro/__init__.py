"""
Elasticsearch Management Module.

A module for managing Elasticsearch operations within a pipeline process.
"""

__version__ = "1.2.0"

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
