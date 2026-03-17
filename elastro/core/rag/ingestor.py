"""
Graph RAG orchestration module.
Scans physical codebases, leverages the ASTParser to extract functional flow maps,
and bulk indexes the enriched documents into Elasticsearch.
Updated with Semantic Chunking and BM25 Support.
"""

import os
import json
import logging
from typing import List, Dict, Any, Generator, Optional
from elastro.core.client import ElasticsearchClient
from elastro.core.rag.ast_parser import ASTParser

logger = logging.getLogger("elastro.rag")


class GraphRAGManager:
    async def __init__(
        self, client: ElasticsearchClient, index_name: str = "fremen_codebase_rag"
    ):
        self.client = client
        self.index_name = index_name
        self.ast_parser = ASTParser()

        # We explicitly target the agent's core polyglot languages + Markdown for KI Bridging
        self.supported_extensions = {
            ".py",
            ".go",
            ".vue",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".md",
        }

        # Prevent indexing binary data, large dependency folders, or generated outputs
        self.ignore_dirs = {
            ".git",
            "node_modules",
            "venv",
            ".venv",
            "env",
            "__pycache__",
            "dist",
            "build",
            ".next",
            ".nuxt",
            "coverage",
            ".idea",
            ".vscode",
        }

    async def _should_ignore(self, path: str) -> bool:
        """Determines if a directory or file should be skipped during ingestion."""
        parts = os.path.normpath(path).split(os.sep)
        for part in parts:
            if part in self.ignore_dirs:
                return True
        return False

    async def scaffold_index(self) -> None:
        """Safely creates the Graph RAG index if it does not manually exist."""
        pipeline_deployed = False
        # 1. Attempt to build the Dense Vector inference pipeline for Hybrid Search
        try:
            await self.client.client.ingest.put_pipeline(
                id="elastro-elser-v2",
                description="Process text via ELSER for Dense Vector Hybrid Search",
                processors=[
                    {
                        "inference": {
                            "model_id": ".elser_model_2",
                            "field_map": {"content": "text_field"},
                            "target_field": "content_embedding",
                            "inference_config": {
                                "text_expansion": {"results_field": "tokens"}
                            },
                            "ignore_failure": True,
                        }
                    }
                ],
            )
            logger.info(
                "Successfully deployed ELSER inference pipeline framework (Enterprise Mode)."
            )
            pipeline_deployed = True
        except Exception as e:
            logger.warning(
                f"Could not scaffold ELSER pipeline (requires ML nodes or Platinum/Enterprise license). Falling back to Open Source BM25 Mode. Error: {e}"
            )

        # Simple existence check without causing hard errors if it doesn't
        if not await self.client.client.indices.exists(index=self.index_name):
            logger.info(f"Creating Graph RAG index '{self.index_name}'")

            settings: Dict[str, Any] = {"number_of_shards": 1, "number_of_replicas": 0}
            if pipeline_deployed:
                settings["default_pipeline"] = "elastro-elser-v2"

            mappings: Dict[str, Any] = {
                "properties": {
                    "repo_name": {"type": "keyword"},
                    "file_path": {"type": "keyword"},
                    "extension": {"type": "keyword"},
                    "chunk_type": {"type": "keyword"},
                    "chunk_name": {"type": "keyword"},
                    "content": {"type": "text"},
                    "functions_defined": {"type": "keyword"},
                    "functions_called": {"type": "keyword"},
                }
            }
            if pipeline_deployed:
                mappings["properties"]["content_embedding"] = {"type": "sparse_vector"}

            # We enforce standard RAG architecture with the Semantic Chunking fields.
            await self.client.client.indices.create(
                index=self.index_name, body={"settings": settings, "mappings": mappings}
            )

    async def scan_and_yield(self, repo_path: str) -> Any:
        """
        Walks the repository sequentially. Applies Semantic Chunking and AST parsing.
        Yields Elasticsearch Bulk API formatted operation dictionaries.
        """
        # Ensure we have absolute paths.
        repo_path = os.path.abspath(repo_path)
        repo_name = os.path.basename(repo_path)

        for root, dirs, files in os.walk(repo_path):
            # Prune ignored directories in-place to avoid deep pointless traversals
            dirs[:] = [
                d for d in dirs if not self._should_ignore(os.path.join(root, d))
            ]

            for file in files:
                file_path = os.path.join(root, file)

                # Check explicit supported AST languages or ignore check
                ext = os.path.splitext(file)[1].lower()
                if ext not in self.supported_extensions or self._should_ignore(
                    file_path
                ):
                    continue

                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    # 1. Engage the AST parser to extract the "Graph" semantic chunks
                    chunks = self.ast_parser.parse_file(file_path, content)
                    rel_path = os.path.relpath(file_path, repo_path)

                    # 2. Yield the Bulk API _index action for each specific chunk
                    for i, chunk in enumerate(chunks):
                        doc_id = f"{repo_name}:{rel_path}::{i}"

                        yield {
                            "_op_type": "index",
                            "_index": self.index_name,
                            "_id": doc_id,
                            "_source": {
                                "repo_name": repo_name,
                                "file_path": rel_path,
                                "extension": ext,
                                "chunk_type": chunk.get("chunk_type", "file"),
                                "chunk_name": chunk.get("name", "module"),
                                "content": chunk.get("content", content),
                                "functions_defined": chunk.get("functions_defined", []),
                                "functions_called": chunk.get("functions_called", []),
                            },
                        }
                except UnicodeDecodeError:
                    # Skip binary files that masquerade as text extensions
                    continue
                except Exception as e:
                    logger.error(f"Error parsing Graph RAG for {file_path}: {e}")

    async def ingest_repository(self, repo_path: str) -> int:
        """
        Orchestrates Elasticsearch bulk insertion directly leveraging the client helpers.
        """
        from elasticsearch.helpers import async_bulk

        # Fire up the index blueprint
        self.scaffold_index()

        # Extract AST Flows & Stream seamlessly to Elastic
        success_count, failed_inserts = await async_bulk(
            self.client.client,
            self.scan_and_yield(repo_path),
            chunk_size=500,  # Large batch sizes for fast performance on local M4 Mini
            stats_only=True,
        )

        return success_count

    async def update_file(self, file_path: str, repo_path: Optional[str] = None) -> int:
        """
        Surgically updates a specific file's AST chunks in Elasticsearch.
        Uses bulk processing for deletions to comply with performance constraints.
        """
        from elasticsearch.helpers import async_bulk

        file_path = os.path.abspath(file_path)
        if not repo_path:
            # Find closest .git dir
            current = file_path
            while current != os.path.dirname(current):
                current = os.path.dirname(current)
                if os.path.isdir(os.path.join(current, ".git")):
                    repo_path = current
                    break
            if not repo_path:
                repo_path = os.getcwd()  # Fallback

        repo_name = os.path.basename(repo_path)
        rel_path = os.path.relpath(file_path, repo_path)

        self.scaffold_index()

        # 1. Yield bulk delete ops for stale chunks matching file_path
        async def generate_deletes() -> Any:
            query = {
                "query": {"term": {"file_path": rel_path}},
                "_source": False,
                "size": 1000,
            }
            try:
                res = await self.client.client.search(index=self.index_name, body=query)
                for hit in res.get("hits", {}).get("hits", []):
                    yield {
                        "_op_type": "delete",
                        "_index": self.index_name,
                        "_id": hit["_id"],
                    }
            except Exception as e:
                logger.warning(f"Could not fetch existing chunks for deletion: {e}")

        # Execute deletes
        try:
            await async_bulk(self.client.client, generate_deletes(), refresh=True, stats_only=True)
        except Exception as e:
            logger.warning(f"Failed to bulk delete stale AST chunks: {e}")

        # 2. Re-ingest
        async def scan_single_file() -> Any:
            ext = os.path.splitext(file_path)[1].lower()
            if ext not in self.supported_extensions or self._should_ignore(file_path):
                return

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                chunks = self.ast_parser.parse_file(file_path, content)
                for i, chunk in enumerate(chunks):
                    doc_id = f"{repo_name}:{rel_path}::{i}"
                    yield {
                        "_op_type": "index",
                        "_index": self.index_name,
                        "_id": doc_id,
                        "_source": {
                            "repo_name": repo_name,
                            "file_path": rel_path,
                            "extension": ext,
                            "chunk_type": chunk.get("chunk_type", "file"),
                            "chunk_name": chunk.get("name", "module"),
                            "content": chunk.get("content", content),
                            "functions_defined": chunk.get("functions_defined", []),
                            "functions_called": chunk.get("functions_called", []),
                        },
                    }
            except Exception as e:
                logger.error(f"Error parsing Graph RAG for {file_path}: {e}")

        success_count, _ = await async_bulk(
            self.client.client,
            scan_single_file(),
            chunk_size=100,
            stats_only=True,
            refresh=True,
        )

        # Re-cast dynamically because bulk returns a tuple
        return int(success_count)
