"""Cluster inventory metrics for GUI overview and health summary panels."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from elastro.core.logger import get_logger
from elastro.health.shards import format_bytes

logger = get_logger(__name__)


def _safe_count(callable_obj, *, label: str, default: int = 0) -> int:
    try:
        return int(callable_obj())
    except Exception as exc:
        logger.debug("Cluster inventory %s unavailable: %s", label, exc)
        return default


def _count_kibana_objects(es: Any, object_type: str) -> Optional[int]:
    """Count Kibana saved objects when .kibana* indices exist."""
    try:
        indices_response = es.cat.indices(index=".kibana*", format="json", h="index")
        if not isinstance(indices_response, list):
            body = getattr(indices_response, "body", indices_response)
            indices_response = body if isinstance(body, list) else []

        index_names = [
            str(row.get("index", "")).strip()
            for row in indices_response
            if isinstance(row, dict) and str(row.get("index", "")).strip()
        ]
        if not index_names:
            return None

        response = es.count(
            index=",".join(index_names),
            query={"term": {"type": object_type}},
        )
        count = (
            response.get("count")
            if isinstance(response, dict)
            else getattr(response, "body", {}).get("count")
        )
        return int(count or 0)
    except Exception as exc:
        logger.debug(
            "Kibana %s count unavailable: %s",
            object_type,
            exc,
        )
        return None


def fetch_cluster_inventory(es: Any) -> Dict[str, Any]:
    """Collect high-level cluster inventory metrics from Elasticsearch."""
    health = es.cluster.health()
    nodes_info = es.nodes.info()
    node_count = int(nodes_info.get("_nodes", {}).get("total", 0))

    node_roles: Dict[str, int] = {}
    for node_data in nodes_info.get("nodes", {}).values():
        if not isinstance(node_data, dict):
            continue
        for role in node_data.get("roles", ["unknown"]):
            node_roles[str(role)] = node_roles.get(str(role), 0) + 1

    idx_res = es.cat.indices(format="json")
    if not isinstance(idx_res, list):
        body = getattr(idx_res, "body", idx_res)
        idx_res = body if isinstance(body, list) else []

    red_indices = 0
    yellow_indices = 0
    green_indices = 0
    for idx in idx_res:
        if not isinstance(idx, dict):
            continue
        status = str(idx.get("health", "")).lower()
        if status == "red":
            red_indices += 1
        elif status == "yellow":
            yellow_indices += 1
        elif status == "green":
            green_indices += 1

    total_indices = len(idx_res)

    shard_rows = es.cat.shards(format="json", h="index,shard,state")
    if not isinstance(shard_rows, list):
        body = getattr(shard_rows, "body", shard_rows)
        shard_rows = body if isinstance(body, list) else []

    unassigned_shards = 0
    for row in shard_rows:
        if isinstance(row, dict) and str(row.get("state", "")).upper() == "UNASSIGNED":
            unassigned_shards += 1

    cluster_stats = es.cluster.stats()
    indices_stats = (
        cluster_stats.get("indices", {}) if isinstance(cluster_stats, dict) else {}
    )
    docs = indices_stats.get("docs", {}) if isinstance(indices_stats, dict) else {}
    store = indices_stats.get("store", {}) if isinstance(indices_stats, dict) else {}
    total_docs = int(docs.get("count", 0) or 0)
    total_store_bytes = int(store.get("size_in_bytes", 0) or 0)

    data_stream_count = _safe_count(
        lambda: len(
            (
                es.indices.get_data_stream(name="*").get("data_streams", [])
                if isinstance(es.indices.get_data_stream(name="*"), dict)
                else []
            )
        ),
        label="data_streams",
    )

    ilm_count = _safe_count(
        lambda: len(es.ilm.get_lifecycle()),
        label="ilm_policies",
    )

    template_count = 0
    try:
        composable = es.indices.get_index_template(name="*")
        templates = (
            composable.get("index_templates", [])
            if isinstance(composable, dict)
            else []
        )
        template_count += len(templates)
    except Exception as exc:
        logger.debug("Composable index templates unavailable: %s", exc)
    try:
        legacy = es.indices.get_template(name="*")
        if isinstance(legacy, dict):
            template_count += len(legacy)
    except Exception as exc:
        logger.debug("Legacy index templates unavailable: %s", exc)

    repos: List[Dict[str, str]] = []
    try:
        repo_res = es.snapshot.get_repository()
        if isinstance(repo_res, dict):
            for repo_name, repo_data in repo_res.items():
                repos.append(
                    {
                        "name": str(repo_name),
                        "type": str((repo_data or {}).get("type", "unknown")),
                    }
                )
    except Exception as exc:
        logger.debug("Snapshot repositories unavailable: %s", exc)

    dashboard_count = _count_kibana_objects(es, "dashboard")
    visualization_count = _count_kibana_objects(es, "visualization")

    return {
        "health": str(health.get("status", "unknown")),
        "nodes": {"total": node_count, "roles": node_roles},
        "indices": {
            "total": total_indices,
            "green": green_indices,
            "yellow": yellow_indices,
            "red": red_indices,
        },
        "shards": {
            "total": len(shard_rows),
            "unassigned": unassigned_shards,
        },
        "data_streams": {"total": data_stream_count},
        "documents": {"total": total_docs},
        "storage": {
            "total_bytes": total_store_bytes,
            "total_human": format_bytes(total_store_bytes),
        },
        "ilm": {"policy_count": ilm_count},
        "index_templates": {"total": template_count},
        "kibana": {
            "dashboards": dashboard_count,
            "visualizations": visualization_count,
            "available": dashboard_count is not None,
        },
        "backups": {
            "configured": len(repos) > 0,
            "repository_count": len(repos),
            "repositories": repos,
        },
    }
