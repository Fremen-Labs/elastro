"""APM and Beats coverage health rules."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from elastro.core.logger import get_logger
from elastro.health.models import (
    Finding,
    FindingStatus,
    RemediationAction,
    RemediationSafety,
    Severity,
)
from elastro.health.rules.engine import RuleContext
from elastro.health.shards import parse_store_size

logger = get_logger(__name__)

COVERAGE_FEATURES = frozenset({"apm", "beats"})
_APM_PREFIXES = ("traces-apm", "metrics-apm", "logs-apm")
_BEATS_PREFIXES = (
    "filebeat-",
    "metricbeat-",
    "logs-filebeat",
    "metrics-metricbeat",
)
_AGE_PATTERN = re.compile(r"^(\d+(?:\.\d+)?)([dhms])", re.IGNORECASE)
_REJECTION_MIN_DOCS = 100
_REJECTION_RATE = 0.01
_IMBALANCE_RATIO = 2.0
_IMBALANCE_MIN_PRIMARIES = 4
_IMBALANCE_MIN_BYTES = 1024**3
_HOT_LAG_DAYS = 2.0


def finding_matches_feature(finding: Finding, feature: str) -> bool:
    """Return True when a finding belongs to ``apm`` or ``beats``."""
    key = feature.lower()
    if finding.category == key or finding.indicator == key:
        return True
    return finding.id.startswith(f"{key}.")


def is_apm_beats_finding(finding: Finding) -> bool:
    """Return True when a finding is APM or Beats coverage-related."""
    return any(finding_matches_feature(finding, name) for name in COVERAGE_FEATURES)


def is_apm_index(name: str) -> bool:
    """Return True for APM data-stream or backing-index names."""
    return _normalized_name(name).startswith(_APM_PREFIXES)


def is_beats_index(name: str) -> bool:
    """Return True for Filebeat/Metricbeat index names."""
    return _normalized_name(name).startswith(_BEATS_PREFIXES)


def apm_data_stream_findings(ctx: RuleContext) -> List[Finding]:
    """APM data streams missing or without recent documents."""
    data = _apm_beats_data(ctx)
    if not data:
        return []
    streams = [
        item
        for item in data.get("data_streams") or []
        if isinstance(item, dict) and is_apm_index(str(item.get("name") or ""))
    ]
    indices = [
        item
        for item in data.get("indices") or []
        if isinstance(item, dict) and is_apm_index(str(item.get("index") or ""))
    ]
    if not streams and not indices:
        logger.info("APM data streams missing cluster=%s", ctx.cluster_name)
        return [
            Finding(
                id="apm.datastream.missing",
                category="apm",
                title="APM data stream missing",
                status=FindingStatus.FAIL,
                severity=Severity.HIGH,
                score_impact=15,
                summary=(
                    "No traces-apm*, metrics-apm*, or logs-apm* data streams "
                    "or indices were found."
                ),
                source="rule",
                indicator="apm",
                remediation=_observe(
                    "coverage.check",
                    "Validate APM coverage",
                    "elastro -o table coverage check --all",
                ),
            )
        ]

    freshness = (data.get("freshness") or {}).get("apm") or {}
    count = _safe_int(freshness.get("doc_count"))
    if count > 0:
        return []
    resources = [str(item.get("name")) for item in streams if item.get("name")]
    resources.extend(str(item.get("index")) for item in indices if item.get("index"))
    return [
        Finding(
            id="apm.datastream.stale",
            category="apm",
            title="APM data stream stale",
            status=FindingStatus.WARN,
            severity=Severity.HIGH,
            score_impact=10,
            summary=(
                "APM streams exist but no documents arrived in the last 15 minutes."
            ),
            affected_resources=resources[:25],
            source="rule",
            indicator="apm",
            remediation=_observe(
                "coverage.check",
                "Check APM data arrival",
                "elastro -o table coverage check --pattern 'traces-apm*'",
            ),
            metadata={"doc_count": count},
        )
    ]


def beats_ilm_findings(ctx: RuleContext) -> List[Finding]:
    """Beats indices that exist but are not ILM-managed."""
    data = _apm_beats_data(ctx)
    if not data:
        return []
    explains = data.get("ilm") or {}
    unmanaged: List[str] = []
    for item in data.get("indices") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("index") or "").strip()
        if not name or not is_beats_index(name):
            continue
        explain = explains.get(name)
        if not isinstance(explain, dict):
            continue
        if explain.get("managed") is False:
            unmanaged.append(name)
    if not unmanaged:
        return []
    logger.info("Beats indices without ILM: %s", len(unmanaged))
    return [
        Finding(
            id="beats.ilm.missing",
            category="beats",
            title="Beats index without active ILM",
            status=FindingStatus.WARN,
            severity=Severity.MEDIUM,
            score_impact=8,
            summary=(
                f"{len(unmanaged)} Filebeat/Metricbeat index(es) are not ILM-managed."
            ),
            affected_resources=unmanaged[:25],
            source="rule",
            indicator="beats",
            remediation=_observe(
                "coverage.templates",
                "Apply Beats ILM templates",
                "elastro coverage templates apply filebeat --dry-run",
            ),
            metadata={"count": len(unmanaged)},
        )
    ]


def apm_rejection_findings(ctx: RuleContext) -> List[Finding]:
    """High indexing failure rate on APM or Beats indices."""
    data = _apm_beats_data(ctx)
    if not data:
        return []
    stats = data.get("stats") or {}
    if not isinstance(stats, dict):
        return []
    rejected: List[Tuple[str, int, int]] = []
    for name, body in stats.items():
        if not isinstance(name, str) or not (
            is_apm_index(name) or is_beats_index(name)
        ):
            continue
        if not isinstance(body, dict):
            continue
        indexing = _indexing_stats(body)
        total = _safe_int(indexing.get("index_total"))
        failed = _safe_int(indexing.get("index_failed"))
        if total < _REJECTION_MIN_DOCS or failed <= 0:
            continue
        if failed / total >= _REJECTION_RATE:
            rejected.append((name, failed, total))
    if not rejected:
        return []
    feature = "apm" if any(is_apm_index(name) for name, _, _ in rejected) else "beats"
    names = [name for name, _, _ in rejected]
    worst = max(rejected, key=lambda item: item[1] / item[2])
    return [
        Finding(
            id=f"{feature}.index.rejections",
            category=feature,
            title="High document rejection rate on APM/Beats indices",
            status=FindingStatus.WARN,
            severity=Severity.HIGH,
            score_impact=12,
            summary=(
                f"{len(rejected)} index(es) reject "
                f"{(worst[1] / worst[2]) * 100:.1f}%+ of indexed documents."
            ),
            affected_resources=names[:25],
            source="rule",
            indicator=feature,
            metadata={
                "indices": [
                    {"index": name, "failed": failed, "total": total}
                    for name, failed, total in rejected[:25]
                ]
            },
        )
    ]


def apm_beats_shard_imbalance_findings(ctx: RuleContext) -> List[Finding]:
    """Uneven primary-shard size across nodes for high-volume APM/Beats indices."""
    rows = (ctx.collector_data.get("shards") or {}).get("shards") or []
    if not isinstance(rows, list):
        return []
    by_index: Dict[str, Dict[str, int]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("index") or "").strip()
        if not name or not (is_apm_index(name) or is_beats_index(name)):
            continue
        if str(row.get("prirep") or "").lower() not in {"p", "primary"}:
            continue
        if str(row.get("state") or "").upper() != "STARTED":
            continue
        node = str(row.get("node") or "").strip() or "unknown"
        size = parse_store_size(row.get("store"))
        if size is None:
            continue
        by_index.setdefault(name, {})
        by_index[name][node] = by_index[name].get(node, 0) + size

    imbalanced: List[str] = []
    details: List[Dict[str, Any]] = []
    for name, node_bytes in by_index.items():
        primary_count = sum(
            1
            for row in rows
            if isinstance(row, dict)
            and row.get("index") == name
            and str(row.get("prirep") or "").lower() in {"p", "primary"}
        )
        if primary_count < _IMBALANCE_MIN_PRIMARIES or len(node_bytes) < 2:
            continue
        total = sum(node_bytes.values())
        if total < _IMBALANCE_MIN_BYTES:
            continue
        smallest = min(node_bytes.values())
        largest = max(node_bytes.values())
        if smallest <= 0 or largest < _IMBALANCE_RATIO * smallest:
            continue
        imbalanced.append(name)
        details.append(
            {
                "index": name,
                "min_bytes": smallest,
                "max_bytes": largest,
                "nodes": len(node_bytes),
            }
        )
    if not imbalanced:
        return []
    feature = "apm" if any(is_apm_index(name) for name in imbalanced) else "beats"
    return [
        Finding(
            id=f"{feature}.shards.imbalance",
            category=feature,
            title="Shard imbalance on high-volume APM/Beats indices",
            status=FindingStatus.WARN,
            severity=Severity.MEDIUM,
            score_impact=8,
            summary=(
                f"{len(imbalanced)} high-volume index(es) have primary shard "
                f"size skewed more than {_IMBALANCE_RATIO:.0f}x across nodes."
            ),
            affected_resources=imbalanced[:25],
            source="rule",
            indicator=feature,
            metadata={"indices": details},
        )
    ]


def apm_ilm_phase_lag_findings(ctx: RuleContext) -> List[Finding]:
    """ILM-managed APM/Beats indices stuck in the hot phase."""
    data = _apm_beats_data(ctx)
    if not data:
        return []
    explains = data.get("ilm") or {}
    stuck: List[str] = []
    for name, explain in explains.items():
        if not isinstance(name, str) or not isinstance(explain, dict):
            continue
        if not (is_apm_index(name) or is_beats_index(name)):
            continue
        if not explain.get("managed"):
            continue
        if str(explain.get("phase") or "").lower() != "hot":
            continue
        age = explain.get("age") or explain.get("time_since_index_creation")
        if _age_exceeds(age, days=_HOT_LAG_DAYS):
            stuck.append(name)
    if not stuck:
        return []
    feature = "apm" if any(is_apm_index(name) for name in stuck) else "beats"
    return [
        Finding(
            id=f"{feature}.ilm.hot_lag",
            category=feature,
            title="ILM phase lag (indices stuck in hot)",
            status=FindingStatus.WARN,
            severity=Severity.MEDIUM,
            score_impact=8,
            summary=(
                f"{len(stuck)} APM/Beats index(es) remain in the hot phase "
                f"for more than {_HOT_LAG_DAYS:.0f} days."
            ),
            affected_resources=stuck[:25],
            source="rule",
            indicator=feature,
            remediation=_observe(
                "ilm.explain",
                "Inspect ILM lifecycle",
                f"elastro ilm get {stuck[0]}" if stuck else "elastro ilm list",
            ),
            metadata={"count": len(stuck)},
        )
    ]


def _apm_beats_data(ctx: RuleContext) -> Dict[str, Any]:
    data = ctx.collector_data.get("apm_beats") or {}
    return data if isinstance(data, dict) else {}


def _normalized_name(name: str) -> str:
    value = (name or "").lstrip(".")
    if value.startswith("ds-"):
        value = value[3:]
    return value


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _indexing_stats(body: Dict[str, Any]) -> Dict[str, Any]:
    for key in ("primaries", "total"):
        block = body.get(key)
        if isinstance(block, dict) and isinstance(block.get("indexing"), dict):
            return block["indexing"]
    indexing = body.get("indexing")
    return indexing if isinstance(indexing, dict) else {}


def _age_exceeds(age: Any, *, days: float) -> bool:
    if age is None:
        return False
    if isinstance(age, (int, float)):
        # ILM may return milliseconds since creation.
        millis = float(age)
        if millis > days * 86400 * 10:
            return millis >= days * 86400 * 1000
        return millis >= days * 86400
    match = _AGE_PATTERN.match(str(age).strip())
    if not match:
        return False
    amount = float(match.group(1))
    unit = match.group(2).lower()
    seconds = {"d": 86400.0, "h": 3600.0, "m": 60.0, "s": 1.0}[unit] * amount
    return seconds >= days * 86400.0


def _observe(action_id: str, label: str, command: str) -> RemediationAction:
    return RemediationAction(
        id=action_id,
        label=label,
        command=command,
        safety=RemediationSafety.OBSERVE,
    )
