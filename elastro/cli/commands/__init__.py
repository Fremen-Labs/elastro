"""
Command handlers for the CLI.

This module contains the implementations of the CLI commands.
"""

from elastro.cli.commands.index import *
from elastro.cli.commands.document import *
from elastro.cli.commands.datastream import *
from elastro.cli.commands.config import *
from elastro.cli.commands.utils import *

__all__ = [
    # Index commands
    "create_index", "get_index", "index_exists", "update_index",
    "delete_index", "open_index", "close_index",
    "list_indices", "find_indices",

    # Document commands
    "index_document", "bulk_index", "get_document", "search_documents",
    "update_document", "delete_document", "bulk_delete",

    # Datastream commands
    "create_datastream", "list_datastreams", "get_datastream",
    "delete_datastream", "rollover_datastream",

    # Config commands
    "get_config_value", "set_config_value", "list_config", "init_config",

    # Utility commands
    "health", "templates", "aliases"
]
