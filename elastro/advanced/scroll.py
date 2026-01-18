"""Scroll helper for handling large result sets in Elasticsearch."""

from typing import Any, Callable, Dict, Generator, List, Optional, Union
from elasticsearch import Elasticsearch
from elasticsearch import Elasticsearch
from elastro.core.logger import get_logger

logger = get_logger(__name__)


class ScrollHelper:
    """Helper for managing Elasticsearch scroll searches.

    Scroll searches allow retrieving large numbers of documents from Elasticsearch
        that would otherwise exceed result size limits. This helper simplifies the
        process of initializing and maintaining scroll contexts.
    """

    def __init__(self, client: Elasticsearch) -> None:
        """Initialize the scroll helper.

        Args:
            client: Elasticsearch client instance
        """
        self._client = client

    def scroll(
        self,
        index: str,
        query: Dict[str, Any],
        scroll_timeout: str = "1m",
        size: int = 1000,
        source_fields: Optional[List[str]] = None,
    ) -> Generator[List[Dict[str, Any]], None, None]:
        """Perform a scroll search and yield batches of results.

        Args:
            index: Index name(s) to search
            query: Elasticsearch query
            scroll_timeout: Time to keep scroll context alive between requests
            size: Number of documents per batch
            source_fields: List of fields to include in _source

        Yields:
            Documents from the scroll search, one batch at a time
        """
        body = {"query": query, "size": size}
        if source_fields:
            body["_source"] = source_fields

        # Initialize scroll
        resp = self._client.search(index=index, body=body, scroll=scroll_timeout)

        # Get the scroll ID
        scroll_id = resp.get("_scroll_id")

        try:
            # First batch of results
            batch = resp.get("hits", {}).get("hits", [])
            while batch:
                yield batch

                # Continue scrolling
                resp = self._client.scroll(scroll_id=scroll_id, scroll=scroll_timeout)

                # Update scroll_id as it may change
                scroll_id = resp.get("_scroll_id")

                # Get next batch
                batch = resp.get("hits", {}).get("hits", [])

                # Stop if no more results
                if not batch:
                    break
        finally:
            # Always clear the scroll context when done
            if scroll_id:
                try:
                    self._client.clear_scroll(scroll_id=scroll_id)
                except Exception as e:
                    logger.warning(f"Failed to clear scroll context: {str(e)}")

    def process_all(
        self,
        index: str,
        query: Dict[str, Any],
        processor: Callable[[Dict[str, Any]], None],
        scroll_timeout: str = "1m",
        size: int = 1000,
        source_fields: Optional[List[str]] = None,
    ) -> int:
        """Process all matching documents with a callback function.

        Args:
            index: Index name(s) to search
            query: Elasticsearch query
            processor: Callback function to process each document
            scroll_timeout: Time to keep scroll context alive
            size: Number of documents per batch
            source_fields: List of fields to include in _source

        Returns:
            Total number of documents processed
        """
        total_processed = 0

        for batch in self.scroll(
            index=index,
            query=query,
            scroll_timeout=scroll_timeout,
            size=size,
            source_fields=source_fields,
        ):
            for doc in batch:
                processor(doc)
                total_processed += 1

        return total_processed

    def collect_all(
        self,
        index: str,
        query: Dict[str, Any],
        scroll_timeout: str = "1m",
        size: int = 1000,
        source_fields: Optional[List[str]] = None,
        max_documents: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Collect all matching documents into a single list.

        Warning: This can consume a lot of memory for large result sets.

        Args:
            index: Index name(s) to search
            query: Elasticsearch query
            scroll_timeout: Time to keep scroll context alive
            size: Number of documents per batch
            source_fields: List of fields to include in _source
            max_documents: Maximum number of documents to collect

        Returns:
            List of all matching documents
        """
        all_docs: List[Dict[str, Any]] = []
        docs_collected = 0

        for batch in self.scroll(
            index=index,
            query=query,
            scroll_timeout=scroll_timeout,
            size=size,
            source_fields=source_fields,
        ):
            if max_documents is not None:
                remaining = max_documents - docs_collected
                if remaining <= 0:
                    break
                if len(batch) > remaining:
                    batch = batch[:remaining]

            all_docs.extend(batch)
            docs_collected += len(batch)

            if max_documents is not None and docs_collected >= max_documents:
                break

        return all_docs
