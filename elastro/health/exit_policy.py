"""Health command exit-code policy for CI and monitoring gates."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Iterable, List, Optional

from elastro.health.models import Finding, FindingStatus
from elastro.health.remediation.models import FixRunResult


class FailOn(str, Enum):
    """Threshold for when a health command should exit with code 2."""

    GREEN = "green"
    YELLOW = "yellow"
    WARN = "warn"
    FAIL = "fail"


FAIL_ON_CHOICES = [item.value for item in FailOn]

_LINT_SKIP_IDS = frozenset({"lint.categories_skipped"})
_CLUSTER_STATUS_RANK = {"red": 0, "yellow": 1, "green": 2}


def _meets_wait_status(actual: Optional[str], required: Optional[str]) -> bool:
    """Return True when actual cluster status satisfies wait_for_status semantics."""
    if not required or not actual:
        return True
    actual_rank = _CLUSTER_STATUS_RANK.get(actual)
    required_rank = _CLUSTER_STATUS_RANK.get(required)
    if actual_rank is None or required_rank is None:
        return actual == required
    return actual_rank >= required_rank


def actionable_findings(findings: Iterable[Finding]) -> List[Finding]:
    return [
        finding
        for finding in findings
        if finding.id not in _LINT_SKIP_IDS
        and finding.status
        not in (FindingStatus.SKIPPED, FindingStatus.UNKNOWN, FindingStatus.PASS)
    ]


def _has_status(findings: Iterable[Finding], status: FindingStatus) -> bool:
    return any(finding.status == status for finding in findings)


def is_degraded(
    *,
    fail_on: FailOn | str,
    overall_status: FindingStatus = FindingStatus.UNKNOWN,
    overall_score: int = 100,
    findings: Optional[List[Finding]] = None,
    extra_signals: Optional[Dict[str, Any]] = None,
) -> bool:
    """Return True when health signals exceed the configured ``fail_on`` threshold."""
    threshold = FailOn(fail_on) if isinstance(fail_on, str) else fail_on
    actionable = actionable_findings(findings or [])
    signals = extra_signals or {}

    has_fail = _has_status(actionable, FindingStatus.FAIL)
    has_warn = _has_status(actionable, FindingStatus.WARN)
    cluster_status = signals.get("cluster_status")
    unassigned_shards = int(signals.get("unassigned_shards") or 0)
    wait_status = signals.get("wait_status")
    timed_out = bool(signals.get("timed_out"))

    if wait_status:
        if timed_out:
            return True
        if cluster_status and not _meets_wait_status(cluster_status, wait_status):
            return True

    if threshold == FailOn.FAIL:
        return (
            overall_status == FindingStatus.FAIL
            or has_fail
            or cluster_status == "red"
            or overall_score < 50
        )

    if threshold == FailOn.WARN:
        return (
            is_degraded(
                fail_on=FailOn.FAIL,
                overall_status=overall_status,
                overall_score=overall_score,
                findings=findings,
                extra_signals={
                    key: value
                    for key, value in signals.items()
                    if key not in {"wait_status", "timed_out"}
                },
            )
            or overall_status == FindingStatus.WARN
            or has_warn
            or unassigned_shards > 0
        )

    if threshold == FailOn.YELLOW:
        return (
            is_degraded(
                fail_on=FailOn.WARN,
                overall_status=overall_status,
                overall_score=overall_score,
                findings=findings,
                extra_signals={
                    key: value
                    for key, value in signals.items()
                    if key not in {"wait_status", "timed_out"}
                },
            )
            or overall_score < 90
            or cluster_status in {"yellow", "red"}
        )

    if threshold == FailOn.GREEN:
        return (
            overall_score < 90
            or overall_status in (FindingStatus.WARN, FindingStatus.FAIL)
            or has_fail
            or has_warn
            or (cluster_status is not None and cluster_status != "green")
            or unassigned_shards > 0
        )

    return False


def resolve_exit_code(
    *,
    fail_on: FailOn | str = FailOn.FAIL,
    overall_status: FindingStatus = FindingStatus.UNKNOWN,
    overall_score: int = 100,
    findings: Optional[List[Finding]] = None,
    extra_signals: Optional[Dict[str, Any]] = None,
) -> int:
    """Return ``0`` when healthy, ``2`` when degraded per ``fail_on``."""
    if is_degraded(
        fail_on=fail_on,
        overall_status=overall_status,
        overall_score=overall_score,
        findings=findings,
        extra_signals=extra_signals,
    ):
        return 2
    return 0


def resolve_fix_exit_code(fix_result: FixRunResult) -> int:
    """Return ``3`` when remediation partially failed, else ``0``."""
    if fix_result.dry_run or fix_result.plan_only:
        return 0

    executed = [result for result in fix_result.results if result.executed]
    if not executed:
        return 0

    if any(not result.success for result in executed):
        return 3
    return 0


def combine_exit_codes(*codes: int) -> int:
    """Pick the most severe non-zero exit code.

    Health degradation (``2``) takes precedence over remediation failure (``3``)
    so CI health gates still fail when the cluster is unhealthy after a partial fix.
    """
    non_zero = [code for code in codes if code > 0]
    if not non_zero:
        return 0
    if 2 in non_zero:
        return 2
    return max(non_zero)
