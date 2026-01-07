"""
ILM (Index Lifecycle Management) module.

This module provides functionality for managing Index Lifecycle Policies.
"""

from typing import Dict, List, Any, Optional
from elastro.core.client import ElasticsearchClient
from elastro.core.errors import OperationError, ValidationError
from elastro.core.logger import get_logger

logger = get_logger(__name__)


class IlmManager:
    """
    Manager for Index Lifecycle Management (ILM) operations.
    """

    def __init__(self, client: ElasticsearchClient):
        """
        Initialize the ILM manager.

        Args:
            client: ElasticsearchClient instance
        """
        self.client = client
        self._client = client

    def list_policies(self) -> List[Dict[str, Any]]:
        """
        List all ILM policies.

        Returns:
            List of policy definitions.
        """
        try:
            logger.debug("Listing ILM policies")
            response = self.client.client.ilm.get_lifecycle()
            body = response.body if hasattr(response, 'body') else dict(response)
            
            # Response is a dict {policy_name: {policy_def...}}
            policies = []
            for name, details in body.items():
                details['name'] = name
                policies.append(details)
            return policies
        except Exception as e:
            logger.error(f"Failed to list ILM policies: {str(e)}")
            raise OperationError(f"Failed to list ILM policies: {str(e)}")

    def get_policy(self, name: str) -> Dict[str, Any]:
        """
        Get a specific ILM policy.

        Args:
            name: Policy name

        Returns:
            Policy definition
        """
        if not name:
            raise ValidationError("Policy name is required")

        try:
            logger.debug(f"Getting ILM policy '{name}'")
            response = self.client.client.ilm.get_lifecycle(name=name)
            body = response.body if hasattr(response, 'body') else dict(response)
            
            if name in body:
                return body[name]
            return body
        except Exception as e:
            logger.error(f"Failed to get ILM policy '{name}': {str(e)}")
            raise OperationError(f"Failed to get ILM policy '{name}': {str(e)}")

    def create_policy(self, name: str, policy: Dict[str, Any]) -> bool:
        """
        Create or update an ILM policy.

        Args:
            name: Policy name
            policy: Policy definition (the 'policy' part of the body, or full body)

        Returns:
            True if successful
        """
        if not name:
            raise ValidationError("Policy name is required")
        if not policy:
            raise ValidationError("Policy definition is required")

        try:
            logger.info(f"Creating/Updating ILM policy '{name}'")
            # If the user passed the full wrapper {"policy": {...}}, unwrap it or pass as is?
            # put_lifecycle expects 'policy' arg to contain phases.
            # Usually strict JSON is {"policy": {"phases": ...}}
            
            response = self.client.client.ilm.put_lifecycle(name=name, body=policy)
            body = response.body if hasattr(response, 'body') else dict(response)
            return body.get("acknowledged", False)
        except Exception as e:
            logger.error(f"Failed to create ILM policy '{name}': {str(e)}")
            raise OperationError(f"Failed to create ILM policy '{name}': {str(e)}")

    def delete_policy(self, name: str) -> bool:
        """
        Delete an ILM policy.

        Args:
            name: Policy name

        Returns:
            True if successful
        """
        if not name:
            raise ValidationError("Policy name is required")

        try:
            logger.info(f"Deleting ILM policy '{name}'")
            response = self.client.client.ilm.delete_lifecycle(name=name)
            body = response.body if hasattr(response, 'body') else dict(response)
            return body.get("acknowledged", False)
        except Exception as e:
            logger.error(f"Failed to delete ILM policy '{name}': {str(e)}")
            raise OperationError(f"Failed to delete ILM policy '{name}': {str(e)}")

    def explain_lifecycle(self, index: str) -> Dict[str, Any]:
        """
        Explain the lifecycle state of an index.

        Args:
            index: Index name

        Returns:
            Explanation dictionary
        """
        if not index:
            raise ValidationError("Index name is required")

        try:
            logger.debug(f"Explaining lifecycle for index '{index}'")
            response = self.client.client.ilm.explain_lifecycle(index=index)
            body = response.body if hasattr(response, 'body') else dict(response)
            
            # Usually returns {'indices': {'index_name': {...}}}
            if 'indices' in body and index in body['indices']:
                return body['indices'][index]
            return body
        except Exception as e:
            logger.error(f"Failed to explain lifecycle for '{index}': {str(e)}")
            raise OperationError(f"Failed to explain lifecycle for '{index}': {str(e)}")

    def start_ilm(self) -> bool:
        """Start ILM service."""
        try:
            resp = self.client.client.ilm.start()
            body = resp.body if hasattr(resp, 'body') else dict(resp)
            return body.get("acknowledged", False)
        except Exception as e:
            raise OperationError(f"Failed to start ILM: {e}")

    def stop_ilm(self) -> bool:
        """Stop ILM service."""
        try:
            resp = self.client.client.ilm.stop()
            body = resp.body if hasattr(resp, 'body') else dict(resp)
            return body.get("acknowledged", False)
        except Exception as e:
            raise OperationError(f"Failed to stop ILM: {e}")
