"""
Default configuration values.

This module defines the default configuration values used by the Elasticsearch
module.
"""

# Default connection settings
DEFAULT_HOSTS = ["http://localhost:9200"]
DEFAULT_TIMEOUT = 30
DEFAULT_RETRY_ON_TIMEOUT = True
DEFAULT_MAX_RETRIES = 3

# Default index settings
DEFAULT_INDEX_SETTINGS = {
    "number_of_shards": 1,
    "number_of_replicas": 1,
    "refresh_interval": "1s",
}

# Default document settings
DEFAULT_DOCUMENT_REFRESH = False

# Default datastream settings
DEFAULT_DATASTREAM_SETTINGS = {"retention": {"max_age": "30d"}}

# Default CLI settings
DEFAULT_CLI_OUTPUT_FORMAT = "json"
DEFAULT_CLI_VERBOSE = False

# Complete default configuration
DEFAULT_CONFIG = {
    "elasticsearch": {
        "hosts": DEFAULT_HOSTS,
        "timeout": DEFAULT_TIMEOUT,
        "retry_on_timeout": DEFAULT_RETRY_ON_TIMEOUT,
        "max_retries": DEFAULT_MAX_RETRIES,
        "auth": {
            "type": None,  # "api_key", "basic"
            "username": None,
            "password": None,
            "api_key": None,
        },
    },
    "index": {"default_settings": DEFAULT_INDEX_SETTINGS},
    "document": {"default_refresh": DEFAULT_DOCUMENT_REFRESH},
    "datastream": {"default_settings": DEFAULT_DATASTREAM_SETTINGS},
    "cli": {"output_format": DEFAULT_CLI_OUTPUT_FORMAT, "verbose": DEFAULT_CLI_VERBOSE},
    "logging": {
        "level": "INFO",
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    },
}
