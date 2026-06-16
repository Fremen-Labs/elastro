"""Cluster-level blocks (read-only cluster, metadata write blocks)."""

from __future__ import annotations

from typing import Any, Dict, List

from elastro.core.logger import get_logger
from elastro.health.models import Finding, FindingStatus, Severity
from elastro.health.rules.engine import RuleContext

logger = get_logger(__name__)

_BLOCK_LABELS = {
    "read_only": "Cluster read-only block",
    "read_only_allow_delete": "Read-only allow-delete block",
    "metadata": "Metadata write block",
}


def cluster_block_findings(ctx: RuleContext) -> List[Finding]:
    """Emit findings for active cluster-level blocks."""
    health = ctx.collector_data.get("cluster_health") or {}
    blocks = health.get("blocks") or {}
    if not isinstance(blocks, dict) or not blocks:
        return []

    findings: List[Finding] = []
    for block_id, block_data in blocks.items():
        if not isinstance(block_data, dict):
            continue
        block_type = str(block_data.get("description", block_id))
        label = _BLOCK_LABELS.get(block_id, block_type)

        logger.info(
            "Cluster block active cluster=%s block=%s",
            ctx.cluster_name,
            block_id,
        )
        findings.append(
            Finding(
                id=f"cluster.block.{block_id}",
                category="cluster",
                title=label,
                status=FindingStatus.FAIL,
                severity=Severity.CRITICAL,
                score_impact=12,
                summary=(
                    f"Cluster block '{block_id}' is active: {block_type}. "
                    "Writes or metadata updates may be blocked cluster-wide."
                ),
                detail=_block_detail(block_id, block_data),
                affected_resources=[ctx.cluster_name]
                if ctx.cluster_name != "unknown"
                else [],
                source="rule",
                metadata={"block_id": block_id, "block": block_data},
            )
        )

    return findings


def _block_detail(block_id: str, block_data: Dict[str, Any]) -> str:
    return (
        f"Active block: {block_id}\n"
        f"Description: {block_data.get('description', 'unknown')}\n\n"
        "How to resolve:\n"
        "  • read_only_allow_delete: free disk above flood watermark, then clear block\n"
        "  • read_only: remove cluster.blocks.read_only setting after fixing root cause\n"
        "  • metadata: resolve master election or cluster state issues first\n"
        "  • elastro health assess --detail  (disk / watermark findings)"
    )
