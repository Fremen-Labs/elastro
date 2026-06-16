"""JSON formatter for health assessment reports."""

from __future__ import annotations

import json
from typing import Any, Dict

from elastro.health.models import AssessmentReport


def format_assessment_json(
    report: AssessmentReport,
    *,
    include_raw: bool = False,
) -> str:
    """Serialize an assessment report to indented JSON."""
    payload: Dict[str, Any] = report.model_dump(mode="json")
    if not include_raw:
        payload.pop("raw_health_report", None)
    return json.dumps(payload, indent=2, default=str)
