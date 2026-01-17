"""
Unit tests for the loader module.
"""

import os
import yaml
import json
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

from elastro.config import loader
from elastro.config.defaults import DEFAULT_CONFIG
from elastro.core.errors import ConfigurationError


@pytest.fixture
def reset_config():
    """Reset the global config before and after each test."""
    loader._config = None
    yield
    loader._config = None


@pytest.fixture
def sample_config():
    """Sample config for testing."""
    return {
        "elasticsearch": {
            "hosts": ["http://test-host:9200"],
            "timeout": 60,
            "max_retries": 5,
            "auth": {
                "type": "basic",
                "username": "test_user",
                "password": "test_password",
            },
        },
        "index": {"default_settings": {"number_of_shards": 2, "number_of_replicas": 1}},
        "logging": {"level": "DEBUG"},
    }


@pytest.fixture
def yaml_config_content(sample_config):
    """YAML config content."""
    return yaml.dump(sample_config)


@pytest.fixture
def json_config_content(sample_config):
    """JSON config content."""
    return json.dumps(sample_config)


@pytest.fixture
def profile_config():
    """Config with profiles for testing."""
    return {
        "default": {"elasticsearch": {"hosts": ["http://default-host:9200"]}},
        "production": {
            "elasticsearch": {"hosts": ["http://prod-host:9200"], "timeout": 120}
        },
    }


class TestLoadFromFile:
    """Tests for _load_from_file function."""

    def test_load_yaml_file(self, yaml_config_content, sample_config):
        """Test loading YAML config file."""
        with patch("builtins.open", mock_open(read_data=yaml_config_content)):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.suffix", ".yaml"):
                    config = loader._load_from_file("config.yaml")
                    assert config == sample_config

    def test_load_json_file(self, json_config_content, sample_config):
        """Test loading JSON config file."""
        with patch("builtins.open", mock_open(read_data=json_config_content)):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.suffix", ".json"):
                    config = loader._load_from_file("config.json")
                    assert config == sample_config

    def test_file_not_exists(self):
        """Test error when file does not exist."""
        with patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(ConfigurationError, match="does not exist"):
                loader._load_from_file("nonexistent.yaml")

    def test_unsupported_format(self):
        """Test error for unsupported file format."""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.suffix", ".txt"):
                with pytest.raises(
                    ConfigurationError, match="Unsupported configuration file format"
                ):
                    loader._load_from_file("config.txt")

    def test_file_loading_error(self):
        """Test error handling during file loading."""
        with patch("builtins.open", mock_open()):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.suffix", ".yaml"):
                    with patch("yaml.safe_load", side_effect=Exception("Test error")):
                        with pytest.raises(
                            ConfigurationError, match="Failed to load configuration"
                        ):
                            loader._load_from_file("config.yaml")


class TestLoadFromEnv:
    """Tests for _load_from_env function."""

    def test_env_variables_override(self):
        """Test environment variables override config values."""
        config = {"elasticsearch": {"hosts": ["http://localhost:9200"], "timeout": 30}}

        with patch.dict(
            os.environ,
            {
                "ELASTIC_ELASTICSEARCH_HOSTS": "http://env-host:9200",
                "ELASTIC_ELASTICSEARCH_TIMEOUT": "60",
            },
        ):
            result = loader._load_from_env(config)
            assert result["elasticsearch"]["hosts"] == "http://env-host:9200"
            assert result["elasticsearch"]["timeout"] == 60

    def test_env_boolean_conversion(self):
        """Test environment boolean values are properly converted."""
        config = {"feature": {"enabled": False}}

        with patch.dict(os.environ, {"ELASTIC_FEATURE_ENABLED": "true"}):
            result = loader._load_from_env(config)
            assert result["feature"]["enabled"] is True

    def test_env_numeric_conversion(self):
        """Test environment numeric values are properly converted."""
        config = {"values": {}}

        with patch.dict(
            os.environ, {"ELASTIC_VALUES_INTEGER": "42", "ELASTIC_VALUES_FLOAT": "3.14"}
        ):
            result = loader._load_from_env(config)
            assert result["values"]["integer"] == 42
            assert result["values"]["float"] == 3.14

    def test_env_nested_creation(self):
        """Test environment variables create nested structure."""
        config = {}

        with patch.dict(os.environ, {"ELASTIC_SECTION_SUBSECTION_KEY": "value"}):
            result = loader._load_from_env(config)
            assert result["section"]["subsection"]["key"] == "value"


