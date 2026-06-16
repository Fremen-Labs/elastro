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
            logger.info(
                "GUI unhealthy indices requested for cluster=%s",
                cluster_name,
            )
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
                    logger.error(
                        "Failed to explain allocation for index=%s: %s",
                        name,
                        e,
                        exc_info=True,
                    )
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
            logger.info(
                "Unhealthy indices complete cluster=%s count=%s",
                cluster_name,
                len(results),
            )
            return {"indices": results}
        except Exception as e:
            logger.error(
                "Unhealthy indices failed for cluster=%s: %s",
                cluster_name,
                e,
                exc_info=True,
            )
            raise HTTPException(status_code=500, detail=str(e)) from e

    @router.post("/clusters/{cluster_name}/indices/{index_name}/fix")
    def fix_index(
        cluster_name: str,
        index_name: str,
        req: IndexFixRequestSchema,
        token: str = Depends(verify_token),
    ) -> Dict[str, Any]:
        target_c = _find_cluster(cluster_name)

        try:
            logger.info(
                "GUI index fix requested cluster=%s index=%s action=%s dry_run=%s",
                cluster_name,
                index_name,
                req.action,
                req.dry_run,
            )
            from elastro.health.audit import HealthAuditLogger

            client = build_es_client(target_c)
            audit = HealthAuditLogger(client, host=str(target_c.get("host", "unknown")))

            from elastro.health.remediation.executor import RemediationExecutor

            action = req.action
            if action == "reroute":
                action = "reroute_failed"

            executor = RemediationExecutor(
                client,
                dry_run=req.dry_run,
                interactive=False,
                api_mode=True,
                audit_logger=audit,
                cluster_name=cluster_name,
            )
            result = executor.execute_action(action, index_name)
            if result.dry_run:
                return {
                    "status": "dry_run",
                    "planned_api_call": result.planned_api_call,
                    "rollback_id": result.rollback_id,
                }
            if not result.success:
                raise HTTPException(status_code=500, detail=result.message)
            return {
                "status": "success",
                "message": result.message,
                "rollback_id": result.rollback_id,
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                "Index fix failed cluster=%s index=%s action=%s: %s",
                cluster_name,
                index_name,
                req.action,
                e,
                exc_info=True,
            )
            raise HTTPException(status_code=500, detail=str(e)) from e

    return router
