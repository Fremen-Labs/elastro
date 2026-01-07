"""Index template management utilities for Elasticsearch."""
from typing import Dict, List, Optional, Any, Union

from pydantic import BaseModel, Field, ConfigDict

from elastro.core.client import ElasticsearchClient
from elastro.core.errors import OperationError


class TemplateDefinition(BaseModel):
    """Pydantic model for index template validation."""
    name: str
    index_patterns: List[str]
    template: Dict[str, Any] = Field(default_factory=dict)
    version: Optional[int] = None
    priority: Optional[int] = None
    composed_of: List[str] = Field(default_factory=list)
    meta: Optional[Dict[str, Any]] = None
    
    model_config = ConfigDict(populate_by_name=True, extra="allow")


class TemplateManager:
    """Manager for Elasticsearch index templates operations.

    This class provides methods to create, get, update, and delete index templates.
    """

    def __init__(self, client: ElasticsearchClient):
        """Initialize the TemplateManager.

        Args:
            client: The Elasticsearch client instance.
        """
        self._client = client
        self._es = client.client

    
    def create(self, name: str, body: Dict[str, Any], template_type: str = "index") -> bool:
        """Create a new template (index or component)."""
        try:
            if template_type == "component":
                resp = self._es.cluster.put_component_template(name=name, body=body)
            else:
                resp = self._es.indices.put_index_template(name=name, body=body)
            return resp.get("acknowledged", False)
        except Exception as e:
            raise OperationError(f"Failed to create {template_type} template {name}: {str(e)}")

    def get(self, name: str, template_type: str = "index") -> Dict[str, Any]:
        """Get a template by name."""
        try:
            if template_type == "component":
                resp = self._es.cluster.get_component_template(name=name)
                # Response format: {'component_templates': [{'name': 'foo', 'component_template': {...}}]}
                if "component_templates" in resp:
                    for t in resp["component_templates"]:
                        if t["name"] == name:
                            return t
                return {}
            else:
                resp = self._es.indices.get_index_template(name=name)
                if "index_templates" in resp:
                     for t in resp["index_templates"]:
                        if t["name"] == name:
                            return t
                return {}
        except Exception as e:
            raise OperationError(f"Failed to get {template_type} template {name}: {str(e)}")

    def delete(self, name: str, template_type: str = "index") -> bool:
        """Delete a template."""
        try:
            if template_type == "component":
                resp = self._es.cluster.delete_component_template(name=name)
            else:
                resp = self._es.indices.delete_index_template(name=name)
            return resp.get("acknowledged", False)
        except Exception as e:
            raise OperationError(f"Failed to delete {template_type} template {name}: {str(e)}")

    def list(self, template_type: str = "index", name: str = None) -> List[Dict[str, Any]]:
        """List templates."""
        try:
            pattern = name if name else "*"
            if template_type == "component":
                resp = self._es.cluster.get_component_template(name=pattern)
                return resp.get("component_templates", [])
            else:
                resp = self._es.indices.get_index_template(name=pattern)
                return resp.get("index_templates", [])
        except Exception as e:
            raise OperationError(f"Failed to list {template_type} templates: {str(e)}")
