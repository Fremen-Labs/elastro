"""Pydantic payloads and stable index names for agent helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Literal, Mapping, Optional, Union

from pydantic import BaseModel, Field

AGENT_SEMANTIC_MEMORY = "agent_semantic_memory"
AGENT_TELEMETRY_DEEP = "agent_telemetry_deep"
FLOW_TOOLS = "flow_tools"
FREMEN_CODEBASE_RAG = "fremen_codebase_rag"

_WAKE_MEMORY_FIELDS = ["subject^3", "content", "tags"]
_WAKE_RAG_FIELDS = ["file_path^3", "content", "chunk_name^2"]


def utc_timestamp() -> str:
    """UTC timestamp in the historical agent ingest format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def dump_payload(document: Union[Mapping[str, Any], BaseModel]) -> Dict[str, Any]:
    """Normalize a pydantic model or mapping into an ES document dict."""
    if isinstance(document, BaseModel):
        return document.model_dump(mode="json", exclude_none=True)
    return dict(document)


class MemoryNote(BaseModel):
    """Semantic memory note stored in ``agent_semantic_memory``."""

    timestamp: str
    note_type: Literal["strategic", "tactical"]
    subject: str
    content: str
    tags: List[str] = Field(default_factory=list)


class OsiLatencyBreakdown(BaseModel):
    l7_application_ms: int = 0
    l4_transport_ms: int = 0
    l3_network_ms: int = 0
    l2_l1_physical_ms: int = 0


class TokenCountQuery(BaseModel):
    input_tokens: int = 0
    output_tokens: Optional[int] = None
    bounded_layer: Optional[int] = None


class TelemetryDocument(BaseModel):
    """Deep agent telemetry document written to ``agent_telemetry_deep``."""

    timestamp: str
    workload_reference: str
    execution_time_minutes: float = 0.0
    t_elastro_query_ms: int = 0
    t_question_to_reasoning_ms: int = 0
    t_reasoning_to_launch_ms: int = 0
    t_planning_ms: int = 0
    ast_hit_ratio: float = 0.0
    context_efficiency: float = 0.0
    first_pass_reliability_rate: float = 0.0
    trajectory_depth: int = 0
    retry_count: int = 0
    osi_latency_breakdown: OsiLatencyBreakdown = Field(
        default_factory=OsiLatencyBreakdown
    )
    token_count_query: TokenCountQuery = Field(default_factory=TokenCountQuery)
    provider_model_string: str = "unknown"
    tools_invoked_array: List[str] = Field(default_factory=list)
    rollback_undo_count: int = 0
    diff_drift_ratio: float = 0.0
    deterministic_fallback_rate: float = 0.0
    complexity_score: float = 0.0


class WakeTelemetryDocument(BaseModel):
    """Telemetry recorded by a primed activation wake query."""

    timestamp: str
    workload_reference: str
    t_elastro_query_ms: int
    effective_latency_to_knowing_state_ms: int
    similarity_scores: List[float]
    avg_similarity_score: float
    token_count_query: TokenCountQuery
    ast_hit_ratio: float = 1.0
    trajectory_depth: int
    complexity_score: float


class ToolRecord(BaseModel):
    """Custom toolchain registry document stored in ``flow_tools``."""

    timestamp: str
    tool_name: str
    file_path: str
    purpose: str
    parameters: str
    file_hash: str


class MlDetector(BaseModel):
    function: str
    field_name: Optional[str] = None


class MlAnalysisConfig(BaseModel):
    bucket_span: str = "15m"
    detectors: List[MlDetector]
    influencers: List[str] = Field(default_factory=list)


class MlJobConfig(BaseModel):
    """Anomaly detection job body sent to ``PUT _ml/anomaly_detectors``."""

    description: str
    analysis_config: MlAnalysisConfig
    data_description: Dict[str, str]


class MlDatafeedConfig(BaseModel):
    job_id: str
    indices: List[str]


def wake_search_fields(index: str) -> List[str]:
    """Return multi_match fields for a wake query against ``index``."""
    if index == FREMEN_CODEBASE_RAG:
        return list(_WAKE_RAG_FIELDS)
    return list(_WAKE_MEMORY_FIELDS)


def memory_search_body(
    query: str,
    *,
    note_type: Optional[str] = None,
    size: int = 10,
) -> Dict[str, Any]:
    """BM25 search body for ``agent_semantic_memory``."""
    bool_clause: Dict[str, List[Any]] = {
        "must": [
            {
                "multi_match": {
                    "query": query,
                    "fields": ["subject^2", "content", "tags"],
                }
            }
        ]
    }
    if note_type:
        bool_clause["filter"] = [{"term": {"note_type": note_type}}]
    return {"size": size, "query": {"bool": bool_clause}}


def tactical_prune_query(
    days: int, *, now: Optional[datetime] = None
) -> Dict[str, Any]:
    """delete_by_query body for tactical notes older than ``days``."""
    when = now or datetime.now(timezone.utc)
    cutoff = when - timedelta(days=days)
    cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "query": {
            "bool": {
                "must": [
                    {"term": {"note_type": "tactical"}},
                    {"range": {"timestamp": {"lt": cutoff_str}}},
                ]
            }
        }
    }


def wake_search_body(
    heuristic_query: str,
    *,
    index: str,
    anchor_hash: str = "",
    k: int = 5,
) -> Dict[str, Any]:
    """Bounded activation-wave search body, including the RAG field special case."""
    must_clauses: List[Dict[str, Any]] = [
        {
            "multi_match": {
                "query": heuristic_query,
                "fields": wake_search_fields(index),
            }
        }
    ]
    if anchor_hash:
        must_clauses.append({"term": {"anchor_hash": anchor_hash}})
    return {
        "size": k,
        "query": {
            "function_score": {
                "query": {"bool": {"must": must_clauses}},
                "functions": [
                    {
                        "exp": {
                            "timestamp": {"scale": "7d", "offset": "1d", "decay": 0.5}
                        }
                    }
                ],
                "boost_mode": "multiply",
            }
        },
    }


def tools_search_body(query: str, *, size: int = 10) -> Dict[str, Any]:
    """Search body for the ``flow_tools`` registry."""
    return {
        "size": size,
        "query": {
            "multi_match": {
                "query": query,
                "fields": ["tool_name^3", "purpose^2", "parameters"],
            }
        },
    }
