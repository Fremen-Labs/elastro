"""Unit tests for remediation safety gates."""

import pytest

from elastro.health.models import RemediationSafety
from elastro.health.remediation.models import PlannedAction
from elastro.health.remediation.safety import (
    RemediationSafetyGate,
    can_auto_confirm,
    refusal_message,
    requires_force,
)


class TestRemediationSafety:
    def test_destructive_requires_force_with_yes(self):
        assert requires_force(RemediationSafety.DESTRUCTIVE, auto_yes=True)
        assert not requires_force(RemediationSafety.CONFIRM, auto_yes=True)

    def test_can_auto_confirm_destructive_only_with_force(self):
        assert not can_auto_confirm(
            RemediationSafety.DESTRUCTIVE,
            auto_yes=True,
            force=False,
        )
        assert can_auto_confirm(
            RemediationSafety.DESTRUCTIVE,
            auto_yes=True,
            force=True,
        )

    def test_refusal_message_for_destructive_without_force(self):
        planned = PlannedAction(
            action_id="reduce_replicas",
            label="Reduce replicas",
            safety=RemediationSafety.DESTRUCTIVE,
            impact="test",
            index_name="logs-2024",
        )
        message = refusal_message(
            planned,
            auto_yes=True,
            force=False,
            interactive=False,
        )
        assert message is not None
        assert "--force" in message

    def test_gate_blocks_non_interactive_confirm_without_yes(self):
        planned = PlannedAction(
            action_id="reroute_failed",
            label="Retry allocation",
            safety=RemediationSafety.CONFIRM,
            impact="load",
        )
        gate = RemediationSafetyGate(
            dry_run=False,
            interactive=False,
            auto_yes=False,
            force=False,
        )
        decision = gate.decide(planned)
        assert decision.execute is False
        assert decision.message is not None

    def test_gate_auto_confirms_with_yes_for_confirm_actions(self):
        planned = PlannedAction(
            action_id="reroute_failed",
            label="Retry allocation",
            safety=RemediationSafety.CONFIRM,
            impact="load",
        )
        gate = RemediationSafetyGate(
            dry_run=False,
            interactive=False,
            auto_yes=True,
            force=False,
        )
        decision = gate.decide(planned)
        assert decision.execute is True

    def test_gate_typed_confirm_for_destructive(self):
        planned = PlannedAction(
            action_id="reduce_replicas",
            label="Reduce replicas",
            safety=RemediationSafety.DESTRUCTIVE,
            impact="ha loss",
            index_name="logs-2024",
        )
        gate = RemediationSafetyGate(
            dry_run=False,
            interactive=True,
            confirm=lambda _prompt, _default: True,
            prompt=lambda _message: "logs-2024",
        )
        decision = gate.decide(planned)
        assert decision.execute is True

    def test_gate_rejects_typed_confirm_mismatch(self):
        planned = PlannedAction(
            action_id="reduce_replicas",
            label="Reduce replicas",
            safety=RemediationSafety.DESTRUCTIVE,
            impact="ha loss",
            index_name="logs-2024",
        )
        gate = RemediationSafetyGate(
            dry_run=False,
            interactive=True,
            confirm=lambda _prompt, _default: True,
            prompt=lambda _message: "wrong-name",
        )
        decision = gate.decide(planned)
        assert decision.execute is False
        assert "did not match" in (decision.message or "")