"""Unit tests for remediation planner."""

from unittest.mock import MagicMock, patch

from elastro.health.remediation.models import IndexDiagnosis
from elastro.health.remediation.planner import RemediationPlanner


class TestRemediationPlanner:
    def test_plans_reduce_replicas_for_yellow_index(self):
        index_manager = MagicMock()
        diagnoses = [
            IndexDiagnosis(
                index_name="logs-2024",
                health="yellow",
                suggested_action_id="reduce_replicas",
                suggestion_text="Reduce replicas",
            )
        ]
        with patch(
            "elastro.health.remediation.planner.resolve_replica_target",
            return_value=0,
        ):
            planned = RemediationPlanner.plan_from_diagnoses(
                index_manager,
                diagnoses,
            )
        assert len(planned) == 1
        assert planned[0].action_id == "reduce_replicas"
        assert planned[0].index_name == "logs-2024"
        assert planned[0].target_replicas == 0
        assert "PUT /logs-2024/_settings" in (planned[0].planned_api_call or "")

    def test_deduplicates_cluster_reroute_actions(self):
        index_manager = MagicMock()
        diagnoses = [
            IndexDiagnosis(
                index_name="idx-a",
                health="red",
                suggested_action_id="reroute_failed",
            ),
            IndexDiagnosis(
                index_name="idx-b",
                health="red",
                suggested_action_id="reroute_failed",
            ),
        ]
        planned = RemediationPlanner.plan_from_diagnoses(
            index_manager,
            diagnoses,
        )
        assert len(planned) == 1
        assert planned[0].dedupe_key == "reroute_failed"

    def test_filters_by_index_pattern(self):
        index_manager = MagicMock()
        diagnoses = [
            IndexDiagnosis(
                index_name="logs-2024",
                health="yellow",
                suggested_action_id="reduce_replicas",
            ),
            IndexDiagnosis(
                index_name="metrics-2024",
                health="yellow",
                suggested_action_id="reduce_replicas",
            ),
        ]
        with patch(
            "elastro.health.remediation.planner.resolve_replica_target",
            return_value=0,
        ):
            planned = RemediationPlanner.plan_from_diagnoses(
                index_manager,
                diagnoses,
                index_pattern="logs-*",
            )
        assert len(planned) == 1
        assert planned[0].index_name == "logs-2024"

    def test_filters_by_action(self):
        index_manager = MagicMock()
        diagnoses = [
            IndexDiagnosis(
                index_name="logs-2024",
                health="yellow",
                suggested_action_id="reduce_replicas",
            ),
            IndexDiagnosis(
                index_name="locked-index",
                health="red",
                suggested_action_id="clear_routing_filters",
            ),
        ]
        with patch(
            "elastro.health.remediation.planner.resolve_replica_target",
            return_value=0,
        ):
            planned = RemediationPlanner.plan_from_diagnoses(
                index_manager,
                diagnoses,
                action_filter="clear_routing_filters",
            )
        assert len(planned) == 1
        assert planned[0].action_id == "clear_routing_filters"