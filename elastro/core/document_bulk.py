"""
Bulk document operations module.

.. deprecated::
    ``BulkDocumentManager`` is deprecated. Use ``DocumentManager.bulk_index_sync()``
    and ``DocumentManager.bulk_delete_sync()`` instead. This module is maintained
    solely for backward compatibility and will be removed in a future release.
"""

import warnings
from typing import Dict, List, Any
from elastro.core.client import ElasticsearchClient
from elastro.core.document import DocumentManager


class BulkDocumentManager:
    """
    Deprecated: Use DocumentManager.bulk_index_sync() / bulk_delete_sync() instead.

    This class is a thin backward-compatibility shim that delegates to
    DocumentManager's synchronous bulk methods.
    """

    def __init__(self, client: ElasticsearchClient) -> None:
        warnings.warn(
            "BulkDocumentManager is deprecated. "
            "Use DocumentManager.bulk_index_sync() and "
            "DocumentManager.bulk_delete_sync() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.client = client
        self._delegate = DocumentManager(client)

    def bulk_index(
        self, index: str, documents: List[Dict[str, Any]], refresh: bool = False
    ) -> Dict[str, Any]:
        """Delegates to DocumentManager.bulk_index_sync()."""
        return self._delegate.bulk_index_sync(index, documents, refresh)

    def bulk_delete(
        self, index: str, ids: List[str], refresh: bool = False
    ) -> Dict[str, Any]:
        """Delegates to DocumentManager.bulk_delete_sync()."""
        return self._delegate.bulk_delete_sync(index, ids, refresh)
