"""
Cluster routes — /api/clusters endpoints.
"""

from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException

from elastro.core.logger import get_logger
from elastro.server.cluster_inventory import fetch_cluster_inventory
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
            inventory = fetch_cluster_inventory(client.client)

            return {
                "name": target_c["name"],
                "host": target_c["host"],
                "health": inventory["health"],
                "nodes": inventory["nodes"],
                "indices": inventory["indices"],
                "shards": inventory["shards"],
                "data_streams": inventory["data_streams"],
                "documents": inventory["documents"],
                "storage": inventory["storage"],
                "ilm": inventory["ilm"],
                "index_templates": inventory["index_templates"],
                "kibana": inventory["kibana"],
                "backups": inventory["backups"],
            }

        except Exception as e:
            logger.error(f"Failed to fetch details for {cluster_name}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed communicating with Elasticsearch: {str(e)}",
            )

    return router
