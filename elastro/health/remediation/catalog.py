"""Single source of truth for executable remediation actions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Optional

from elastro.core.index import IndexManager
from elastro.health.models import RemediationSafety
from elastro.health.remediation.actions import (
    clear_routing_filters,
    planned_clear_routing_filters,
    planned_reduce_replicas,
    planned_reroute_failed,
    reduce_replicas,
    reroute_failed,
)


@dataclass(frozen=True)
class CatalogEntry:
    id: str
    label: str
    safety: RemediationSafety
    command: str
    planned: Callable[..., str]
    execute: Callable[..., str]
    requires_index: bool = True
    rollback_command: str = "elastro health rollback apply --id {rollback_id}"


class RemediationCatalog:
    """Registry of supported remediation handlers."""

    _ENTRIES: Dict[str, CatalogEntry] = {
        "reduce_replicas": CatalogEntry(
            id="reduce_replicas",
            label="Reduce replicas to safe target",
            safety=RemediationSafety.DESTRUCTIVE,
            command="elastro health fix",
            planned=planned_reduce_replicas,
            execute=lambda mgr, index_name, **kwargs: reduce_replicas(
                mgr,
                index_name,
                api_mode=kwargs.get("api_mode", False),
                target_replicas=kwargs.get("target_replicas"),
            ),
        ),
        "reroute_failed": CatalogEntry(
            id="reroute_failed",
            label="Retry failed shard allocation",
            safety=RemediationSafety.CONFIRM,
            command="elastro health fix",
            planned=planned_reroute_failed,
            execute=lambda mgr, index_name, **kwargs: reroute_failed(mgr),
            requires_index=False,
        ),
        "clear_routing_filters": CatalogEntry(
            id="clear_routing_filters",
            label="Clear routing allocation filters",
            safety=RemediationSafety.CONFIRM,
            command="elastro health fix",
            planned=planned_clear_routing_filters,
            execute=lambda mgr, index_name, **kwargs: clear_routing_filters(
                mgr, index_name
            ),
        ),
    }

    @classmethod
    def get(cls, action_id: str) -> Optional[CatalogEntry]:
        return cls._ENTRIES.get(action_id)

    @classmethod
    def list_ids(cls) -> list[str]:
        return list(cls._ENTRIES.keys())

    @classmethod
    def default_confirm(cls, action_id: str) -> bool:
        """Return whether an action should default to confirmed execution."""
        entry = cls.get(action_id)
        if entry is None:
            return False
        return entry.safety in {RemediationSafety.OBSERVE, RemediationSafety.SUGGEST}

    @classmethod
    def planned_call(
        cls,
        action_id: str,
        index_name: Optional[str] = None,
        *,
        api_mode: bool = False,
        target_replicas: Optional[int] = None,
    ) -> str:
        entry = cls._ENTRIES[action_id]
        if entry.requires_index:
            if not index_name:
                raise ValueError(f"Action {action_id} requires an index name")
            if action_id == "reduce_replicas":
                return entry.planned(
                    index_name,
                    api_mode=api_mode,
                    target_replicas=target_replicas,
                )
            return entry.planned(index_name)
        return entry.planned(index_name)

    @classmethod
    def execute(
        cls,
        action_id: str,
        index_manager: IndexManager,
        index_name: Optional[str] = None,
        *,
        api_mode: bool = False,
        target_replicas: Optional[int] = None,
    ) -> str:
        entry = cls._ENTRIES[action_id]
        if entry.requires_index:
            if not index_name:
                raise ValueError(f"Action {action_id} requires an index name")
            return entry.execute(
                index_manager,
                index_name,
                api_mode=api_mode,
                target_replicas=target_replicas,
            )
        return entry.execute(
            index_manager,
            index_name or "",
            api_mode=api_mode,
            target_replicas=target_replicas,
        )

    @classmethod
    def triggers_remediation_scan(cls, command: Optional[str]) -> bool:
        """Return True when a finding command should launch index remediation."""
        if not command:
            return False
        normalized = command.strip().lower()
        return normalized in {
            "elastro health fix",
            "elastro health assess --fix",
            "elastro index fix",
            "elastro cluster allocation",
        }