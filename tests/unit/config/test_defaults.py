"""
Unit tests for the defaults module.
"""

import pytest
from elastro.config import defaults


def test_default_hosts_exists():
    """Test that DEFAULT_HOSTS is defined and is a list of strings."""
    assert hasattr(defaults, "DEFAULT_HOSTS")
    assert isinstance(defaults.DEFAULT_HOSTS, list)
    assert all(isinstance(host, str) for host in defaults.DEFAULT_HOSTS)
    assert len(defaults.DEFAULT_HOSTS) > 0
    assert defaults.DEFAULT_HOSTS == ["http://localhost:9200"]


def test_default_timeout_exists():
    """Test that DEFAULT_TIMEOUT is defined and is a valid integer."""
    assert hasattr(defaults, "DEFAULT_TIMEOUT")
    assert isinstance(defaults.DEFAULT_TIMEOUT, int)
    assert defaults.DEFAULT_TIMEOUT == 30


def test_default_retry_on_timeout_exists():
    """Test that DEFAULT_RETRY_ON_TIMEOUT is defined and is a boolean."""
    assert hasattr(defaults, "DEFAULT_RETRY_ON_TIMEOUT")
    assert isinstance(defaults.DEFAULT_RETRY_ON_TIMEOUT, bool)
    assert defaults.DEFAULT_RETRY_ON_TIMEOUT is True


def test_default_max_retries_exists():
    """Test that DEFAULT_MAX_RETRIES is defined and is a valid integer."""
    assert hasattr(defaults, "DEFAULT_MAX_RETRIES")
    assert isinstance(defaults.DEFAULT_MAX_RETRIES, int)
    assert defaults.DEFAULT_MAX_RETRIES == 3


def test_default_index_settings_exists():
    """Test that DEFAULT_INDEX_SETTINGS is defined and has the expected structure."""
    assert hasattr(defaults, "DEFAULT_INDEX_SETTINGS")
    assert isinstance(defaults.DEFAULT_INDEX_SETTINGS, dict)

    # Check required keys
    expected_keys = ["number_of_shards", "number_of_replicas", "refresh_interval"]
    for key in expected_keys:
        assert key in defaults.DEFAULT_INDEX_SETTINGS

    # Check values
    assert defaults.DEFAULT_INDEX_SETTINGS["number_of_shards"] == 1
    assert defaults.DEFAULT_INDEX_SETTINGS["number_of_replicas"] == 1
    assert defaults.DEFAULT_INDEX_SETTINGS["refresh_interval"] == "1s"


def test_default_document_refresh_exists():
    """Test that DEFAULT_DOCUMENT_REFRESH is defined and is a boolean."""
    assert hasattr(defaults, "DEFAULT_DOCUMENT_REFRESH")
    assert isinstance(defaults.DEFAULT_DOCUMENT_REFRESH, bool)
    assert defaults.DEFAULT_DOCUMENT_REFRESH is False


def test_default_datastream_settings_exists():
    """Test that DEFAULT_DATASTREAM_SETTINGS is defined and has the expected structure."""
    assert hasattr(defaults, "DEFAULT_DATASTREAM_SETTINGS")
    assert isinstance(defaults.DEFAULT_DATASTREAM_SETTINGS, dict)

    # Check required keys and nested structure
    assert "retention" in defaults.DEFAULT_DATASTREAM_SETTINGS
    assert isinstance(defaults.DEFAULT_DATASTREAM_SETTINGS["retention"], dict)
    assert "max_age" in defaults.DEFAULT_DATASTREAM_SETTINGS["retention"]

    # Check values
    assert defaults.DEFAULT_DATASTREAM_SETTINGS["retention"]["max_age"] == "30d"


def test_default_cli_output_format_exists():
    """Test that DEFAULT_CLI_OUTPUT_FORMAT is defined and is a string."""
    assert hasattr(defaults, "DEFAULT_CLI_OUTPUT_FORMAT")
    assert isinstance(defaults.DEFAULT_CLI_OUTPUT_FORMAT, str)
    assert defaults.DEFAULT_CLI_OUTPUT_FORMAT == "json"


def test_default_cli_verbose_exists():
    """Test that DEFAULT_CLI_VERBOSE is defined and is a boolean."""
    assert hasattr(defaults, "DEFAULT_CLI_VERBOSE")
    assert isinstance(defaults.DEFAULT_CLI_VERBOSE, bool)
    assert defaults.DEFAULT_CLI_VERBOSE is False


def test_default_config_exists():
    """Test that DEFAULT_CONFIG is defined and has the expected structure."""
    assert hasattr(defaults, "DEFAULT_CONFIG")
    assert isinstance(defaults.DEFAULT_CONFIG, dict)

    # Check top-level keys
    expected_top_level_keys = [
        "elasticsearch",
        "index",
        "document",
        "datastream",
        "cli",
        "logging",
    ]
    for key in expected_top_level_keys:
        assert key in defaults.DEFAULT_CONFIG

    # Check elasticsearch section
    es_config = defaults.DEFAULT_CONFIG["elasticsearch"]
    assert "hosts" in es_config
    assert es_config["hosts"] == defaults.DEFAULT_HOSTS
    assert "timeout" in es_config
    assert es_config["timeout"] == defaults.DEFAULT_TIMEOUT
    assert "retry_on_timeout" in es_config
    assert es_config["retry_on_timeout"] == defaults.DEFAULT_RETRY_ON_TIMEOUT
    assert "max_retries" in es_config
    assert es_config["max_retries"] == defaults.DEFAULT_MAX_RETRIES
    assert "auth" in es_config
    assert isinstance(es_config["auth"], dict)

    # Check index section
    assert "default_settings" in defaults.DEFAULT_CONFIG["index"]
    assert (
        defaults.DEFAULT_CONFIG["index"]["default_settings"]
        == defaults.DEFAULT_INDEX_SETTINGS
    )

    # Check document section
    assert "default_refresh" in defaults.DEFAULT_CONFIG["document"]
    assert (
        defaults.DEFAULT_CONFIG["document"]["default_refresh"]
        == defaults.DEFAULT_DOCUMENT_REFRESH
    )

    # Check datastream section
    assert "default_settings" in defaults.DEFAULT_CONFIG["datastream"]
    assert (
        defaults.DEFAULT_CONFIG["datastream"]["default_settings"]
        == defaults.DEFAULT_DATASTREAM_SETTINGS
    )

    # Check cli section
    assert "output_format" in defaults.DEFAULT_CONFIG["cli"]
    assert (
        defaults.DEFAULT_CONFIG["cli"]["output_format"]
        == defaults.DEFAULT_CLI_OUTPUT_FORMAT
    )
    assert "verbose" in defaults.DEFAULT_CONFIG["cli"]
    assert defaults.DEFAULT_CONFIG["cli"]["verbose"] == defaults.DEFAULT_CLI_VERBOSE

    # Check logging section
    assert "level" in defaults.DEFAULT_CONFIG["logging"]
    assert defaults.DEFAULT_CONFIG["logging"]["level"] == "INFO"
    assert "format" in defaults.DEFAULT_CONFIG["logging"]
    assert (
        defaults.DEFAULT_CONFIG["logging"]["format"]
        == "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
