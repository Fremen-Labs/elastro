"""Best-practice linter for Elasticsearch index settings, mappings, and shards."""

from __future__ import annotations

import time
from typing import List, Optional, Sequence, Set

from elastro.core.client import ElasticsearchClient
from elastro.core.errors import OperationError
from elastro.core.index import IndexManager
from elastro.core.logger import get_logger
from elastro.health.collectors.base import CollectContext
from elastro.health.collectors.mappings import MappingsCollector
from elastro.health.collectors.security import SecurityCollector
from elastro.health.collectors.shards import ShardsCollector
from elastro.health.mappings import is_system_index
from elastro.health.models import (
    Finding,
    FindingStatus,
    RemediationAction,
    RemediationSafety,
    Severity,
)
from elastro.health.rules.mapping_explosion import mapping_explosion_findings
from elastro.health.rules.engine import RuleContext
from elastro.health.shards import (
    DEFAULT_OVERSHARD_THRESHOLD_MB,
    DEFAULT_UNDERSHARD_THRESHOLD_GB,
    format_bytes,
)

logger = get_logger(__name__)

LINT_CATEGORIES = ("settings", "mappings", "shards", "security")
_DEFAULT_MAX_INDICES = 50


def run_lint(
    client: ElasticsearchClient,
    *,
    categories: Optional[Sequence[str]] = None,
    index_pattern: Optional[str] = None,
    timeout: str = "30s",
    max_indices: int = _DEFAULT_MAX_INDICES,
) -> List[Finding]:
    """Run selected lint categories and return findings."""
    selected = _normalize_categories(categories)
    ctx = CollectContext(client=client, timeout=timeout)
    ctx.options["max_indices"] = max_indices
    if index_pattern:
        ctx.options["index"] = index_pattern

    findings: List[Finding] = []
    skipped: List[str] = []
    start = time.monotonic()
    logger.info(
        "Starting health lint categories=%s index_pattern=%s max_indices=%s",
        ",".join(sorted(selected)),
        index_pattern or "*",
        max_indices,
    )

    if "settings" in selected:
        findings.extend(
            _lint_settings(
                client,
                max_indices=max_indices,
                index_pattern=index_pattern,
            )
        )

    collector_data: dict = {}
    if "mappings" in selected:
        mappings_result = MappingsCollector().collect(ctx)
        if mappings_result.status == "ok":
            collector_data["mappings"] = mappings_result.data
            findings.extend(
                mapping_explosion_findings(
                    RuleContext(collector_data=collector_data),
                )
            )
        elif mappings_result.error:
            skipped.append("mappings")
            logger.warning("Mappings lint skipped: %s", mappings_result.error)

    if "shards" in selected:
        shards_result = ShardsCollector().collect(ctx)
        if shards_result.status == "ok":
            findings.extend(_lint_shards(shards_result.data))
        elif shards_result.error:
            skipped.append("shards")
            logger.warning("Shards lint skipped: %s", shards_result.error)

    if "security" in selected:
        security_result = SecurityCollector().collect(ctx)
        if security_result.status == "ok":
            findings.extend(security_result.data.get("findings", []))
        elif security_result.error:
            skipped.append("security")
            logger.warning("Security lint skipped: %s", security_result.error)

    if skipped:
        findings.append(
            Finding(
                id="lint.categories_skipped",
                category="lint",
                title="Some lint categories were skipped",
                status=FindingStatus.WARN,
                severity=Severity.LOW,
                summary=f"Skipped categories: {', '.join(skipped)}",
                source="lint",
            )
        )

    logger.info(
        "Health lint complete categories=%s findings=%s duration_ms=%s",
        ",".join(sorted(selected)),
        len(findings),
        int((time.monotonic() - start) * 1000),
    )
    return findings


def _normalize_categories(categories: Optional[Sequence[str]]) -> Set[str]:
    if not categories:
        return set(LINT_CATEGORIES)
    selected = {item.strip().lower() for item in categories if item}
    unknown = selected - set(LINT_CATEGORIES)
    if unknown:
        raise OperationError(
            f"Unknown lint categories: {', '.join(sorted(unknown))}. "
            f"Valid: {', '.join(LINT_CATEGORIES)}"
        )
    return selected


def _lint_settings(
    client: ElasticsearchClient,
    *,
    max_indices: int,
    index_pattern: Optional[str] = None,
) -> List[Finding]:
    index_manager = IndexManager(client)
    findings: List[Finding] = []

    try:
        indices = index_manager.list(pattern=index_pattern or "*")
    except OperationError as exc:
        logger.error("Settings lint failed listing indices: %s", exc, exc_info=True)
        raise

    scanned = 0
    for entry in indices:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("index", "")).strip()
        if not name or is_system_index(name):
            continue

        try:
            raw = index_manager.get(name)
        except OperationError as exc:
            logger.debug("Settings lint skip %s: %s", name, exc)
            continue

        if isinstance(raw, dict) and name in raw:
            body = raw[name]
        elif isinstance(raw, dict):
            body = next(iter(raw.values()), {})
        else:
            continue

        settings = (body.get("settings") or {}).get("index") or {}
        if not isinstance(settings, dict):
            settings = {}

        findings.extend(_settings_findings(name, settings, entry))
        scanned += 1
        if scanned >= max_indices:
            break

    return findings


