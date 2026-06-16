"""Unit tests for health exit-code policy."""

import pytest

from elastro.health.exit_policy import (
    FailOn,
    combine_exit_codes,
    is_degraded,
    resolve_exit_code,
    resolve_fix_exit_code,
)
from elastro.health.models import Finding, FindingStatus, Severity
from elastro.health.remediation.models import FixRunResult, RemediationResult


def _finding(status: FindingStatus) -> Finding:
    return Finding(
        id="test.finding",
        category="test",
        title="Test finding",
        status=status,
        severity=Severity.MEDIUM,
        summary="summary",
    )


class TestIsDegraded:
    def test_fail_threshold_ignores_warn_score(self):
        assert not is_degraded(
            fail_on=FailOn.FAIL,
            overall_status=FindingStatus.WARN,
            overall_score=80,
            findings=[_finding(FindingStatus.WARN)],
        )

    def test_fail_threshold_triggers_on_fail_status(self):
        assert is_degraded(
            fail_on=FailOn.FAIL,
            overall_status=FindingStatus.FAIL,
            overall_score=30,
        )

    def test_warn_threshold_triggers_on_warn_finding(self):
        assert is_degraded(
            fail_on=FailOn.WARN,
            overall_status=FindingStatus.PASS,
            overall_score=95,
            findings=[_finding(FindingStatus.WARN)],
        )

    def test_warn_threshold_triggers_on_unassigned_shards(self):
        assert is_degraded(
            fail_on=FailOn.WARN,
            extra_signals={"unassigned_shards": 2},
        )

    def test_yellow_threshold_triggers_on_cluster_yellow(self):
        assert is_degraded(
            fail_on=FailOn.YELLOW,
            overall_status=FindingStatus.PASS,
            overall_score=95,
            extra_signals={"cluster_status": "yellow"},
        )

    def test_green_threshold_requires_pristine_cluster(self):
        assert is_degraded(
            fail_on=FailOn.GREEN,
            overall_status=FindingStatus.WARN,
            overall_score=95,
            extra_signals={"cluster_status": "green"},
        )

    def test_wait_timeout_is_degraded(self):
        assert is_degraded(
            fail_on=FailOn.FAIL,
            extra_signals={
                "cluster_status": "yellow",
                "wait_status": "green",
                "timed_out": True,
            },
        )

    def test_wait_yellow_satisfied_by_green_cluster(self):
        assert not is_degraded(
            fail_on=FailOn.FAIL,
            extra_signals={
                "cluster_status": "green",
                "wait_status": "yellow",
                "timed_out": False,
            },
        )

    def test_wait_green_not_satisfied_by_yellow_cluster(self):
        assert is_degraded(
            fail_on=FailOn.FAIL,
            extra_signals={
                "cluster_status": "yellow",
                "wait_status": "green",
                "timed_out": False,
            },
        )

    def test_fail_on_green_allows_unknown_status_with_high_score(self):
        assert not is_degraded(
            fail_on=FailOn.GREEN,
            overall_status=FindingStatus.UNKNOWN,
            overall_score=95,
            extra_signals={"cluster_status": "green"},
        )


class TestResolveExitCode:
    def test_returns_zero_when_healthy(self):
        assert (
            resolve_exit_code(
                fail_on=FailOn.FAIL,
                overall_status=FindingStatus.PASS,
                overall_score=95,
            )
            == 0
        )

    def test_returns_two_when_degraded(self):
        assert (
            resolve_exit_code(
                fail_on=FailOn.WARN,
                findings=[_finding(FindingStatus.WARN)],
            )
            == 2
        )


class TestResolveFixExitCode:
    def test_dry_run_never_fails(self):
        result = FixRunResult(
            dry_run=True,
            results=[
                RemediationResult(
                    action_id="reduce_replicas",
                    success=False,
                    executed=True,
                    message="failed",
                )
            ],
        )
        assert resolve_fix_exit_code(result) == 0

    def test_partial_failure_returns_three(self):
        result = FixRunResult(
            results=[
                RemediationResult(
                    action_id="reduce_replicas",
                    success=True,
                    executed=True,
                    message="ok",
                ),
                RemediationResult(
                    action_id="reroute_failed",
                    success=False,
                    executed=True,
                    message="failed",
                ),
            ]
        )
        assert resolve_fix_exit_code(result) == 3

    def test_blocked_without_execution_returns_zero(self):
        result = FixRunResult(blocked=["needs --force"])
        assert resolve_fix_exit_code(result) == 0


@pytest.mark.parametrize(
    ("codes", "expected"),
    [
        ((0, 0), 0),
        ((0, 2), 2),
        ((2, 3), 2),
        ((0, 3), 3),
    ],
)
def test_combine_exit_codes(codes, expected):
    assert combine_exit_codes(*codes) == expected
