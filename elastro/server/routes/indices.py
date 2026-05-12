"""
Index routes — /api/clusters/{cluster_name}/indices endpoints.
"""

from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException

from elastro.core.logger import get_logger
from elastro.server.schemas import IndexFixRequestSchema
from elastro.server.services import build_es_client

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["indices"])


def index_routes(read_config: Any, verify_token: Any) -> APIRouter:
    """Bind index routes to shared config accessor and auth functions."""

    def _find_cluster(cluster_name: str) -> Dict[str, Any]:
        """Locate a cluster config by name or raise 404."""
        config = read_config()
        target_c = next(
            (c for c in config.get("clusters", []) if c["name"] == cluster_name),
            None,
        )
        if not target_c:
            raise HTTPException(status_code=404, detail="Cluster not found")
        return target_c

    @router.get("/clusters/{cluster_name}/indices/unhealthy")
    def get_unhealthy_indices(
        cluster_name: str, token: str = Depends(verify_token)
    ) -> Dict[str, Any]:
        target_c = _find_cluster(cluster_name)

        try:
            client = build_es_client(target_c)

            from elastro.core.index import IndexManager

            idx_mgr = IndexManager(client)

            indices = idx_mgr.list()
            unhealthy = [
                idx
                for idx in indices
                if idx.get("health", "green") in ["yellow", "red"]
            ]

            results = []
            for idx in unhealthy:
                name = str(idx.get("index", ""))
                if not name:
                    continue
                try:
                    explain = idx_mgr.allocation_explain(name)
                    unassigned = explain.get("unassigned_info", {})

                    routing_filter_fault = False
                    explanation_parts = []
                    for node_decision in explain.get("node_allocation_decisions", []):
                        for decider in node_decision.get("deciders", []):
                            if decider.get("decision") == "NO":
                                msg = decider.get("explanation", "").strip()
                                if msg and msg not in explanation_parts:
                                    explanation_parts.append(msg)

                            if decider.get(
                                "decider"
                            ) == "filter" and "index.routing.allocation" in decider.get(
                                "explanation", ""
                            ):
                                routing_filter_fault = True

                    alloc_explanation = explain.get("allocate_explanation", "")
                    if (
                        "Elasticsearch isn't allowed to allocate this shard"
                        in alloc_explanation
                        and explanation_parts
                    ):
                        alloc_explanation = "Allocation blocked: " + " | ".join(
                            explanation_parts
                        )
                    elif not alloc_explanation:
                        alloc_explanation = "No explanation"

                    results.append(
                        {
                            "index": name,
                            "health": idx.get("health"),
                            "status": idx.get("status"),
                            "allocate_explanation": alloc_explanation,
                            "reason": unassigned.get("reason", "UNKNOWN"),
                            "routing_filter_fault": routing_filter_fault,
                        }
                    )
                except Exception as e:
                    logger.error(f"Failed to explain {name}: {e}")
                    results.append(
                        {
                            "index": name,
                            "health": idx.get("health"),
                            "status": idx.get("status"),
                            "allocate_explanation": "Failed to fetch explanation",
                            "reason": "ERROR",
                            "routing_filter_fault": False,
                        }
                    )
            return {"indices": results}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/clusters/{cluster_name}/indices/{index_name}/fix")
    def fix_index(
        cluster_name: str,
        index_name: str,
        req: IndexFixRequestSchema,
        token: str = Depends(verify_token),
    ) -> Dict[str, Any]:
        target_c = _find_cluster(cluster_name)

        try:
            client = build_es_client(target_c)

            from elastro.core.index import IndexManager

            idx_mgr = IndexManager(client)

            if req.action == "reduce_replicas":
                payload = {
                    "index": {
                        "number_of_replicas": 0,
                        "auto_expand_replicas": "false",
                    }
                }
                try:
                    idx_mgr.update(index_name, payload)
                except Exception:
                    client.client.indices.put_settings(
                        index=index_name,
                        body=payload,
                        allow_no_indices=False,
                        expand_wildcards="all",
                        ignore_unavailable=True,
                    )

                return {
                    "status": "success",
                    "message": f"Replicas reduced to 0 and auto-expand disabled for {index_name}",
                }
            elif req.action == "reroute":
                idx_mgr.reroute(retry_failed=True)
                return {
                    "status": "success",
                    "message": "Cluster rerouted successfully",
                }
            elif req.action == "clear_routing_filters":
                settings_payload = {
                    "routing.allocation.require._name": None,
                    "routing.allocation.include._name": None,
                    "routing.allocation.exclude._name": None,
                    "routing.allocation.require.*": None,
                    "routing.allocation.include.*": None,
                    "routing.allocation.exclude.*": None,
                }
                idx_mgr.update(index_name, {"index": settings_payload})
                return {
                    "status": "success",
                    "message": f"Custom routing allocation filters cleared for {index_name}",
                }
            else:
                raise HTTPException(status_code=400, detail="Unknown action")

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return router
