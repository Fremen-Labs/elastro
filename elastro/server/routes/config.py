"""
Config routes — /api/config endpoints.
"""

from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException

from elastro.server.schemas import ClusterConfigSchema

router = APIRouter(prefix="/api", tags=["config"])


def config_routes(read_config: Any, write_config: Any, verify_token: Any) -> APIRouter:
    """Bind config routes to the shared config accessor functions."""

    @router.get("/config")
    def get_config(token: str = Depends(verify_token)) -> Dict[str, Any]:
        config = read_config()
        safe_clusters = []
        for c in config.get("clusters", []):
            safe_c = c.copy()
            if "auth" in safe_c:
                if "password" in safe_c["auth"]:
                    safe_c["auth"]["password"] = "******"
                if "api_key" in safe_c["auth"]:
                    safe_c["auth"]["api_key"] = "******"
            safe_clusters.append(safe_c)
        return {"clusters": safe_clusters}

    @router.post("/config/clusters")
    def add_cluster(
        cluster: ClusterConfigSchema, token: str = Depends(verify_token)
    ) -> Dict[str, str]:
        config = read_config()
        clusters = config.get("clusters", [])
        for c in clusters:
            if c["name"] == cluster.name:
                raise HTTPException(
                    status_code=400, detail="Cluster name already exists"
                )
        clusters.append(cluster.model_dump())
        config["clusters"] = clusters
        write_config(config)
        return {"status": "success"}

    return router
