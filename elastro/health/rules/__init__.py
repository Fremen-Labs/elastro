"""Custom health rules beyond native Elasticsearch indicators."""

from elastro.health.rules.jvm import jvm_pressure_findings

__all__ = ["jvm_pressure_findings"]