"""Mapping explosion rule — warn when field counts approach index limits."""

from __future__ import annotations

from typing import List

from elastro.core.logger import get_logger
from elastro.health.mappings import DEFAULT_FIELD_WARN_RATIO
from elastro.health.models import Finding, FindingStatus, RemediationAction, RemediationSafety, Severity
from elastro.health.rules.engine import RuleContext

logger = get_logger(__name__)

DEFAULT_MAPPING_FIELD_WARN_RATIO = DEFAULT_FIELD_WARN_RATIO


def mapping_explosion_findings(
    ctx: RuleContext,
    *,
    warn_ratio: float = DEFAULT_MAPPING_FIELD_WARN_RATIO,
) -> List[Finding]:
    """Emit findings when mapped field counts approach total_fields limits."""
    indices = (ctx.collector_data.get("mappings") or {}).get("indices") or []
    if not indices:
        return []

    findings: List[Finding] = []
    for entry in indices:
        if not isinstance(entry, dict):
            continue
        index_name = str(entry.get("index", "")).strip()
        field_count = int(entry.get("field_count", 0))
        field_limit = int(entry.get("field_limit", 0))
        if not index_name or field_limit <= 0:
            continue

        ratio = field_count / field_limit
        if ratio < warn_ratio:
            continue

        severity = Severity.HIGH if ratio >= 0.95 else Severity.MEDIUM
        logger.debug(
            "Mapping explosion: index=%s fields=%s limit=%s ratio=%.2f",
            index_name,
            field_count,
            field_limit,
            ratio,
        )
        findings.append(
            Finding(
                id=f"mappings.explosion.{index_name}",
                category="mappings",
                title=f"Mapping field count high: {index_name}",
                status=FindingStatus.WARN,
                severity=severity,
                score_impact=10 if severity == Severity.HIGH else 5,
                summary=(
                    f"Index '{index_name}' maps {field_count} fields "
                    f"({int(ratio * 100)}% of limit {field_limit})."
                ),
                affected_resources=[index_name],
                source="rule",
                remediation=RemediationAction(
                    id="review_mapping",
                    label="Review index mapping",
                    command=f"elastro index get {index_name}",
                    safety=RemediationSafety.OBSERVE,
                ),
                metadata={
                    "field_count": field_count,
                    "field_limit": field_limit,
                    "field_ratio": round(ratio, 4),
                },
            )
        )

    return findings