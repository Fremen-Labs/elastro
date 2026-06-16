"""Snapshot / SLM backup policy gaps."""

from __future__ import annotations

from typing import List

from elastro.core.logger import get_logger
from elastro.health.models import Finding, FindingStatus, Severity
from elastro.health.rules.engine import RuleContext

logger = get_logger(__name__)


def backup_policy_findings(ctx: RuleContext) -> List[Finding]:
    """Emit a finding when no snapshot repositories are registered."""
    if "snapshots" not in ctx.collector_data:
        return []

    snapshots = ctx.collector_data.get("snapshots") or {}
    repo_count = int(snapshots.get("count", 0) or 0)
    if repo_count > 0:
        return []

    logger.info("No snapshot repositories configured cluster=%s", ctx.cluster_name)
    return [
        Finding(
            id="snapshots.not_configured",
            category="snapshots",
            title="No snapshot repositories configured",
            status=FindingStatus.WARN,
            severity=Severity.HIGH,
            score_impact=8,
            summary=(
                "This cluster has zero snapshot repositories. Without SLM or "
                "scheduled snapshots, index and cluster metadata cannot be restored "
                "after deletion or corruption."
            ),
            detail=(
                "Elasticsearch does not perform automatic backups.\n\n"
                "How to resolve:\n"
                "  1. Register a snapshot repository (S3, GCS, shared filesystem)\n"
                "  2. Configure SLM policies via _slm/policy for recurring snapshots\n"
                "  3. Verify with: elastro snapshot list (or GET _snapshot)\n"
                "  4. Test restore on a non-production cluster quarterly"
            ),
            affected_resources=[ctx.cluster_name] if ctx.cluster_name != "unknown" else [],
            source="rule",
            metadata={"repository_count": 0},
        )
    ]