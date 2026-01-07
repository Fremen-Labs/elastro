"""
Document management module.

This module provides functionality for managing Elasticsearch documents.
"""

from typing import Dict, List, Any, Optional, Union
from elasticsearch import helpers
from elastro.core.client import ElasticsearchClient
from elastro.core.errors import DocumentError, ValidationError, OperationError
from elastro.core.validation import Validator
from elastro.core.logger import get_logger

logger = get_logger(__name__)


class DocumentManager:
    """
    Manager for Elasticsearch document operations.

    This class provides methods for indexing, updating, and searching documents.
    """

    def __init__(self, client: ElasticsearchClient):
        """
        Initialize the document manager.

        Args:
            client: ElasticsearchClient instance
        """
        self.client = client
        self._client = client  # Add this for compatibility with tests
        self.validator = Validator()

    def index(
        self,
        index: str,
        id: Optional[str],
        document: Dict[str, Any],
        refresh: bool = False
    ) -> Any:
        """
        Index a document.

        Args:
            index: Name of the index
            id: Document ID (optional)
            document: Document data
            refresh: Whether to refresh the index immediately

        Returns:
            Indexing response
        """
        # Validate inputs
        if not index:
            raise ValidationError("Index name cannot be empty")

        # Document validation could be expanded based on schema
        if not document or not isinstance(document, dict):
            raise ValidationError("Document must be a non-empty dictionary")

        try:
            # Prepare indexing parameters
            params = {
                "index": index,
                "document": document,
                "refresh": "true" if refresh else "false"
            }

            # Add ID if provided
            if id:
                params["id"] = id
            
            logger.debug(f"Indexing document into '{index}' with ID '{id}'")
            # Execute the index operation
            response = self.client.client.index(**params)  # type: ignore
            return response.body if hasattr(response, 'body') else dict(response)
        except Exception as e:
            logger.error(f"Failed to index document info '{index}': {str(e)}")
            raise DocumentError(f"Failed to index document: {str(e)}")

    def bulk_index(
        self,
        index: str,
        documents: List[Dict[str, Any]],
        refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Bulk index multiple documents.

        Args:
            index: Name of the index
            documents: List of documents to index
            refresh: Whether to refresh the index immediately

        Returns:
            Dict containing bulk indexing response summary

        Raises:
            ValidationError: If input validation fails
            OperationError: If bulk indexing fails
        """
        # Validate inputs
        if not index:
            raise ValidationError("Index name cannot be empty")

        if not documents or not isinstance(documents, list):
            raise ValidationError("Documents must be a non-empty list")

        try:
            # Prepare actions for streaming bulk
            actions = []
            for doc in documents:
                # Create action dict
                action = {
                    "_index": index,
                    "_source": doc
                }
                
                # If document has an ID field, separate it
                if "_id" in doc:
                    action["_id"] = doc["_id"]
                    # Create a copy without _id for _source
                    doc_copy = doc.copy()
                    doc_copy.pop("_id", None)
                    action["_source"] = doc_copy
                
                actions.append(action)

            logger.info(f"Bulk indexing {len(actions)} documents into '{index}'...")
            
            # Use helpers.bulk for optimized streaming
            success_count, errors = helpers.bulk(
                self.client.client,
                actions,
                refresh="true" if refresh else "false",
                stats_only=False, # We want details if needed, but summary is usually returned
                raise_on_error=True
            )
            
            logger.info(f"Bulk index complete: {success_count} successful")
            
            return {
                "success_count": success_count,
                "errors": errors if isinstance(errors, list) else []
            }

        except Exception as e:
            logger.error(f"Failed to bulk index documents: {str(e)}")
            raise OperationError(f"Failed to bulk index documents: {str(e)}")

    def get(self, index: str, id: str) -> Any:
        """
        Get a document by ID.

        Args:
            index: Name of the index
            id: Document ID

        Returns:
            Document data
        """
        # Validate inputs
        if not index:
            raise ValidationError("Index name cannot be empty")

        if not id:
            raise ValidationError("Document ID cannot be empty")

        try:
            response = self.client.client.get(index=index, id=id)
            return response.body if hasattr(response, 'body') else dict(response)
        except Exception as e:
            # Log only if it's an unexpected error
            logger.error(f"Failed to get document '{id}' from '{index}': {str(e)}")
            raise DocumentError(f"Failed to get document: {str(e)}")

    def update(
        self,
        index: str,
        id: str,
        document: Dict[str, Any],
        partial: bool = True,
        refresh: bool = False
    ) -> Any:
        """
        Update a document.

        Args:
            index: Name of the index
            id: Document ID
            document: Updated document data or partial document
            partial: Whether this is a partial update
            refresh: Whether to refresh the index immediately

        Returns:
            Update response
        """
        # Validate inputs
        if not index:
            raise ValidationError("Index name cannot be empty")

        if not id:
            raise ValidationError("Document ID cannot be empty")

        if not document or not isinstance(document, dict):
            raise ValidationError("Document must be a non-empty dictionary")

        try:
            logger.debug(f"Updating document '{id}' in '{index}' (partial={partial})")
            if partial:
                # For partial updates, wrap in "doc" field
                body = {"doc": document}
                response = self.client.client.update(
                    index=index,
                    id=id,
                    body=body,
                    refresh="true" if refresh else "false"
                )
                return response.body if hasattr(response, 'body') else dict(response)
            else:
                # For full document updates, just index it again
                return self.index(index=index, id=id, document=document, refresh=refresh)
        except Exception as e:
            logger.error(f"Failed to update document '{id}': {str(e)}")
            raise DocumentError(f"Failed to update document: {str(e)}")

    def delete(
        self,
        index: str,
        id: str,
        refresh: bool = False
    ) -> Any:
        """
        Delete a document by ID.

        Args:
            index: Name of the index
            id: Document ID
            refresh: Whether to refresh the index immediately

        Returns:
            Deletion response
        """
        # Validate inputs
        if not index:
            raise ValidationError("Index name cannot be empty")

        if not id:
            raise ValidationError("Document ID cannot be empty")

        try:
            logger.info(f"Deleting document '{id}' from '{index}'")
            response = self.client.client.delete(
                index=index,
                id=id,
                refresh="true" if refresh else "false"
            )
            return response.body if hasattr(response, 'body') else dict(response)
        except Exception as e:
            logger.error(f"Failed to delete document '{id}': {str(e)}")
            raise DocumentError(f"Failed to delete document: {str(e)}")

    def search(
        self,
        index: str,
        query: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Search for documents.

        Args:
            index: Name of the index
            query: Elasticsearch query DSL
            options: Additional search options like size, from, sort, etc.

        Returns:
            Search results
        """
        # Validate inputs
        if not index:
            raise ValidationError("Index name cannot be empty")

        if not query:
            raise ValidationError("Query cannot be empty")

        # Prepare search body
        # Check if query already has "query" key at top level to avoid double wrapping
        if query and "query" in query and len(query) == 1:
            # It might be a full body with just query
            body = query.copy()
        elif query:
            body = {"query": query}
        else:
             body = {"query": {"match_all": {}}}

        # Add search options if provided
        if options:
            for key, value in options.items():
                if key in ["size", "from", "sort", "track_total_hits"]:
                    body[key] = value
                elif key in ["_source", "aggs", "aggregations", "highlight"]:
                    body[key] = value

        search_params = {"index": index, "body": body}

        try:
            logger.debug(f"Searching index '{index}'...")
            response = self.client.client.search(**search_params)  # type: ignore
            return response.body if hasattr(response, 'body') else dict(response)
        except Exception as e:
            logger.error(f"Failed to search documents in '{index}': {str(e)}")
            raise DocumentError(f"Failed to search documents: {str(e)}")
