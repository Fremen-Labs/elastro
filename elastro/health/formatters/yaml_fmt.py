"""YAML formatter for health assessment reports."""

from __future__ import annotations

import yaml

from elastro.health.models import AssessmentReport


def format_assessment_yaml(
    report: AssessmentReport,
    *,
    include_raw: bool = False,
) -> str:
    """Serialize an assessment report to YAML."""
    payload = report.model_dump(mode="json")
    if not include_raw:
        payload.pop("raw_health_report", None)
    return yaml.dump(payload, default_flow_style=False, sort_keys=False)