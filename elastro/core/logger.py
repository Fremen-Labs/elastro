"""
Logger configuration for Elastro.

This module provides a robust, colored logger with file rotation support.
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional
import colorlog

# Default configuration
DEFAULT_LOG_LEVEL = os.getenv("ELASTRO_LOG_LEVEL", "INFO")
LOG_FILE_PATH = os.getenv("ELASTRO_LOG_FILE", "elastro.log")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
COLOR_LOG_FORMAT = "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def get_logger(name: str, log_level: Optional[str] = None) -> logging.Logger:
    """
    Get a configured logger instance.

    Args:
        name: Logger name (usually __name__)
        log_level: Optional log level override

    Returns:
        Configured logging.Logger instance
    """
    logger = logging.getLogger(name)
    
    # If logger is already configured, return it
    if logger.handlers:
        return logger

    level = log_level or DEFAULT_LOG_LEVEL
    logger.setLevel(level)

    # 1. Console Handler (Colored)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(level)
    
    color_formatter = colorlog.ColoredFormatter(
        COLOR_LOG_FORMAT,
        datefmt="%Y-%m-%d %H:%M:%S",
        reset=True,
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        }
    )
    console_handler.setFormatter(color_formatter)
    logger.addHandler(console_handler)

    # 2. File Handler (Rotating)
    try:
        # 10MB per file, max 5 backup files
        file_handler = RotatingFileHandler(
            LOG_FILE_PATH, maxBytes=10*1024*1024, backupCount=5
        )
        file_handler.setLevel(level)
        file_formatter = logging.Formatter(LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    except Exception:
        # Fallback if file logging fails (e.g. permissions)
        sys.stderr.write(f"Warning: Could not set up file logging to {LOG_FILE_PATH}\n")

    return logger
