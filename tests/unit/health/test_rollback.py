"""Unit tests for remediation rollback store."""

import os
from unittest.mock import MagicMock

from elastro.health.remediation.rollback import (
    RollbackRecord,
    RollbackStore,
    apply_rollback,
    capture_index_settings,
    create_rollback_record,
)


class TestRollbackStore:
    def test_rejects_invalid_rollback_id(self, tmp_path):
        store = RollbackStore(root=tmp_path)
        assert store.get("../etc/passwd") is None
        assert store.get("rb-test") is None

    def test_save_and_get_round_trip(self, tmp_path):
        store = RollbackStore(root=tmp_path)
        record = create_rollback_record(
            session_id="sess-1",
            action_id="reduce_replicas",
            index_name="logs-2024",
            before={"index": {"number_of_replicas": 1}},
        )
        store.save(record)
        loaded = store.get(record.rollback_id)
        assert loaded is not None
        assert loaded.index_name == "logs-2024"
        assert loaded.before["index"]["number_of_replicas"] == 1

    def test_save_sets_restrictive_permissions(self, tmp_path):
        store = RollbackStore(root=tmp_path)
        record = create_rollback_record(
            session_id="sess-1",
            action_id="reduce_replicas",
            index_name="logs-2024",
            before={"index": {"number_of_replicas": 1}},
        )
        store.save(record)
        path = tmp_path / f"{record.rollback_id}.json"
        assert (path.stat().st_mode & 0o777) == 0o600


class TestRollbackHelpers:
    def test_capture_index_settings_extracts_replica_count(self):
        manager = MagicMock()
        manager.get.return_value = {
            "logs-2024": {
                "settings": {
                    "index": {
                        "number_of_replicas": "2",
                        "auto_expand_replicas": "0-1",
                    }
                }
            }
        }
        captured = capture_index_settings(manager, "logs-2024")
        assert captured == {
            "index": {
                "number_of_replicas": "2",
                "auto_expand_replicas": "0-1",
            }
        }

    def test_apply_rollback_restores_settings(self):
        manager = MagicMock()
        record = RollbackRecord(
            rollback_id="rb-550e8400-e29b-41d4-a716-446655440000",
            session_id="sess-1",
            action_id="reduce_replicas",
            index_name="logs-2024",
            before={"index": {"number_of_replicas": 1}},
        )
        message = apply_rollback(manager, record, dry_run=False)
        manager.update.assert_called_once_with(
            "logs-2024",
            {"index": {"number_of_replicas": 1}},
        )
        assert "Restored settings" in message

    def test_apply_rollback_dry_run_skips_update(self):
        manager = MagicMock()
        record = RollbackRecord(
            rollback_id="rb-550e8400-e29b-41d4-a716-446655440000",
            session_id="sess-1",
            action_id="reduce_replicas",
            index_name="logs-2024",
            before={"index": {"number_of_replicas": 1}},
        )
        message = apply_rollback(manager, record, dry_run=True)
        manager.update.assert_not_called()
        assert "Would restore settings" in message