"""Dispatch assessment report formatting by output type."""

from __future__ import annotations

from typing import Optional

from elastro.health.formatters.json_fmt import format_assessment_json
from elastro.health.formatters.table import format_assessment_table
from elastro.health.formatters.yaml_fmt import format_assessment_yaml
from elastro.health.models import AssessmentReport


def render_assessment(
    report: AssessmentReport,
    output_format: str,
    *,
    include_raw: bool = False,
    show_detail: bool = False,
    detail_finding: Optional[str] = None,
) -> str:
    if output_format == "table":
        return format_assessment_table(
            report,
            show_detail=show_detail,
            detail_finding=detail_finding,
        )
    if output_format == "yaml":
        return format_assessment_yaml(report, include_raw=include_raw)
    return format_assessment_json(report, include_raw=include_raw)
