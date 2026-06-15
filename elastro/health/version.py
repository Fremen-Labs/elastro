"""Elasticsearch version parsing and capability checks."""

from __future__ import annotations

from typing import Tuple


def parse_version(version: str) -> Tuple[int, int, int]:
    """Parse an Elasticsearch version string into (major, minor, patch)."""
    cleaned = version.split("-")[0]
    parts = cleaned.split(".")
    try:
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
        return major, minor, patch
    except ValueError:
        return 0, 0, 0


def supports_health_report(version: str) -> bool:
    """Return True when the cluster supports GET _health_report (8.7+)."""
    major, minor, _ = parse_version(version)
    return (major, minor) >= (8, 7)