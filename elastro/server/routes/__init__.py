"""
Routes __init__ — re-exports all API routers for clean mounting.
"""

from elastro.server.routes.config import router as config_router
from elastro.server.routes.clusters import router as clusters_router
from elastro.server.routes.indices import router as indices_router
from elastro.server.routes.cli import router as cli_router

__all__ = [
    "config_router",
    "clusters_router",
    "indices_router",
    "cli_router",
]
