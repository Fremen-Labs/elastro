"""
ES|QL fluent query builder and renderer.

Provides a Pythonic, pipe-based API for constructing ES|QL queries
that mirrors the native ES|QL syntax while offering compile-time
safety and composability.
"""

from elastro.core.esql.builder import ESQLQuery

__all__ = ["ESQLQuery"]
