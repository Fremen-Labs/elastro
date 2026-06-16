"""Disk usage collector with cluster watermark derivation."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from elastro.core.errors import OperationError
from elastro.core.logger import get_logger
from elastro.health.collectors.base import CollectContext, CollectorResult
from elastro.health.collectors.nodes import NodesCollector
from elastro.health.manager import HealthManager
from elastro.core.index import IndexManager
from elastro.health.disk_blocks import discover_read_only_blocked_indices
from elastro.health.models import (
    Finding,
    FindingStatus,
    RemediationAction,
    RemediationSafety,
    Severity,
)

logger = get_logger(__name__)

_DEFAULT_WATERMARKS = {
    "low": 85.0,
    "high": 90.0,
    "flood_stage": 95.0,
}


class DiskCollector:
    """Derive per-node disk usage and emit findings above watermarks."""

    name = "disk"

    def collect(self, ctx: CollectContext) -> CollectorResult:
        manager = HealthManager(ctx.client)
        logger.debug("Collecting disk usage and watermark settings")

        try:
            settings = manager.cluster_settings(include_defaults=True)
            watermarks = parse_disk_watermarks(settings)
            nodes_result = NodesCollector().collect(
                CollectContext(
                    client=ctx.client,
                    timeout=ctx.timeout,
                    es_version=ctx.es_version,
                    options={"metrics": "fs"},
                )
            )
            if nodes_result.status != "ok":
                return CollectorResult(
                    name=self.name,
                    status="error",
                    error=nodes_result.error or "Failed to collect node filesystem stats",
                )

            nodes = nodes_result.data.get("nodes", {})
            node_usages = build_node_disk_usages(nodes)
            findings = disk_watermark_findings(node_usages, watermarks)
            findings.extend(
                read_only_block_findings(IndexManager(ctx.client), findings)
            )

            logger.info(
                "Disk collector complete: nodes=%s findings=%s",
                len(node_usages),
                len(findings),
            )
            return CollectorResult(
                name=self.name,
                status="ok",
                data={
                    "watermarks": watermarks,
                    "nodes": node_usages,
                    "findings": findings,
                    "cluster_settings": settings,
                },
            )
        except OperationError as exc:
            logger.error("Disk collector failed: %s", exc)
            return CollectorResult(name=self.name, status="error", error=str(exc))


def parse_disk_watermarks(settings: Dict[str, Any]) -> Dict[str, float]:
    """Parse cluster disk watermark settings as used-percent thresholds."""
    merged: Dict[str, Any] = {}
    for layer in ("defaults", "persistent", "transient"):
        layer_values = settings.get(layer, {})
        if isinstance(layer_values, dict):
            merged.update(layer_values)

    return {
        "low": _parse_percent_setting(
            merged.get("cluster.routing.allocation.disk.watermark.low"),
            _DEFAULT_WATERMARKS["low"],
        ),
        "high": _parse_percent_setting(
            merged.get("cluster.routing.allocation.disk.watermark.high"),
            _DEFAULT_WATERMARKS["high"],
        ),
        "flood_stage": _parse_percent_setting(
            merged.get("cluster.routing.allocation.disk.watermark.flood_stage"),
            _DEFAULT_WATERMARKS["flood_stage"],
        ),
    }


def _parse_percent_setting(value: Any, default: float) -> float:
    if value is None:
        return default
    text = str(value).strip()
    if text.endswith("%"):
        try:
            return float(text.rstrip("%"))
        except ValueError:
            return default
    return default


def disk_used_percent(fs: Dict[str, Any]) -> Optional[float]:
    """Compute used disk percentage from a nodes.stats fs block."""
    total_block = fs.get("total") or {}
    total_bytes = total_block.get("total_in_bytes")
    available_bytes = total_block.get("available_in_bytes")
    if not total_bytes or total_bytes <= 0:
        return None
    if available_bytes is None:
        return None
    used_bytes = total_bytes - available_bytes
    return round((used_bytes / total_bytes) * 100, 2)


def build_node_disk_usages(nodes: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return sorted node disk usage records."""
    records: List[Dict[str, Any]] = []
    for node_id, node in nodes.items():
        fs = node.get("fs") or {}
        used_pct = disk_used_percent(fs)
        if used_pct is None:
            continue
        total_block = fs.get("total") or {}
        records.append(
            {
                "node_id": node_id,
                "node_name": node.get("name", node_id),
                "used_percent": used_pct,
                "total_bytes": total_block.get("total_in_bytes"),
                "available_bytes": total_block.get("available_in_bytes"),
            }
        )
    records.sort(key=lambda item: item["used_percent"], reverse=True)
    return records


def disk_watermark_findings(
    node_usages: List[Dict[str, Any]],
    watermarks: Dict[str, float],
) -> List[Finding]:
    """Emit findings for nodes at or above high/flood disk watermarks."""
    findings: List[Finding] = []
    high_threshold = watermarks.get("high", _DEFAULT_WATERMARKS["high"])
    flood_threshold = watermarks.get("flood_stage", _DEFAULT_WATERMARKS["flood_stage"])

    for node in node_usages:
        used_pct = node["used_percent"]
        node_name = node["node_name"]
        if used_pct >= flood_threshold:
            status, severity, stage = FindingStatus.FAIL, Severity.CRITICAL, "flood-stage"
            score_impact = 15
        elif used_pct >= high_threshold:
            status, severity, stage = FindingStatus.WARN, Severity.HIGH, "high"
            score_impact = 8
        else:
            continue

        findings.append(
            Finding(
                id=f"disk.{stage}.{node_name}",
                category="disk",
                title=f"Disk {stage} watermark on {node_name}",
                status=status,
                severity=severity,
                score_impact=score_impact,
                summary=(
                    f"Node '{node_name}' disk usage is {used_pct}% "
                    f"(threshold {flood_threshold if stage == 'flood-stage' else high_threshold}%)."
                ),
                affected_resources=[node_name],
                source="collector",
                remediation=RemediationAction(
                    id="disk_watermark",
                    label="Review disk watermarks",
                    command="elastro cluster settings",
                    safety=RemediationSafety.OBSERVE,
                ),
                metadata={
                    "node_id": node["node_id"],
                    "used_percent": used_pct,
                    "watermarks": watermarks,
                    "stage": stage,
                },
            )
        )

    return findings


def read_only_block_findings(
    index_manager: IndexManager,
    existing_findings: List[Finding],
) -> List[Finding]:
    """Emit findings for indices blocked by flood-stage disk protection."""
    if not any(
        finding.metadata.get("stage") == "flood-stage"
        for finding in existing_findings
        if finding.category == "disk"
    ):
        return []

    blocked = discover_read_only_blocked_indices(index_manager)
    findings: List[Finding] = []
    for index_name in blocked:
        findings.append(
            Finding(
                id=f"disk.read_only_block.{index_name}",
                category="disk",
                title=f"Index blocked by flood-stage disk watermark: {index_name}",
                status=FindingStatus.WARN,
                severity=Severity.HIGH,
                score_impact=8,
                summary=(
                    f"Index '{index_name}' has read_only_allow_delete enabled. "
                    "Resolve disk pressure before clearing the block."
                ),
                affected_resources=[index_name],
                source="collector",
                remediation=RemediationAction(
                    id="clear_read_only",
                    label="Clear read-only-allow-delete block",
                    command=(
                        "elastro health fix --action clear_read_only "
                        f"--index {index_name}"
                    ),
                    safety=RemediationSafety.DESTRUCTIVE,
                ),
                metadata={"index_name": index_name},
            )
        )
    return findings