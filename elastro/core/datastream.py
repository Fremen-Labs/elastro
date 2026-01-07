"""
Datastream management module.

This module provides functionality for managing Elasticsearch datastreams.
"""

from typing import Dict, List, Any, Optional
from elastro.core.client import ElasticsearchClient
from elastro.core.errors import DatastreamError, ValidationError
from elastro.core.validation import Validator


class DatastreamManager:
    """
    Manager for Elasticsearch datastream operations.

    This class provides methods for creating and managing Elasticsearch datastreams.
    """

    def __init__(self, client: ElasticsearchClient):
        """
        Initialize the datastream manager.

        Args:
            client: ElasticsearchClient instance
        """
        self._client = client
        self.validator = Validator()

    def create_index_template(self, name: str, pattern: str, settings: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create an index template required for data streams in Elasticsearch 8.x.

        Args:
            name: Name of the template
            pattern: Index pattern the template applies to (e.g., "logs-*")
            settings: Template settings with mappings and settings

        Returns:
            Dict containing template creation response

        Raises:
            ValidationError: If input validation fails
            DatastreamError: If template creation fails
        """
        try:
            # Validate inputs
            if not name:
                raise ValidationError("Template name cannot be empty")
            if not pattern:
                raise ValidationError("Index pattern cannot be empty")
            if settings:
                if 'mappings' in settings:
                    self.validator.validate_index_mappings(settings)
                if 'settings' in settings:
                    self.validator.validate_index_settings(settings)

            # Ensure the client is connected
            if not self._client.is_connected():
                self._client.connect()

            # Prepare template definition
            template_def = {
                "index_patterns": [pattern],
                "data_stream": {},  # Enable data stream
                "priority": 500
            }

            # Add settings and mappings if provided
            if 'settings' in settings:
                template_def["settings"] = settings["settings"]
            if 'mappings' in settings:
                template_def["mappings"] = settings["mappings"]

            # Create the template
            response = self._client._client.indices.put_index_template(
                name=name,
                body=template_def
            )
            return response.body if hasattr(response, 'body') else dict(response)
        except ValidationError as e:
            raise e
        except Exception as e:
            raise DatastreamError(f"Failed to create index template '{name}': {str(e)}")

    def create(self, name: str, description: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new datastream.

        Note: In Elasticsearch 8.x, a matching index template with data_stream enabled 
        must exist before creating the data stream. This method will create the data stream
        only; the index template must be created separately.

        Args:
            name: Name of the datastream
            description: Description of the datastream (optional)

        Returns:
            Dict containing creation response

        Raises:
            ValidationError: If input validation fails
            DatastreamError: If datastream creation fails
        """
        if not name:
            raise ValidationError("Datastream name is required")

        try:
            # Ensure the client is connected
            if not self._client.is_connected():
                self._client.connect()

            # Create params for datastream creation
            create_params = {
                "name": name,
            }

            if description:
                create_params["aliases"] = {"default": {"is_write_index": True}}

            # Create datastream
            response = self._client._client.indices.create_data_stream(**create_params)
            return response.body if hasattr(response, 'body') else dict(response)
        except Exception as e:
            raise DatastreamError(f"Failed to create datastream: {str(e)}")

    def list(self, pattern: str = "*") -> List[Dict[str, Any]]:
        """
        List datastreams matching the pattern.

        Args:
            pattern: Pattern to match datastream names (default: "*")

        Returns:
            List of datastreams

        Raises:
            DatastreamError: If the list operation fails
        """
        try:
            # Ensure the client is connected
            if not self._client.is_connected():
                self._client.connect()

            # Get datastreams matching the pattern
            try:
                response = self._client._client.indices.get_data_stream(name=pattern)
                
                # Format the response
                datastreams = []
                # response['data_streams'] access works on ObjectApiResponse too, so this might be fine already
                # but to be safe:
                body = response.body if hasattr(response, 'body') else dict(response)
                
                if 'data_streams' in body:
                    datastreams = body['data_streams']
                
                return datastreams
            except Exception as e:
                # Handle "index_not_found" error gracefully
                if "index_not_found" in str(e):
                    return []  # Return empty list when no datastreams found
                raise  # Re-raise other errors
                
        except Exception as e:
            raise DatastreamError(f"Failed to list datastreams: {str(e)}")

    def get(self, name: str) -> Dict[str, Any]:
        """
        Get datastream information.

        Args:
            name: Name of the datastream

        Returns:
            Dict containing datastream information

        Raises:
            DatastreamError: If datastream doesn't exist or operation fails
        """
        try:
            # Validate inputs
            if not name:
                raise ValidationError("Datastream name cannot be empty")

            # Ensure the client is connected
            if not self._client.is_connected():
                self._client.connect()

            # Get the datastream
            response = self._client._client.indices.get_data_stream(name=name)
            body = response.body if hasattr(response, 'body') else dict(response)

            # Format the response to match test expectations
            if 'data_streams' in body and len(body['data_streams']) > 0:
                datastream = body['data_streams'][0]
                # Transform to format expected by tests
                return {
                    "name": datastream.get("name"),
                    "generation": datastream.get("generation"),
                    "status": datastream.get("status", "GREEN"),
                    "indices": datastream.get("indices", [])
                }

            raise DatastreamError(f"Datastream '{name}' not found")
        except ValidationError as e:
            raise e
        except Exception as e:
            raise DatastreamError(f"Failed to get datastream '{name}': {str(e)}")

    def exists(self, name: str) -> bool:
        """
        Check if a datastream exists.

        Args:
            name: Name of the datastream

        Returns:
            True if datastream exists, False otherwise
        """
        try:
            # Validate inputs
            if not name:
                raise ValidationError("Datastream name cannot be empty")

            # Ensure the client is connected
            if not self._client.is_connected():
                self._client.connect()

            # Check if datastream exists
            try:
                self._client._client.indices.get_data_stream(name=name)
                return True
            except Exception as e:
                # If datastream doesn't exist, a 404 error is raised
                if "index_not_found" in str(e):
                    return False
                # For other errors, re-raise
                raise
        except ValidationError as e:
            raise e
        except Exception as e:
            raise DatastreamError(f"Failed to check if datastream '{name}' exists: {str(e)}")

    def delete(self, name: str) -> Dict[str, Any]:
        """
        Delete a datastream.

        Args:
            name: Name of the datastream

        Returns:
            Dict containing deletion response

        Raises:
            DatastreamError: If datastream deletion fails
        """
        try:
            # Validate inputs
            if not name:
                raise ValidationError("Datastream name cannot be empty")

            # Ensure the client is connected
            if not self._client.is_connected():
                self._client.connect()

            # Delete the datastream
            response = self._client._client.indices.delete_data_stream(name=name)
            
            # Delete associated index template if it exists
            template_name = f"{name}-template"
            try:
                self._client._client.indices.delete_index_template(name=template_name)
            except Exception:
                # Ignore errors if template doesn't exist
                pass
                
            return response.body if hasattr(response, 'body') else dict(response)
        except ValidationError as e:
            raise e
        except Exception as e:
            raise DatastreamError(f"Failed to delete datastream '{name}': {str(e)}")

    def rollover(self, name: str, conditions: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Rollover a datastream.

        Args:
            name: Name of the datastream
            conditions: Rollover conditions (e.g., {"max_age": "1d", "max_docs": 10000})

        Returns:
            Dict containing rollover response

        Raises:
            ValidationError: If conditions validation fails
            DatastreamError: If datastream rollover fails
        """
        try:
            # Validate inputs
            if not name:
                raise ValidationError("Datastream name cannot be empty")

            # Ensure the client is connected
            if not self._client.is_connected():
                self._client.connect()

            # Prepare rollover parameters
            rollover_params = {
                "alias": name  # Use alias instead of index for datastreams
            }

            # Add conditions as a 'conditions' parameter if provided
            if conditions:
                rollover_params["body"] = {"conditions": conditions}

            # Execute rollover
            response = self._client._client.indices.rollover(**rollover_params)
            return response.body if hasattr(response, 'body') else dict(response)
        except ValidationError as e:
            raise e
        except Exception as e:
            raise DatastreamError(f"Failed to rollover datastream '{name}': {str(e)}")
