"""
Configuration module.

This module provides functionality for loading and managing configuration.
"""

from elastro.config.loader import load_config, get_config, save_config, default_config
from elastro.config.defaults import DEFAULT_CONFIG

__all__ = ["load_config", "get_config", "save_config", "default_config", "DEFAULT_CONFIG"]
