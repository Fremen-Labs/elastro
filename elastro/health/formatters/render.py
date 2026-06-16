"""Dispatch assessment report formatting by output type."""

from __future__ import annotations

from elastro.health.formatters.json_fmt import format_assessment_json
from elastro.health.formatters.table import format_assessment_table
from elastro.health.formatters.yaml_fmt import format_assessment_yaml
from elastro.health.models import AssessmentReport


def render_assessment(
    report: AssessmentReport,
    output_format: str,
    *,
    include_raw: bool = False,
) -> str:
    if output_format == "table":
        return format_assessment_table(report)
    if output_format == "yaml":
        return format_assessment_yaml(report, include_raw=include_raw)
    return format_assessment_json(report, include_raw=include_raw)