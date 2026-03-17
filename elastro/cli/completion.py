import asyncio
import rich_click as click
from typing import List, Optional, Any
from elastro.config import load_config
from elastro.core.client import ElasticsearchClient


def get_quick_client() -> Optional[ElasticsearchClient]:
    """Fast client initialization for autocomplete."""
    try:
        cfg = load_config(None, "default")
        client = ElasticsearchClient(
            hosts=cfg["elasticsearch"]["hosts"],
            auth=cfg["elasticsearch"]["auth"],
            timeout=1,  # Fast timeout for completion
            retry_on_timeout=False,
            max_retries=0,
        )
        return client
    except Exception:
        return None


def complete_indices(ctx: Any, param: Any, incomplete: str) -> List[str]:
    """Autocomplete for index names."""
    async def _run():
        client = ctx.obj if ctx and ctx.obj else get_quick_client()
        if not client:
            return []

        try:
            if not await client.is_connected():
                await client.connect()
                
            pattern = f"{incomplete}*" if incomplete else "*"
            
            # get_alias returns a dict of indices and their aliases
            # e.g., {'metrics-local': {'aliases': {}}}
            resp = await client.client.indices.get_alias(index=pattern)
            body = resp.body if hasattr(resp, "body") else dict(resp)
            indices = list(body.keys())
            
            return [i for i in indices if i.startswith(incomplete)]
        except Exception:
            return []
    return asyncio.run(_run())


def complete_datastreams(ctx: Any, param: Any, incomplete: str) -> List[str]:
    """Autocomplete for datastreams."""
    async def _run():
        client = ctx.obj if ctx and ctx.obj else get_quick_client()
        if not client:
            return []

        try:
            if not await client.is_connected():
                await client.connect()
                
            pattern = f"{incomplete}*" if incomplete else "*"
            resp = await client.client.indices.get_data_stream(name=pattern)
            body = resp.body if hasattr(resp, "body") else dict(resp)
            names = [ds["name"] for ds in body.get("data_streams", [])]
            return names
        except Exception:
            return []
    return asyncio.run(_run())


def complete_templates(ctx: Any, param: Any, incomplete: str) -> List[str]:
    """Autocomplete for templates."""
    async def _run():
        client = ctx.obj if ctx and ctx.obj else get_quick_client()
        if not client:
            return []

        try:
            if not await client.is_connected():
                await client.connect()
                
            pattern = f"{incomplete}*" if incomplete else "*"
            resp = await client.client.indices.get_index_template(name=pattern)
            body = resp.body if hasattr(resp, "body") else dict(resp)
            names = [t["name"] for t in body.get("index_templates", [])]
            return names
        except Exception:
            return []
    return asyncio.run(_run())


def complete_policies(ctx: Any, param: Any, incomplete: str) -> List[str]:
    """Autocomplete for ILM policies."""
    async def _run():
        client = ctx.obj if ctx and ctx.obj else get_quick_client()
        if not client:
            return []

        try:
            if not await client.is_connected():
                await client.connect()
                
            resp = await client.client.ilm.get_lifecycle()
            body = resp.body if hasattr(resp, "body") else dict(resp)
            policies = list(body.keys())
            return [p for p in policies if p.startswith(incomplete)]
        except Exception:
            return []
    return asyncio.run(_run())
