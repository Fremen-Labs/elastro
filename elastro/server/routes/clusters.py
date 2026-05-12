"""
Cluster routes — /api/clusters endpoints.
"""

from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException

from elastro.core.logger import get_logger
from elastro.server.services import build_es_client, parse_index_size

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["clusters"])


def cluster_routes(read_config: Any, verify_token: Any) -> APIRouter:
    """Bind cluster routes to the shared config accessor and auth functions."""

    @router.get("/clusters")
    def get_clusters_health(
        token: str = Depends(verify_token),
    ) -> Dict[str, Any]:
        config = read_config()
        results = []

        for c in config.get("clusters", []):
            try:
                client = build_es_client(c)
                es = client.client

                health = es.cluster.health()
                idx_res = es.cat.indices(format="json")

                unstable: List[Dict[str, Any]] = []
                largest_idx_name = "N/A"
                largest_idx_size = -1
                largest_idx_raw = "0b"

                for idx in idx_res:
                    if not isinstance(idx, dict):
                        continue
                    if idx.get("health") in ["yellow", "red"]:
                        unstable.append(
                            {
                                "index": idx.get("index", "unknown"),
                                "health": idx.get("health"),
                                "docs": idx.get("docs.count", "0"),
                            }
                        )

                    raw_size = idx.get("store.size", "0b")
                    size_bytes, _ = parse_index_size(raw_size)

                    if size_bytes > largest_idx_size:
                        largest_idx_size = size_bytes
                        largest_idx_name = idx.get("index", "Unknown")
                        largest_idx_raw = idx.get("store.size", "0b")

                results.append(
                    {
                        "name": c["name"],
                        "host": c["host"],
                        "health": health["status"],
                        "index_count": len(idx_res),
                        "largest_index": {
                            "name": largest_idx_name,
                            "size": largest_idx_raw,
                        },
                        "unstable_indices": unstable,
                    }
                )

            except Exception as e:
                logger.error(f"Failed to connect to {c['name']}: {str(e)}")
                results.append(
                    {
                        "name": c["name"],
                        "host": c["host"],
                        "health": "offline",
                        "index_count": 0,
                        "largest_index": {"name": "N/A", "size": "0B"},
                        "unstable_indices": [],
                    }
                )

        return {"clusters": results}

    @router.get("/cluster/{cluster_name}")
    def get_cluster_details(
        cluster_name: str, token: str = Depends(verify_token)
    ) -> Dict[str, Any]:
        config = read_config()
        target_c = None

        for c in config.get("clusters", []):
            if c["name"] == cluster_name:
                target_c = c
                break

        if not target_c:
            raise HTTPException(
                status_code=404,
                detail=f"Cluster '{cluster_name}' not found in configuration.",
            )

        try:
            client = build_es_client(target_c)
            es = client.client

            # Fetch detailed metrics
            health = es.cluster.health()

            # Node stats
            nodes_info = es.nodes.info()
            node_count = nodes_info.get("_nodes", {}).get("total", 0)

            node_roles: Dict[str, int] = {}
            for node_id, node_data in nodes_info.get("nodes", {}).items():
                roles = node_data.get("roles", ["unknown"])
                for r in roles:
                    node_roles[r] = node_roles.get(r, 0) + 1

            # ILM Policies
            try:
                ilm_policies = es.ilm.get_lifecycle()
                ilm_count = len(ilm_policies)
            except Exception as e:
                logger.warning(f"Could not fetch ILM for {cluster_name}: {e}")
                ilm_count = 0

            # Snapshots / Backups
            repos = []
            try:
                repo_res = es.snapshot.get_repository()
                for r_name, r_data in repo_res.items():
                    repos.append(
                        {"name": r_name, "type": r_data.get("type", "unknown")}
                    )
            except Exception as e:
                logger.warning(f"Could not fetch Repos for {cluster_name}: {e}")

            # Indices detailed summary
            idx_res = es.cat.indices(format="json")
            red_indices = 0
            yellow_indices = 0
            total_indices = len(idx_res)

            for idx in idx_res:
                if not isinstance(idx, dict):
                    continue
                if idx.get("health") == "red":
                    red_indices += 1
                elif idx.get("health") == "yellow":
                    yellow_indices += 1

            return {
                "name": target_c["name"],
                "host": target_c["host"],
                "health": health["status"],
                "nodes": {"total": node_count, "roles": node_roles},
                "indices": {
                    "total": total_indices,
                    "yellow": yellow_indices,
                    "red": red_indices,
                },
                "ilm": {"policy_count": ilm_count},
                "backups": {"configured": len(repos) > 0, "repositories": repos},
            }

        except Exception as e:
            logger.error(f"Failed to fetch details for {cluster_name}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed communicating with Elasticsearch: {str(e)}",
            )

    return router
