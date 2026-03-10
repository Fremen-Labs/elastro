"""
Elastro Fast-Path Daemon.

Maintains a persistent Elasticsearch client for sub-millisecond agentic queries.
"""

import argparse
from contextlib import asynccontextmanager
from typing import List, Optional, AsyncGenerator, Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from elastro.cli.output import format_output
from elastro.config.loader import get_config
from elastro.core.client import ElasticsearchClient
from elastro.core.document import DocumentManager
from elastro.core.query_builder import QueryBuilder

# Global client
client: Optional[ElasticsearchClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global client
    config = get_config()
    client = ElasticsearchClient(
        hosts=config["elasticsearch"]["hosts"],
        auth=config["elasticsearch"].get("auth"),
        timeout=config["elasticsearch"].get("timeout", 30),
        retry_on_timeout=config["elasticsearch"].get("retry_on_timeout", True),
        max_retries=config["elasticsearch"].get("max_retries", 3),
    )
    client.connect()
    yield
    if client:
        client.disconnect()


app = FastAPI(lifespan=lifespan, title="Elastro Agentic Daemon")


class DocSearchRequest(BaseModel):
    args: List[str]


@app.get("/health")
def health_check() -> dict[str, Any]:
    return {
        "status": "alive",
        "client_connected": client.is_connected() if client else False,
    }


@app.post("/fast-path/doc/search")
async def fast_path_search(req: DocSearchRequest) -> PlainTextResponse:
    # Parse args manually for top 10 query types
    parser = argparse.ArgumentParser()
    parser.add_argument("index", type=str)
    parser.add_argument("query", type=str, nargs="?", default=None)
    parser.add_argument("--size", type=int, default=10)
    parser.add_argument("--from", "from_", type=int, default=0, dest="from_")

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

    parsed, _ = parser.parse_known_args(req.args)

    if not client:
        return PlainTextResponse(
            "Error: Elasticsearch client not connected in daemon.", status_code=500
        )

    doc_manager = DocumentManager(client)

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
    options = {"size": getattr(parsed, "size", 10), "from": getattr(parsed, "from_", 0)}

    try:
        results = doc_manager.search(getattr(parsed, "index", ""), query_body, options)
        output_format = getattr(parsed, "output", "json")
        output_str = format_output(results, output_format=output_format)
        return PlainTextResponse(content=output_str)
    except Exception as e:
        return PlainTextResponse(
            content=f"Daemon search error: {str(e)}", status_code=500
        )


def start_daemon(host: str = "127.0.0.1", port: int = 9201) -> None:
    """Start the Elastro daemon server."""
    uvicorn.run(app, host=host, port=port, log_level="info")