class TestMergeConfigs:
    """Tests for _merge_configs function."""

    def test_merge_simple_values(self):
        """Test merging simple values."""
        base = {"key1": "value1", "key2": "value2"}
        override = {"key2": "new_value", "key3": "value3"}

        result = loader._merge_configs(base, override)
        assert result == {"key1": "value1", "key2": "new_value", "key3": "value3"}

    def test_merge_nested_dicts(self):
        """Test merging nested dictionaries."""
        base = {"section": {"key1": "value1", "key2": "value2"}}
        override = {"section": {"key2": "new_value", "key3": "value3"}}

        result = loader._merge_configs(base, override)
        assert result == {
            "section": {"key1": "value1", "key2": "new_value", "key3": "value3"}
        }

    def test_merge_with_new_section(self):
        """Test merging with new section."""
        base = {"section1": {"key": "value"}}
        override = {"section2": {"key": "value"}}

        result = loader._merge_configs(base, override)
        assert result == {"section1": {"key": "value"}, "section2": {"key": "value"}}

    def test_merge_different_types(self):
        """Test merging when types are different."""
        base = {"key": {"nested": "value"}}
        override = {"key": "simple_value"}

        result = loader._merge_configs(base, override)
        assert result == {"key": "simple_value"}


class TestValidateConfig:
    """Tests for _validate_config function."""

    def test_valid_config(self):
        """Test validation of a valid config."""
        config = {"elasticsearch": {"hosts": ["http://localhost:9200"]}}

        # Should not raise an exception
        loader._validate_config(config)

    def test_missing_elasticsearch_section(self):
        """Test validation with missing elasticsearch section."""
        config = {"some_section": {}}

        with pytest.raises(ConfigurationError, match="Missing 'elasticsearch' section"):
            loader._validate_config(config)

    def test_missing_hosts(self):
        """Test validation with missing hosts."""
        config = {"elasticsearch": {}}

        with pytest.raises(ConfigurationError, match="Missing or empty 'hosts'"):
            loader._validate_config(config)

    def test_empty_hosts(self):
        """Test validation with empty hosts list."""
        config = {"elasticsearch": {"hosts": []}}

        with pytest.raises(ConfigurationError, match="Missing or empty 'hosts'"):
            loader._validate_config(config)

    def test_invalid_auth_type(self):
        """Test validation with invalid auth type."""
        config = {
            "elasticsearch": {
                "hosts": ["http://localhost:9200"],
                "auth": {"type": "invalid"},
            }
        }

        with pytest.raises(ConfigurationError, match="Invalid authentication type"):
            loader._validate_config(config)

    def test_missing_api_key(self):
        """Test validation with missing API key."""
        config = {
            "elasticsearch": {
                "hosts": ["http://localhost:9200"],
                "auth": {"type": "api_key"},
            }
        }

        with pytest.raises(ConfigurationError, match="Missing 'api_key'"):
            loader._validate_config(config)

    def test_missing_basic_auth_credentials(self):
        """Test validation with missing basic auth credentials."""
        config = {
            "elasticsearch": {
                "hosts": ["http://localhost:9200"],
                "auth": {"type": "basic"},
            }
        }

        with pytest.raises(
            ConfigurationError, match="Missing 'username' or 'password'"
        ):
            loader._validate_config(config)

    def test_missing_cloud_id(self):
        """Test validation with missing cloud ID."""
        config = {
            "elasticsearch": {
                "hosts": ["http://localhost:9200"],
                "auth": {"type": "cloud"},
            }
        }

        with pytest.raises(ConfigurationError, match="Missing 'cloud_id'"):
            loader._validate_config(config)

    def test_invalid_timeout(self):
        """Test validation with invalid timeout."""
        config = {
            "elasticsearch": {"hosts": ["http://localhost:9200"], "timeout": "invalid"}
        }

        with pytest.raises(ConfigurationError, match="'timeout' must be a number"):
            loader._validate_config(config)

    def test_invalid_max_retries(self):
        """Test validation with invalid max_retries."""
        config = {
            "elasticsearch": {"hosts": ["http://localhost:9200"], "max_retries": 3.5}
        }

        with pytest.raises(
            ConfigurationError, match="'max_retries' must be an integer"
        ):
            loader._validate_config(config)

    def test_invalid_index_settings(self):
        """Test validation with invalid index settings."""
        config = {
            "elasticsearch": {"hosts": ["http://localhost:9200"]},
            "index": {"default_settings": "not a dict"},
        }

        with pytest.raises(
            ConfigurationError,
            match="'default_settings' in index section must be a dictionary",
        ):
            loader._validate_config(config)

    def test_invalid_logging_level(self):
        """Test validation with invalid logging level."""
        config = {
            "elasticsearch": {"hosts": ["http://localhost:9200"]},
            "logging": {"level": "INVALID_LEVEL"},
        }

        with pytest.raises(ConfigurationError, match="Invalid logging level"):
            loader._validate_config(config)


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_with_explicit_config_path(self, reset_config, sample_config):
        """Test loading config with explicit config path."""
        with patch(
            "elastro.config.loader._load_from_file", return_value=sample_config
        ) as mock_load:
            with patch(
                "elastro.config.loader._load_from_env", return_value=sample_config
            ):
                config = loader.load_config("explicit_path.yaml")
                assert config == sample_config
                mock_load.assert_called_once_with("explicit_path.yaml")

    def test_load_with_profile(self, reset_config, profile_config):
        """Test loading config with profile."""
        with patch(
            "elastro.config.loader._load_from_file", return_value=profile_config
        ) as mock_load:
            with patch(
                "elastro.config.loader._load_from_env",
                return_value=profile_config["production"],
            ):
                config = loader.load_config("profile_config.yaml", "production")
                assert config["elasticsearch"]["hosts"] == ["http://prod-host:9200"]
                mock_load.assert_called_once_with("profile_config.yaml")

    def test_load_from_standard_locations(self, reset_config, sample_config):
        """Test loading config from standard locations."""
        with patch("os.path.exists", return_value=True):
            with patch(
                "elastro.config.loader._load_from_file", return_value=sample_config
            ) as mock_load:
                with patch(
                    "elastro.config.loader._load_from_env", return_value=sample_config
                ):
                    config = loader.load_config()
                    assert config == sample_config
                    # It should try to load from the first standard location (CWD/elastic.yaml)
                    mock_load.assert_called_once()

    def test_global_config_storage(self, reset_config, sample_config):
        """Test global config storage."""
        with patch("elastro.config.loader._load_from_file", return_value=sample_config):
            with patch(
                "elastro.config.loader._load_from_env", return_value=sample_config
            ):
                # First load should set the global config
                config1 = loader.load_config()
                assert config1 == sample_config
                assert loader._config == sample_config


class TestGetConfig:
    """Tests for get_config function."""

    def test_get_config_when_loaded(self, reset_config, sample_config):
        """Test getting config when already loaded."""
        loader._config = sample_config
        config = loader.get_config()
        assert config == sample_config

    def test_get_config_load_if_not_loaded(self, reset_config, sample_config):
        """Test getting config loads it if not already loaded."""
        with patch(
            "elastro.config.loader.load_config", return_value=sample_config
        ) as mock_load:
            config = loader.get_config()
            assert config == sample_config
            mock_load.assert_called_once()
