"""
Custom exceptions for the Elasticsearch module.

This module defines custom exceptions for different categories of errors
that can occur when interacting with Elasticsearch.
"""


class ElasticModuleError(Exception):
    """Base exception class for all elastro errors."""
    pass


class ConnectionError(ElasticModuleError):
    """Raised when there's a problem connecting to Elasticsearch."""
    pass


class AuthenticationError(ElasticModuleError):
    """Raised when authentication to Elasticsearch fails."""
    pass


class OperationError(ElasticModuleError):
    """Raised when an Elasticsearch operation fails."""
    pass


class ValidationError(ElasticModuleError):
    """Raised when input validation fails."""
    pass


class ConfigurationError(ElasticModuleError):
    """Raised when there's an issue with the configuration."""
    pass


class ElasticIndexError(OperationError):
    """Raised when an index operation fails."""
    pass


class DocumentError(OperationError):
    """Raised when a document operation fails."""
    pass


class DatastreamError(OperationError):
    """Raised when a datastream operation fails."""
    pass
