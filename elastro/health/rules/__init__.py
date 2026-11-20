"""Custom health rules beyond native Elasticsearch indicators."""

from elastro.health.rules.apm_beats import (
    apm_beats_shard_imbalance_findings,
    apm_data_stream_findings,
    apm_ilm_phase_lag_findings,
    apm_rejection_findings,
    beats_ilm_findings,
)
from elastro.health.rules.engine import RuleContext, RuleEngine
from elastro.health.rules.hotspots import hotspot_findings, hotspot_variance
from elastro.health.rules.jvm import jvm_pressure_findings, jvm_rule
from elastro.health.rules.mapping_explosion import mapping_explosion_findings
from elastro.health.rules.oversharding import oversharding_findings
from elastro.health.rules.persistent_yellow import persistent_yellow_findings
from elastro.health.rules.replica import replica_misconfig_findings

__all__ = [
    "RuleContext",
    "RuleEngine",
    "hotspot_findings",
    "hotspot_variance",
    "jvm_pressure_findings",
    "jvm_rule",
    "mapping_explosion_findings",
    "oversharding_findings",
    "persistent_yellow_findings",
    "replica_misconfig_findings",
    "apm_data_stream_findings",
    "beats_ilm_findings",
    "apm_rejection_findings",
    "apm_beats_shard_imbalance_findings",
    "apm_ilm_phase_lag_findings",
]
