"""
Pydantic request/response schemas for the Elastro GUI API.
"""

from typing import Optional
from pydantic import BaseModel


class AuthSchema(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    api_key: Optional[str] = None


class ClusterConfigSchema(BaseModel):
    name: str
    host: str
    auth: AuthSchema


class ClusterCLIRequestSchema(BaseModel):
    command: str
    stdin: Optional[str] = None


class IndexFixRequestSchema(BaseModel):
    action: str
    dry_run: bool = True


class HealthFixRequestSchema(BaseModel):
    finding_id: str = ""
    action: str
    dry_run: bool = True
    force: bool = False
    index_name: Optional[str] = None
