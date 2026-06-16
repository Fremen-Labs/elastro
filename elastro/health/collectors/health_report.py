"""Health report collector using GET _health_report (Elasticsearch 8.7+)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from elastro.core.logger import get_logger
from elastro.health.collectors.base import CollectContext, CollectorResult
from elastro.health.models import (
    Finding,
    FindingStatus,
    RemediationAction,
    RemediationSafety,
    Severity,
)
from elastro.health.version import supports_health_report

logger = get_logger(__name__)

KNOWN_INDICATORS = (
    "master_is_stable",
    "shards_availability",
    "disk",
    "repository_integrity",
    "data_stream_lifecycle",
    "ilm",
    "slm",
    "shards_capacity",
    "file_settings",
)

_INDICATOR_STATUS_MAP: Dict[str, Tuple[FindingStatus, Severity]] = {
    "red": (FindingStatus.FAIL, Severity.CRITICAL),
    "yellow": (FindingStatus.WARN, Severity.HIGH),
    "green": (FindingStatus.PASS, Severity.INFO),
    "unknown": (FindingStatus.UNKNOWN, Severity.MEDIUM),
    "unavailable": (FindingStatus.SKIPPED, Severity.LOW),
}

_INDICATOR_CATEGORIES = {
    "master_is_stable": "master",
    "shards_availability": "shards",
    "disk": "disk",
    "repository_integrity": "snapshots",
    "data_stream_lifecycle": "datastream",
    "ilm": "ilm",
    "slm": "slm",
    "shards_capacity": "shards",
    "file_settings": "settings",
}


def map_indicator(indicator_name: str, body: Dict[str, Any]) -> Finding:
    """Map a single _health_report indicator to a Finding."""
    status = body.get("status", "unknown")
    finding_status, severity = _INDICATOR_STATUS_MAP.get(
        status, (FindingStatus.UNKNOWN, Severity.MEDIUM)
    )

    symptom = body.get("symptom", f"Indicator {indicator_name} status is {status}")
    diagnoses = body.get("diagnosis") or []
    detail_parts: List[str] = []
    affected: List[str] = []
    remediation: Optional[RemediationAction] = None

    for diagnosis in diagnoses:
        if not isinstance(diagnosis, dict):
            continue
        cause = diagnosis.get("cause")
        action = diagnosis.get("action")
        if cause:
            detail_parts.append(cause)
        if action and remediation is None:
            detail_parts.append(f"Recommended action: {action}")
            remediation = RemediationAction(
                id=f"{indicator_name}.diagnosis",
                label=action,
                command=_suggest_command(indicator_name, action, diagnosis),
                safety=RemediationSafety.SUGGEST,
            )
        affected.extend(_extract_affected_resources(diagnosis))

    if affected:
        affected = list(dict.fromkeys(affected))

    impacts = body.get("impacts") or []
    if impacts and not detail_parts:
        detail_parts.append(impacts[0].get("description", ""))

    return Finding(
        id=f"indicator.{indicator_name}",
        category=_INDICATOR_CATEGORIES.get(indicator_name, indicator_name),
        title=_indicator_title(indicator_name, status),
        status=finding_status,
        severity=severity if status != "green" else Severity.INFO,
        score_impact=_score_impact_for_status(status),
        summary=symptom,
        detail="\n".join(part for part in detail_parts if part) or None,
        affected_resources=affected,
        source="health_report",
        indicator=indicator_name,
        remediation=remediation,
        metadata={"indicator": body},
    )


def map_indicators(report: Dict[str, Any]) -> List[Finding]:
    """Map all indicators in a health report response to findings."""
    indicators = report.get("indicators", {})
    findings: List[Finding] = []

    for name in KNOWN_INDICATORS:
        body = indicators.get(name)
        if body is None:
            findings.append(_missing_indicator_finding(name))
        elif isinstance(body, dict):
            findings.append(map_indicator(name, body))

    for name, body in indicators.items():
        if name in KNOWN_INDICATORS or not isinstance(body, dict):
            continue
        findings.append(map_indicator(name, body))

    return findings


def non_passing_findings(findings: List[Finding]) -> List[Finding]:
    """Return actionable findings (warn, fail, unknown) from a mapped report."""
    return [
        f
        for f in findings
        if f.status not in (FindingStatus.PASS, FindingStatus.SKIPPED)
    ]


class HealthReportCollector:
    """Collect cluster health from GET _health_report."""

    name = "health_report"

    def collect(self, ctx: CollectContext) -> CollectorResult:
        version = ctx.es_version or "unknown"
        if not supports_health_report(version):
            logger.info("Skipping health_report collector: ES %s < 8.7", version)
            return CollectorResult(
                name=self.name,
                status="skipped",
                error=f"Elasticsearch {version} does not support _health_report (requires 8.7+)",
            )

        verbose = bool(ctx.options.get("verbose_report", True))
        feature = ctx.options.get("feature")

        try:
            report = _fetch_health_report(ctx, verbose=verbose, feature=feature)
        except _HealthReportUnsupported as exc:
            return CollectorResult(
                name=self.name,
                status="skipped",
                error=str(exc),
            )
        except Exception as exc:
            logger.error("Health report collector failed: %s", exc)
            return CollectorResult(
                name=self.name,
                status="error",
                error=str(exc),
            )

        findings = map_indicators(report)
        return CollectorResult(
            name=self.name,
            status="ok",
            data={
                "report": report,
                "findings": findings,
                "cluster_name": report.get("cluster_name"),
                "status": report.get("status"),
                "indicators": report.get("indicators", {}),
            },
        )


class _HealthReportUnsupported(Exception):
    pass


def _fetch_health_report(
    ctx: CollectContext,
    *,
    verbose: bool,
    feature: Optional[Any] = None,
) -> Dict[str, Any]:
    es = ctx.client.client
    kwargs: Dict[str, Any] = {"verbose": verbose}

    try:
        if feature:
            response = es.health_report(feature=feature, **kwargs)
        else:
            response = es.health_report(**kwargs)
    except Exception as exc:
        if _is_not_found(exc):
            raise _HealthReportUnsupported(
                "_health_report API not available on this cluster"
            ) from exc
        raise

    if hasattr(response, "body"):
        return dict(response.body)
    return dict(response)


def _is_not_found(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code == 404:
        return True
    meta = getattr(exc, "meta", None)
    if meta is not None and getattr(meta, "status", None) == 404:
        return True
    return type(exc).__name__ == "NotFoundError"


def _missing_indicator_finding(indicator_name: str) -> Finding:
    return Finding(
        id=f"indicator.{indicator_name}.missing",
        category=_INDICATOR_CATEGORIES.get(indicator_name, indicator_name),
        title=f"{indicator_name.replace('_', ' ').title()} not reported",
        status=FindingStatus.SKIPPED,
        severity=Severity.LOW,
        summary="Indicator was not present in the health report response.",
        source="health_report",
        indicator=indicator_name,
    )


def _extract_affected_resources(diagnosis: Dict[str, Any]) -> List[str]:
    resources = diagnosis.get("affected_resources") or {}
    affected: List[str] = []
    for key in ("indices", "nodes", "snapshots", "feature_states"):
        values = resources.get(key)
        if isinstance(values, list):
            affected.extend(str(v) for v in values)
    return affected


def _indicator_title(indicator_name: str, status: str) -> str:
    label = indicator_name.replace("_", " ").title()
    if status == "green":
        return f"{label} healthy"
    return f"{label} {status}"


def _score_impact_for_status(status: str) -> int:
    return {
        "red": 30,
        "yellow": 15,
        "unknown": 5,
        "unavailable": 10,
    }.get(status, 0)


def _suggest_command(
    indicator_name: str,
    action: str,
    diagnosis: Optional[Dict[str, Any]] = None,
) -> str:
    diagnosis_id = (diagnosis or {}).get("id", "")
    action_lower = action.lower()

    if indicator_name == "shards_availability":
        if "tier" in diagnosis_id or "tier" in action_lower:
            return "elastro cluster allocation"
        if "replica" in action_lower and "index" in action_lower:
            return "elastro health fix"
        return "elastro cluster allocation"
    if indicator_name == "disk":
        return "elastro health report --feature disk --verbose"
    if indicator_name in {"ilm", "data_stream_lifecycle"}:
        return "elastro ilm explain <index>"
    if indicator_name == "repository_integrity" or "snapshot" in action_lower:
        return "elastro snapshot repo list"
    if "routing" in action_lower:
        return "elastro cluster settings --enable-routing all"
    if "replica" in action_lower:
        return "elastro health fix"
    return "elastro health report --verbose"
