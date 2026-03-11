"""
Telemetry ingest command for Elastro CLI.
"""

import rich_click as click
from datetime import datetime, timezone

from elastro.core.client import ElasticsearchClient

@click.group(name="telemetry")
def telemetry_group() -> None:
    """Manage and ingest Agent telemetry."""
    pass

@telemetry_group.command("ingest")
@click.argument("workload_reference")
@click.option("--exec-mins", type=float, default=0.0, help="Execution time in minutes")
@click.option("--elastro-q-ms", type=int, default=0, help="Elastro query latency ms")
@click.option("--q2r-ms", type=int, default=0, help="Question to Reasoning latency ms")
@click.option("--r2l-ms", type=int, default=0, help="Reasoning to Launch latency ms")
@click.option("--plan-ms", type=int, default=0, help="Planning latency ms")
@click.option("--ast-ratio", type=float, default=0.0, help="AST Hit Ratio")
@click.option("--ctx-eff", type=float, default=0.0, help="Context Efficiency")
@click.option("--rel-rate", type=float, default=0.0, help="Reliability Rate")
@click.option("--depth", type=int, default=0, help="Trajectory Depth")
@click.option("--retry", type=int, default=0, help="Retry count")
@click.option("--l7-ms", type=int, default=0, help="L7 Application Latency ms")
@click.option("--l4-ms", type=int, default=0, help="L4 Transport Latency ms")
@click.option("--l3-ms", type=int, default=0, help="L3 Network Latency ms")
@click.option("--l1-ms", type=int, default=0, help="L1/L2 Physical Latency ms")
@click.option("--in-tokens", type=int, default=0, help="Input Tokens")
@click.option("--out-tokens", type=int, default=0, help="Output Tokens")
@click.pass_obj
def ingest_telemetry(
    client: ElasticsearchClient,
    workload_reference: str,
    exec_mins: float,
    elastro_q_ms: int,
    q2r_ms: int,
    r2l_ms: int,
    plan_ms: int,
    ast_ratio: float,
    ctx_eff: float,
    rel_rate: float,
    depth: int,
    retry: int,
    l7_ms: int,
    l4_ms: int,
    l3_ms: int,
    l1_ms: int,
    in_tokens: int,
    out_tokens: int,
) -> None:
    """
    Ingest standardized session telemetry into the deep analytics index.
    
    This command enforces the schema for the Deep Agent Telemetry visualization,
    submitting the performance vector into target index 'agent_telemetry_deep'.
    """
    index_name = "agent_telemetry_deep"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    payload = {
        "timestamp": timestamp,
        "workload_reference": workload_reference,
        "execution_time_minutes": exec_mins,
        "t_elastro_query_ms": elastro_q_ms,
        "t_question_to_reasoning_ms": q2r_ms,
        "t_reasoning_to_launch_ms": r2l_ms,
        "t_planning_ms": plan_ms,
        "ast_hit_ratio": ast_ratio,
        "context_efficiency": ctx_eff,
        "first_pass_reliability_rate": rel_rate,
        "trajectory_depth": depth,
        "retry_count": retry,
        "osi_latency_breakdown": {
            "l7_application_ms": l7_ms,
            "l4_transport_ms": l4_ms,
            "l3_network_ms": l3_ms,
            "l2_l1_physical_ms": l1_ms
        },
        "token_count_query": {
            "input_tokens": in_tokens,
            "output_tokens": out_tokens
        }
    }

    try:
        response = client.index(index=index_name, document=payload)
        click.secho(f">> Sink execution complete for [{workload_reference}]. ID: {response.get('_id', 'unknown')}", fg="green")
    except Exception as e:
        click.secho(f"Failed to ingest telemetry payload: {e}", fg="red", err=True)
        import sys
        sys.exit(1)
