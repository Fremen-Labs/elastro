"""
Configuration loader module.

This module provides functionality for loading and managing configuration from
files and environment variables.
"""

import os
import yaml
import json
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from elastro.core.errors import ConfigurationError
from elastro.config.defaults import DEFAULT_CONFIG


# Load environment variables from .env file
load_dotenv()

# Global configuration object
_config = None


def load_config(config_path: Optional[str] = None, profile: str = "default") -> Dict[str, Any]:
    """
    Load configuration from file and environment variables.

    Args:
        config_path: Path to the configuration file (optional)
        profile: Configuration profile to use

    Returns:
        Dict containing configuration

    Raises:
        ConfigurationError: If configuration loading fails
    """
    global _config

    # Start with default configuration
    config = DEFAULT_CONFIG.copy()

    # Try to load configuration from file
    if config_path:
        file_config = _load_from_file(config_path)
        if file_config:
            # If profile exists, use it; otherwise use the entire config
            if profile in file_config:
                config = _merge_configs(config, file_config[profile])
            else:
                config = _merge_configs(config, file_config)
    else:
        # Look for config file in standard locations
        standard_locations = [
            os.path.join(os.getcwd(), "elastic.yaml"),
            os.path.join(os.getcwd(), "elastic.json"),
            os.path.expanduser("~/.elastic.yaml"),
            os.path.expanduser("~/.elastic.json"),
            os.path.expanduser("~/.elastic/config.yaml"),
        ]

        for loc in standard_locations:
            if os.path.exists(loc):
                file_config = _load_from_file(loc)
                if file_config:
                    # If profile exists, use it; otherwise use the entire config
                    if profile in file_config:
                        config = _merge_configs(config, file_config[profile])
                    else:
                        config = _merge_configs(config, file_config)
                break

    # Override with environment variables
    config = _load_from_env(config)

    # Validate the configuration
    _validate_config(config)

    # Store the loaded configuration
    _config = config

    return config


def get_config(profile: str = "default") -> Dict[str, Any]:
    """
    Get the current configuration.

    Args:
        profile: Configuration profile to use

    Returns:
        Dict containing configuration

    Raises:
        ConfigurationError: If configuration has not been loaded
    """
    global _config

    if _config is None:
        # Load configuration if not already loaded
        return load_config(profile=profile)

    return _config


def _load_from_file(file_path: str) -> Dict[str, Any]:
    """
    Load configuration from a file.

    Args:
        file_path: Path to the configuration file

    Returns:
        Dict containing configuration from file

    Raises:
        ConfigurationError: If file loading fails
    """
    try:
        file_path = Path(file_path)

        if not file_path.exists():
            raise ConfigurationError(f"Configuration file {file_path} does not exist")

        if file_path.suffix == ".yaml" or file_path.suffix == ".yml":
            with open(file_path, "r") as f:
                return yaml.safe_load(f)
        elif file_path.suffix == ".json":
            with open(file_path, "r") as f:
                return json.load(f)
        else:
            raise ConfigurationError(f"Unsupported configuration file format: {file_path.suffix}")
    except Exception as e:
        raise ConfigurationError(f"Failed to load configuration from {file_path}: {str(e)}")


def _load_from_env(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Override configuration with environment variables.

    Environment variables are expected to be in the format:
    ELASTIC_SECTION_KEY=value

    Args:
        config: Current configuration

    Returns:
        Dict containing updated configuration
    """
    prefix = "ELASTIC_"

    for env_var, value in os.environ.items():
        if env_var.startswith(prefix):
            # Remove prefix and split into sections
            path = env_var[len(prefix):].lower().split("_")

            # Navigate to the correct config section
            current = config
            for section in path[:-1]:
                if section not in current:
                    current[section] = {}
                current = current[section]

            # Set the value (convert to appropriate type)
            key = path[-1]
            if value.lower() == "true":
                current[key] = True
            elif value.lower() == "false":
                current[key] = False
            elif value.isdigit():
                current[key] = int(value)
            elif value.replace(".", "", 1).isdigit() and value.count(".") == 1:
                current[key] = float(value)
            else:
                current[key] = value

    return config


def _merge_configs(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge two configuration dictionaries.

    Args:
        base: Base configuration
        override: Override configuration

    Returns:
        Dict containing merged configuration
    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recursively merge dictionaries
            result[key] = _merge_configs(result[key], value)
        else:
            # Override or add value
            result[key] = value

    return result


def _validate_config(config: Dict[str, Any]) -> None:
    """
    Validate the configuration.

    Args:
        config: Configuration to validate

    Raises:
        ConfigurationError: If configuration is invalid
    """
    # Validate elasticsearch section
    if "elasticsearch" not in config:
        raise ConfigurationError("Missing 'elasticsearch' section in configuration")

    es_config = config["elasticsearch"]

    # Validate hosts
    if "hosts" not in es_config or not es_config["hosts"]:
        raise ConfigurationError("Missing or empty 'hosts' in elasticsearch configuration")

    # Validate authentication if provided
    if "auth" in es_config and es_config["auth"]:
        auth = es_config["auth"]

        # Check auth type
        if "type" in auth and auth["type"]:
            auth_type = auth["type"]
            if auth_type not in [None, "api_key", "basic", "cloud"]:
                raise ConfigurationError(f"Invalid authentication type: {auth_type}")

            # Validate required auth parameters based on type
            if auth_type == "api_key" and "api_key" not in auth:
                raise ConfigurationError("Missing 'api_key' for API key authentication")
            elif auth_type == "basic" and ("username" not in auth or "password" not in auth):
                raise ConfigurationError("Missing 'username' or 'password' for basic authentication")
            elif auth_type == "cloud" and "cloud_id" not in auth:
                raise ConfigurationError("Missing 'cloud_id' for cloud authentication")

    # Validate timeout
    if "timeout" in es_config and not isinstance(es_config["timeout"], (int, float)):
        raise ConfigurationError("'timeout' must be a number")

    # Validate max_retries
    if "max_retries" in es_config and not isinstance(es_config["max_retries"], int):
        raise ConfigurationError("'max_retries' must be an integer")

    # Validate index settings
    if "index" in config and "default_settings" in config["index"]:
        settings = config["index"]["default_settings"]
        if not isinstance(settings, dict):
            raise ConfigurationError("'default_settings' in index section must be a dictionary")

    # Validate logging level
    if "logging" in config and "level" in config["logging"]:
        level = config["logging"]["level"]
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if level not in valid_levels:
            raise ConfigurationError(f"Invalid logging level: {level}. Must be one of {valid_levels}")


def save_config(config: Dict[str, Any], path: Optional[str] = None, profile: str = "default") -> None:
    """
    Save configuration to a file.

    Args:
        config: Configuration to save
        path: Path to the configuration file (optional)
        profile: Configuration profile to use (not used in simple save for now, assumes config is full structure)
    """
    # Use default path if not provided
    if not path:
        path = os.path.expanduser("~/.elastic/config.yaml")

    path_obj = Path(path)
    
    # Create directory if it doesn't exist
    if not path_obj.parent.exists():
        path_obj.parent.mkdir(parents=True)

    try:
        with open(path_obj, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
    except Exception as e:
        raise ConfigurationError(f"Failed to save configuration to {path}: {str(e)}")


def default_config() -> Dict[str, Any]:
    """
    Get the default configuration.

    Returns:
        Dict containing default configuration
    """
    return DEFAULT_CONFIG.copy()