def _settings_findings(
    index_name: str,
    settings: dict,
    cat_entry: dict,
) -> List[Finding]:
    findings: List[Finding] = []

    replicas = _parse_int(settings.get("number_of_replicas"))
    if replicas == 0:
        findings.append(
            Finding(
                id=f"settings.replicas_zero.{index_name}",
                category="settings",
                title=f"Index has zero replicas: {index_name}",
                status=FindingStatus.WARN,
                severity=Severity.MEDIUM,
                score_impact=5,
                summary=(
                    f"Index '{index_name}' sets number_of_replicas=0, "
                    "reducing availability during node loss."
                ),
                affected_resources=[index_name],
                source="lint",
                remediation=RemediationAction(
                    id="review_replicas",
                    label="Review replica settings",
                    command=f"elastro index get {index_name}",
                    safety=RemediationSafety.OBSERVE,
                ),
            )
        )

    refresh = str(settings.get("refresh_interval", "")).strip().lower()
    docs_count = _parse_int(cat_entry.get("docs.count"), default=0)
    if refresh in {"1s", "500ms", "100ms"} and docs_count >= 1_000_000:
        findings.append(
            Finding(
                id=f"settings.refresh_aggressive.{index_name}",
                category="settings",
                title=f"Aggressive refresh interval: {index_name}",
                status=FindingStatus.WARN,
                severity=Severity.LOW,
                score_impact=2,
                summary=(
                    f"Index '{index_name}' uses refresh_interval={refresh} "
                    f"with {docs_count:,} documents."
                ),
                affected_resources=[index_name],
                source="lint",
            )
        )

    primary_shards = _parse_int(cat_entry.get("pri"))
    if primary_shards is not None and primary_shards > 10 and docs_count < 10_000:
        findings.append(
            Finding(
                id=f"settings.oversharded_primary.{index_name}",
                category="settings",
                title=f"High primary shard count for small index: {index_name}",
                status=FindingStatus.WARN,
                severity=Severity.MEDIUM,
                score_impact=5,
                summary=(
                    f"Index '{index_name}' has {primary_shards} primary shards "
                    f"but only {docs_count:,} documents."
                ),
                affected_resources=[index_name],
                source="lint",
            )
        )

    return findings


def _lint_shards(shard_data: dict) -> List[Finding]:
    findings: List[Finding] = []
    analysis = shard_data.get("analysis") or {}
    if not analysis:
        return findings

    oversharded = int(analysis.get("oversharded_count", 0))
    undersharded = int(analysis.get("undersharded_count", 0))
    unassigned = int(analysis.get("unassigned_count", 0))

    if unassigned > 0:
        findings.append(
            Finding(
                id="shards.unassigned",
                category="shards",
                title="Unassigned shards detected",
                status=FindingStatus.FAIL,
                severity=Severity.HIGH,
                score_impact=min(unassigned * 2, 15),
                summary=f"{unassigned} shard(s) are UNASSIGNED.",
                source="lint",
                remediation=RemediationAction(
                    id="explain_allocation",
                    label="Explain shard allocation",
                    command="elastro health shards --explain",
                    safety=RemediationSafety.OBSERVE,
                ),
            )
        )

    if oversharded > 0:
        from elastro.health.finding_guides.oversharding import build_oversharding_guide

        threshold = int(
            analysis.get(
                "overshard_threshold_bytes",
                int(DEFAULT_OVERSHARD_THRESHOLD_MB * 1024 * 1024),
            )
        )
        detail, guide_metadata, affected = build_oversharding_guide(analysis)
        findings.append(
            Finding(
                id="shards.oversharded",
                category="shards",
                title="Oversharded shards detected",
                status=FindingStatus.WARN,
                severity=Severity.MEDIUM,
                score_impact=min(oversharded, 10),
                summary=(
                    f"{oversharded} shard(s) are smaller than "
                    f"{format_bytes(threshold)}."
                ),
                detail=detail,
                affected_resources=affected,
                source="lint",
                remediation=RemediationAction(
                    id="analyze_shards",
                    label="Analyze shard sizes",
                    command="elastro health shards --analyze -o table",
                    safety=RemediationSafety.OBSERVE,
                ),
                metadata={
                    "oversharded_count": oversharded,
                    "threshold_bytes": threshold,
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
        findings.append(
            Finding(
                id="shards.undersharded",
                category="shards",
                title="Undersharded shards detected",
                status=FindingStatus.WARN,
                severity=Severity.MEDIUM,
                score_impact=min(undersharded * 2, 10),
                summary=(f"{undersharded} shard(s) exceed {format_bytes(threshold)}."),
                source="lint",
                remediation=RemediationAction(
                    id="analyze_shards",
                    label="Analyze shard sizes",
                    command="elastro health shards --analyze",
                    safety=RemediationSafety.OBSERVE,
                ),
            )
        )

    return findings


def _parse_int(value: object, *, default: Optional[int] = None) -> Optional[int]:
    if value is None:
        return default
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default
