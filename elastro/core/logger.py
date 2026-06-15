"""
Logger configuration for Elastro.

This module provides a robust, colored logger with file rotation support.
LogLoom integration enriches every log record with code-structure metadata
(node_id, module, function, tags) from the build-time knowledge graph.

Handlers are attached once to the ``elastro`` package logger; child loggers
use ``logging.getLogger(__name__)`` and propagate upward (FAANG/stdlib pattern).
"""

from __future__ import annotations

import json
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional

import colorlog

PACKAGE_LOGGER_NAME = "elastro"
DEFAULT_LOG_LEVEL = os.getenv("ELASTRO_LOG_LEVEL", "INFO")
LOG_FILE_PATH = os.getenv("ELASTRO_LOG_FILE", "elastro.log")
LOGLOOM_LOG_PATH = os.getenv("ELASTRO_LOGLOOM_FILE", "elastro-logloom.ndjson")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
COLOR_LOG_FORMAT = "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s"

_CONFIGURED = False

# ── LogLoom integration ──────────────────────────────────────────────────────
_logloom_handler = None
try:
    from logloom.otel.bridge import LogLoomOTELHandler

    _logloom_handler = LogLoomOTELHandler()
    _logloom_handler.install()
except Exception:
    pass


class _LogLoomJSONFormatter(logging.Formatter):
    """Formats log records as JSON with LogLoom enrichment fields."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }

        for attr in (
            "logloom_node_id",
            "logloom_module",
            "logloom_function",
            "logloom_tags",
            "logloom_file",
            "logloom_line",
        ):
            val = getattr(record, attr, None)
            if val is not None:
                entry[attr] = val

        return json.dumps(entry, default=str)


def _resolve_level(level: str) -> int:
    if isinstance(level, int):
        return level
    return getattr(logging, str(level).upper(), logging.INFO)


def configure_logging(log_level: Optional[str] = None) -> logging.Logger:
    """Configure package-level handlers once and return the root elastro logger."""
    global _CONFIGURED

    level_name = log_level or DEFAULT_LOG_LEVEL
    level = _resolve_level(level_name)
    package_logger = logging.getLogger(PACKAGE_LOGGER_NAME)
    package_logger.setLevel(level)

    if _CONFIGURED:
        package_logger.setLevel(level)
        for handler in package_logger.handlers:
            handler.setLevel(level)
        return package_logger

    package_logger.propagate = False

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(level)
    console_handler.setFormatter(
        colorlog.ColoredFormatter(
            COLOR_LOG_FORMAT,
            datefmt="%Y-%m-%d %H:%M:%S",
            reset=True,
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "red,bg_white",
            },
        )
    )
    package_logger.addHandler(console_handler)

    try:
        file_handler = RotatingFileHandler(
            LOG_FILE_PATH, maxBytes=10 * 1024 * 1024, backupCount=5
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(
            logging.Formatter(LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")
        )
        package_logger.addHandler(file_handler)
    except Exception:
        sys.stderr.write(
            f"Warning: Could not set up file logging to {LOG_FILE_PATH}\n"
        )

    if _logloom_handler is not None:
        try:
            logloom_file_handler = RotatingFileHandler(
                LOGLOOM_LOG_PATH, maxBytes=10 * 1024 * 1024, backupCount=3
            )
            logloom_file_handler.setLevel(level)
            logloom_file_handler.setFormatter(
                _LogLoomJSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S")
            )
            package_logger.addHandler(logloom_file_handler)
        except Exception:
            pass

    _CONFIGURED = True
    return package_logger


def get_logger(name: str, log_level: Optional[str] = None) -> logging.Logger:
    """
    Get a configured logger instance.

    Args:
        name: Logger name (usually __name__)
        log_level: Optional log level override for this logger

    Returns:
        Configured logging.Logger instance
    """
    configure_logging(log_level)
    logger = logging.getLogger(name)
    if name.startswith(f"{PACKAGE_LOGGER_NAME}.") and logger.handlers:
        logger.handlers.clear()
    if log_level is not None:
        logger.setLevel(_resolve_level(log_level))
    return logger