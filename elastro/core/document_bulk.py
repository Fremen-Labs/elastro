"""
Bulk document operations module.

This module provides functionality for bulk operations on Elasticsearch documents.
"""

from typing import Dict, List, Any, Optional
from elastro.core.client import ElasticsearchClient
from elastro.core.errors import DocumentError, ValidationError
from elastro.core.validation import Validator


class BulkDocumentManager:
    """
    Manager for Elasticsearch bulk document operations.

    This class provides methods for bulk indexing and deleting documents.
    """

    def __init__(self, client: ElasticsearchClient):
        """
        Initialize the bulk document manager.

        Args:
            client: ElasticsearchClient instance
        """
        self.client = client
        self.validator = Validator()

    def bulk_index(
        self, index: str, documents: List[Dict[str, Any]], refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Index multiple documents in bulk.

        Args:
            index: Name of the index
            documents: List of document data
            refresh: Whether to refresh the index immediately

        Returns:
            Dict containing bulk indexing response

        Raises:
            ValidationError: If input validation fails
            DocumentError: If bulk indexing fails
        """
        # Validate inputs
        if not index:
            raise ValidationError("Index name cannot be empty")

        if not documents or not isinstance(documents, list):
            raise ValidationError("Documents must be a non-empty list")

        if not all(isinstance(doc, dict) for doc in documents):
            raise ValidationError("All documents must be dictionaries")

        try:
            # Prepare bulk operations
            operations = []
            for doc in documents:
                # Each document can optionally have an _id field
                doc_id = doc.pop("_id", None)

                # Create action/metadata
                action = {"_index": index}
                if doc_id:
                    action["_id"] = doc_id

                # Add to operations list
                operations.append({"index": action})
                operations.append(doc)

            # Execute bulk operation
            return self.client.client.bulk(
                operations=operations, refresh="true" if refresh else "false"
            )
        except Exception as e:
            raise DocumentError(f"Failed to bulk index documents: {str(e)}")

    def bulk_delete(
        self, index: str, ids: List[str], refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Delete multiple documents in bulk.

        Args:
            index: Name of the index
            ids: List of document IDs
            refresh: Whether to refresh the index immediately

        Returns:
            Dict containing bulk deletion response

        Raises:
            ValidationError: If input validation fails
            DocumentError: If bulk deletion fails
        """
        # Validate inputs
        if not index:
            raise ValidationError("Index name cannot be empty")

        if not ids or not isinstance(ids, list):
            raise ValidationError("IDs must be a non-empty list")

        try:
            # Prepare bulk operations for deletion
            operations = []
            for doc_id in ids:
                operations.append({"delete": {"_index": index, "_id": doc_id}})

            # Execute bulk operation
            return self.client.client.bulk(
                operations=operations, refresh="true" if refresh else "false"
            )
        except Exception as e:
            raise DocumentError(f"Failed to bulk delete documents: {str(e)}")
