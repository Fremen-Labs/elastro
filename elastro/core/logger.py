"""
Logger configuration for Elastro.

This module provides a robust, colored logger with file rotation support.
LogLoom integration enriches every log record with code-structure metadata
(node_id, module, function, tags) from the build-time knowledge graph.
"""

import os
import sys
import json
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional
import colorlog

# Default configuration
DEFAULT_LOG_LEVEL = os.getenv("ELASTRO_LOG_LEVEL", "INFO")
LOG_FILE_PATH = os.getenv("ELASTRO_LOG_FILE", "elastro.log")
LOGLOOM_LOG_PATH = os.getenv("ELASTRO_LOGLOOM_FILE", "elastro-logloom.ndjson")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
COLOR_LOG_FORMAT = "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# ── LogLoom integration ──────────────────────────────────────────────────────
# Install once at module load time. Safe to call even if the graph doesn't exist.
_logloom_handler = None
try:
    from logloom.otel.bridge import LogLoomOTELHandler
    _logloom_handler = LogLoomOTELHandler()
    _logloom_handler.install()
except Exception:
    pass  # LogLoom not installed or graph not found — graceful degradation


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

        # LogLoom enrichment fields (injected by LogLoomOTELHandler.install())
        for attr in ("logloom_node_id", "logloom_module", "logloom_function",
                      "logloom_tags", "logloom_file", "logloom_line"):
            val = getattr(record, attr, None)
            if val is not None:
                entry[attr] = val

        return json.dumps(entry, default=str)


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
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "red,bg_white",
        },
    )
    console_handler.setFormatter(color_formatter)
    logger.addHandler(console_handler)

    # 2. File Handler (Rotating)
    try:
        # 10MB per file, max 5 backup files
        file_handler = RotatingFileHandler(
            LOG_FILE_PATH, maxBytes=10 * 1024 * 1024, backupCount=5
        )
        file_handler.setLevel(level)
        file_formatter = logging.Formatter(LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    except Exception:
        # Fallback if file logging fails (e.g. permissions)
        sys.stderr.write(f"Warning: Could not set up file logging to {LOG_FILE_PATH}\n")

    # 3. LogLoom JSON Handler — writes enriched NDJSON for Elastic ingestion
    if _logloom_handler is not None:
        try:
            logloom_file_handler = RotatingFileHandler(
                LOGLOOM_LOG_PATH, maxBytes=10 * 1024 * 1024, backupCount=3
            )
            logloom_file_handler.setLevel(level)
            logloom_file_handler.setFormatter(_LogLoomJSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S"))
            logger.addHandler(logloom_file_handler)
        except Exception:
            pass  # Non-fatal: LogLoom JSON logging is optional

    return logger

