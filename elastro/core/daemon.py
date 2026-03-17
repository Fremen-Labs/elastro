"""
Elastro Fast-Path Daemon.

Maintains a persistent Elasticsearch client for sub-millisecond agentic queries.
"""

import argparse
from typing import List, Optional
from xmlrpc.server import SimpleXMLRPCServer

from elastro.cli.output import format_output
from elastro.config.loader import get_config
from elastro.core.client import ElasticsearchClient
from elastro.core.document import DocumentManager
from elastro.core.query_builder import QueryBuilder


class ElastroRPCService:
    def __init__(self) -> None:
        self.client: Optional[ElasticsearchClient] = None
        self._connect()

    async def _connect(self) -> None:
        config = get_config()
        self.client = ElasticsearchClient(
            hosts=config["elasticsearch"]["hosts"],
            auth=config["elasticsearch"].get("auth"),
            timeout=config["elasticsearch"].get("timeout", 30),
            retry_on_timeout=config["elasticsearch"].get("retry_on_timeout", True),
            max_retries=config["elasticsearch"].get("max_retries", 3),
        )
        await self.client.connect()

    async def health_check(self) -> bool:
        if self.client:
            return self.client.is_connected()
        return False

    async def fast_path_search(self, args: List[str]) -> str:
        if not self.client:
            return "Error: Elasticsearch client not connected in daemon."

        parser = argparse.ArgumentParser()
        parser.add_argument("index", type=str)
        parser.add_argument("query", type=str, nargs="?", default=None)
        parser.add_argument("--size", type=int, default=10)
        parser.add_argument("--from", type=int, default=0, dest="from_")

        # Query types
        parser.add_argument("--match", action="append", default=[])
        parser.add_argument(
            "--match-phrase", action="append", default=[], dest="match_phrase"
        )
        parser.add_argument("--term", action="append", default=[])
        parser.add_argument("--terms", action="append", default=[])
        parser.add_argument("--range", action="append", default=[])
        parser.add_argument("--prefix", action="append", default=[])
        parser.add_argument("--wildcard", action="append", default=[])
        parser.add_argument("--exists", action="append", default=[])
        parser.add_argument("--ids", action="append", default=[])
        parser.add_argument("--fuzzy", action="append", default=[])

        # Excludes
        parser.add_argument(
            "--exclude-match", action="append", default=[], dest="exclude_match"
        )
        parser.add_argument(
            "--exclude-term", action="append", default=[], dest="exclude_term"
        )

        parser.add_argument("--output", "-o", type=str, default="json")

        try:
            parsed, _ = parser.parse_known_args(args)
        except Exception as e:
            return f"Error parsing arguments: {str(e)}"

        doc_manager = DocumentManager(self.client)

        inner_query = QueryBuilder.build_bool_query(
            must_match=getattr(parsed, "match", None),
            must_match_phrase=getattr(parsed, "match_phrase", None),
            must_term=getattr(parsed, "term", None),
            must_terms=getattr(parsed, "terms", None),
            must_range=getattr(parsed, "range", None),
            must_prefix=getattr(parsed, "prefix", None),
            must_wildcard=getattr(parsed, "wildcard", None),
            must_exists=getattr(parsed, "exists", None),
            must_ids=getattr(parsed, "ids", None),
            must_fuzzy=getattr(parsed, "fuzzy", None),
            exclude_match=getattr(parsed, "exclude_match", None),
            exclude_term=getattr(parsed, "exclude_term", None),
            query_string=getattr(parsed, "query", None),
        )

        query_body = {"query": inner_query}
        options = {
            "size": getattr(parsed, "size", 10),
            "from": getattr(parsed, "from_", 0),
        }

        try:
            results = doc_manager.search(
                getattr(parsed, "index", ""), query_body, options
            )
            output_format = getattr(parsed, "output", "json")
            output_str = format_output(results, output_format=output_format)
            return output_str
        except Exception as e:
            return f"Daemon search error: {str(e)}"


def start_daemon(host: str = "127.0.0.1", port: int = 9201) -> None:
    """Start the Elastro XML-RPC daemon server."""
    server = SimpleXMLRPCServer((host, port), allow_none=True)
    server.register_instance(ElastroRPCService())
    print(f"Starting Elastro XML-RPC Daemon on {host}:{port}...", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down daemon.")
