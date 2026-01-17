"""
Unit tests for the elastro.core.errors module.

Tests that custom exceptions are properly defined and behave as expected.
"""

import pytest
from elastro.core import errors


class TestErrorClasses:
    """Test suite for custom error classes."""

    def test_base_error_class(self):
        """Test ElasticModuleError base class."""
        error = errors.ElasticModuleError("Test error message")
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)

    def test_connection_error(self):
        """Test ConnectionError class."""
        error = errors.ConnectionError("Connection failed")
        assert str(error) == "Connection failed"
        assert isinstance(error, errors.ElasticModuleError)
        assert isinstance(error, Exception)

    def test_authentication_error(self):
        """Test AuthenticationError class."""
        error = errors.AuthenticationError("Authentication failed")
        assert str(error) == "Authentication failed"
        assert isinstance(error, errors.ElasticModuleError)
        assert isinstance(error, Exception)

    def test_operation_error(self):
        """Test OperationError class."""
        error = errors.OperationError("Operation failed")
        assert str(error) == "Operation failed"
        assert isinstance(error, errors.ElasticModuleError)
        assert isinstance(error, Exception)

    def test_validation_error(self):
        """Test ValidationError class."""
        error = errors.ValidationError("Validation failed")
        assert str(error) == "Validation failed"
        assert isinstance(error, errors.ElasticModuleError)
        assert isinstance(error, Exception)

    def test_configuration_error(self):
        """Test ConfigurationError class."""
        error = errors.ConfigurationError("Configuration error")
        assert str(error) == "Configuration error"
        assert isinstance(error, errors.ElasticModuleError)
        assert isinstance(error, Exception)

    def test_index_error(self):
        """Test IndexError class."""
        error = errors.IndexError("Index operation failed")
        assert str(error) == "Index operation failed"
        assert isinstance(error, errors.OperationError)
        assert isinstance(error, errors.ElasticModuleError)
        assert isinstance(error, Exception)

    def test_document_error(self):
        """Test DocumentError class."""
        error = errors.DocumentError("Document operation failed")
        assert str(error) == "Document operation failed"
        assert isinstance(error, errors.OperationError)
        assert isinstance(error, errors.ElasticModuleError)
        assert isinstance(error, Exception)

    def test_datastream_error(self):
        """Test DatastreamError class."""
        error = errors.DatastreamError("Datastream operation failed")
        assert str(error) == "Datastream operation failed"
        assert isinstance(error, errors.OperationError)
        assert isinstance(error, errors.ElasticModuleError)
        assert isinstance(error, Exception)

    def test_exception_hierarchy(self):
        """Test that exception hierarchy works correctly with try/except."""
        try:
            raise errors.DocumentError("Test document error")
        except errors.IndexError:
            pytest.fail("DocumentError was caught as IndexError")
        except errors.DocumentError:
            # This is the expected path
            pass
        except errors.OperationError:
            pytest.fail("DocumentError should be caught before OperationError")
        except errors.ElasticModuleError:
            pytest.fail("DocumentError should be caught before ElasticModuleError")
        except Exception:
            pytest.fail("DocumentError should be caught before general Exception")

    def test_exception_parent_catches_child(self):
        """Test that parent exceptions catch child exceptions."""
        try:
            raise errors.IndexError("Test index error")
        except errors.OperationError:
            # This is the expected path
            pass
        except Exception:
            pytest.fail("IndexError should be caught by OperationError")

        try:
            raise errors.DocumentError("Test document error")
        except errors.ElasticModuleError:
            # This is the expected path
            pass
        except Exception:
            pytest.fail("DocumentError should be caught by ElasticModuleError")
