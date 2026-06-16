"""Health check and diagnostics utilities for Elasticsearch.

Backward-compatible facade; implementation lives in elastro.health.manager.
"""

from elastro.health.manager import HealthManager

__all__ = ["HealthManager"]
