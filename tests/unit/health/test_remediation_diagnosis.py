"""Unit tests for remediation diagnosis helpers."""

from elastro.health.remediation.diagnosis import (
    detect_routing_filter_fault,
    suggest_action_id,
)


class TestSuggestActionId:
    def test_yellow_replica_same_node(self):
        action_id, suggestion = suggest_action_id(
            health="yellow",
            reason="REPLICA_ADDED",
            allocate_explanation="cannot allocate replica on same node",
            routing_filter_fault=False,
        )
        assert action_id == "reduce_replicas"
        assert suggestion is not None

    def test_allocation_failed_reroute(self):
        action_id, _ = suggest_action_id(
            health="red",
            reason="ALLOCATION_FAILED",
            allocate_explanation="failed after max retries",
            routing_filter_fault=False,
        )
        assert action_id == "reroute_failed"

    def test_routing_filter_clear(self):
        action_id, _ = suggest_action_id(
            health="yellow",
            reason="INDEX_CREATED",
            allocate_explanation="blocked by filters",
            routing_filter_fault=True,
        )
        assert action_id == "clear_routing_filters"

    def test_no_action_for_unknown_case(self):
        action_id, suggestion = suggest_action_id(
            health="yellow",
            reason="INDEX_CREATED",
            allocate_explanation="waiting for shard",
            routing_filter_fault=False,
        )
        assert action_id is None
        assert suggestion is None


class TestDetectRoutingFilterFault:
    def test_detects_filter_decider(self):
        explain = {
            "node_allocation_decisions": [
                {
                    "deciders": [
                        {
                            "decider": "filter",
                            "explanation": "index.routing.allocation.exclude._name blocks",
                        }
                    ]
                }
            ]
        }
        assert detect_routing_filter_fault(explain) is True

    def test_returns_false_without_filter(self):
        explain = {
            "node_allocation_decisions": [
                {"deciders": [{"decider": "disk", "explanation": "not enough disk"}]}
            ]
        }
        assert detect_routing_filter_fault(explain) is False
