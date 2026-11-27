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

# Keys on GET _cluster/state/blocks that are containers, not block types.
_STATE_CONTAINERS = frozenset({"indices", "cluster", "global"})


def _is_block_payload(value: Any) -> bool:
    return isinstance(value, dict) and bool(value)


def cluster_block_findings(ctx: RuleContext) -> List[Finding]:
    """Emit findings for active cluster-level blocks.

    Elasticsearch ``_cluster/state/blocks`` looks like
    ``{"indices": {...}, "cluster": {...}}``. Empty containers are not
    blocks. A FAIL finding for ``cluster.block.indices`` on a green
    cluster was a false positive from treating the ``indices`` map as a
    block type.
    """
    health = ctx.collector_data.get("cluster_health") or {}
    blocks = health.get("blocks") or {}
    if not isinstance(blocks, dict) or not blocks:
        return []

    findings: List[Finding] = []
    nested_cluster = blocks.get("cluster")
    if isinstance(nested_cluster, dict):
        for block_id, block_data in nested_cluster.items():
            finding = _cluster_block_finding(ctx, str(block_id), block_data)
            if finding is not None:
                findings.append(finding)
    else:
        for block_id, block_data in blocks.items():
            if block_id in _STATE_CONTAINERS:
                continue
            finding = _cluster_block_finding(ctx, str(block_id), block_data)
            if finding is not None:
                findings.append(finding)

    index_blocks = blocks.get("indices")
    if isinstance(index_blocks, dict):
        blocked = [
            name for name, payload in index_blocks.items() if _is_block_payload(payload)
        ]
        if blocked:
            logger.info(
                "Index-level blocks cluster=%s count=%s",
                ctx.cluster_name,
                len(blocked),
            )
            findings.append(
                Finding(
                    id="cluster.block.indices",
                    category="cluster",
                    title="Index-level blocks",
                    status=FindingStatus.WARN,
                    severity=Severity.HIGH,
                    score_impact=6,
                    summary=(
                        f"{len(blocked)} index(es) have active blocks. "
                        "Cluster health can still be green."
                    ),
                    detail=(
                        "Blocked indices:\n  • "
                        + "\n  • ".join(blocked[:20])
                        + ("\n  • …" if len(blocked) > 20 else "")
                    ),
                    affected_resources=blocked[:20],
                    source="rule",
                    metadata={"index_count": len(blocked)},
                )
            )

    return findings


def _cluster_block_finding(
    ctx: RuleContext, block_id: str, block_data: Any
) -> Finding | None:
    if not _is_block_payload(block_data):
        return None
    block_type = str(block_data.get("description", block_id))
    label = _BLOCK_LABELS.get(block_id, block_type)
    logger.info(
        "Cluster block active cluster=%s block=%s",
        ctx.cluster_name,
        block_id,
    )
    return Finding(
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
        affected_resources=[ctx.cluster_name] if ctx.cluster_name != "unknown" else [],
        source="rule",
        metadata={"block_id": block_id, "block": block_data},
    )


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
