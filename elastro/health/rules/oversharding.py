"""Oversharding and undersharding rules based on shard size thresholds."""

from __future__ import annotations

from typing import List

from elastro.core.logger import get_logger
from elastro.health.finding_guides.oversharding import build_oversharding_guide
from elastro.health.models import (
    Finding,
    FindingStatus,
    RemediationAction,
    RemediationSafety,
    Severity,
)
from elastro.health.rules.engine import RuleContext
from elastro.health.shards import (
    DEFAULT_OVERSHARD_THRESHOLD_MB,
    DEFAULT_UNDERSHARD_THRESHOLD_GB,
    format_bytes,
)

logger = get_logger(__name__)


def oversharding_findings(ctx: RuleContext) -> List[Finding]:
    """Emit findings when shard sizes fall outside recommended bounds."""
    analysis = (ctx.collector_data.get("shards") or {}).get("analysis") or {}
    if not analysis:
        return []

    findings: List[Finding] = []
    oversharded = int(analysis.get("oversharded_count", 0))
    undersharded = int(analysis.get("undersharded_count", 0))
    avg_bytes = float(analysis.get("avg_bytes", 0))

    if oversharded > 0:
        threshold = int(
            analysis.get(
                "overshard_threshold_bytes",
                int(DEFAULT_OVERSHARD_THRESHOLD_MB * 1024 * 1024),
            )
        )
        logger.debug("Oversharding rule: count=%s threshold=%s", oversharded, threshold)
        detail, guide_metadata, affected = build_oversharding_guide(
            analysis,
            es_version=ctx.es_version,
        )
        findings.append(
            Finding(
                id="shards.oversharded",
                category="shards",
                title="Oversharded indices detected",
                status=FindingStatus.WARN,
                severity=Severity.MEDIUM,
                score_impact=min(oversharded, 10),
                summary=(
                    f"{oversharded} shard(s) are smaller than "
                    f"{format_bytes(threshold)} (OVERSHARDED)."
                ),
                detail=detail,
                affected_resources=affected,
                source="rule",
                remediation=RemediationAction(
                    id="analyze_shards",
                    label="Analyze oversharded shards",
                    command="elastro health shards --analyze -o table",
                    safety=RemediationSafety.OBSERVE,
                ),
                metadata={
                    "oversharded_count": oversharded,
                    "threshold_bytes": threshold,
                    "avg_bytes": avg_bytes,
                    **guide_metadata,
                },
            )
        )

    if undersharded > 0:
        threshold = int(
            analysis.get(
                "undershard_threshold_bytes",
                int(DEFAULT_UNDERSHARD_THRESHOLD_GB * 1024**3),
            )
        )
        logger.debug(
            "Undersharding rule: count=%s threshold=%s",
            undersharded,
            threshold,
        )
        findings.append(
            Finding(
                id="shards.undersharded",
                category="shards",
                title="Undersharded indices detected",
                status=FindingStatus.WARN,
                severity=Severity.MEDIUM,
                score_impact=min(undersharded * 2, 10),
                summary=(
                    f"{undersharded} shard(s) exceed "
                    f"{format_bytes(threshold)} (UNDERSHARDED)."
                ),
                source="rule",
                metadata={
                    "undersharded_count": undersharded,
                    "threshold_bytes": threshold,
                    "avg_bytes": avg_bytes,
                },
            )
        )

    return findings
