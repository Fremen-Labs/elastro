"""Unit tests for elastro logging configuration."""

import logging

import pytest

from elastro.core import logger as logger_module


@pytest.fixture(autouse=True)
def reset_logger_state(monkeypatch):
    """Isolate logger configuration between tests."""
    monkeypatch.setattr(logger_module, "_CONFIGURED", False)
    package_logger = logging.getLogger(logger_module.PACKAGE_LOGGER_NAME)
    package_logger.handlers.clear()
    package_logger.propagate = True
    yield
    package_logger.handlers.clear()
    package_logger.propagate = True
    monkeypatch.setattr(logger_module, "_CONFIGURED", False)


class TestLoggerConfiguration:
    def test_configure_logging_attaches_handlers_once(self):
        root = logger_module.configure_logging("INFO")
        assert root.handlers
        handler_count = len(root.handlers)

        again = logger_module.configure_logging("DEBUG")
        assert again is root
        assert len(root.handlers) == handler_count

    def test_child_logger_propagates_without_own_handlers(self):
        logger_module.configure_logging("INFO")
        child = logger_module.get_logger("elastro.health.assessor")
        assert not child.handlers

    def test_get_logger_respects_level_override(self):
        logger_module.configure_logging("INFO")
        child = logger_module.get_logger("elastro.test.module", log_level="DEBUG")
        assert child.level == logging.DEBUG
