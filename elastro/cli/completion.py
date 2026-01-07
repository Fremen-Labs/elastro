import rich_click as click
from typing import List
from elastro.config import load_config
from elastro.core.client import ElasticsearchClient

def get_quick_client():
    """Fast client initialization for autocomplete."""
    # Attempt to load default config/profile
    # We don't have access to --profile flag easily here without complex parsing
    # So we default to 'default' profile for completion.
    try:
        cfg = load_config(None, "default")
        client = ElasticsearchClient(
            hosts=cfg["elasticsearch"]["hosts"],
            auth=cfg["elasticsearch"]["auth"],
            timeout=1, # Fast timeout for completion
            retry_on_timeout=False,
            max_retries=0
        )
        client.connect()
        return client
    except Exception:
        return None

def complete_indices(ctx, param, incomplete: str) -> List[str]:
    """Autocomplete for index names."""
    client = ctx.obj if ctx and ctx.obj else get_quick_client()
    if not client:
        return []
    
    try:
        # Use simple wildcard search for indices
        # expand_wildcards='all' ensures we see hidden ones if needed, but maybe 'open' is better
        # We fetch names matching incomplete*
        # Using cat.indices or get_alias is faster than search
        # client.client is the raw library client
        if not incomplete:
            pattern = "*"
        else:
            pattern = f"{incomplete}*"
            
        indices = list(client.client.indices.get_alias(index=pattern).keys())
        return [i for i in indices if i.startswith(incomplete)]
    except Exception:
        return []

def complete_datastreams(ctx, param, incomplete: str) -> List[str]:
    """Autocomplete for datastreams."""
    client = ctx.obj if ctx and ctx.obj else get_quick_client()
    if not client:
        return []
        
    try:
        # Datastreams API
        if not incomplete:
            pattern = "*"
        else:
            pattern = f"{incomplete}*"
            
        resp = client.client.indices.get_data_stream(name=pattern)
        names = [ds['name'] for ds in resp.get('data_streams', [])]
        return names
    except Exception:
        return []

def complete_templates(ctx, param, incomplete: str) -> List[str]:
    """Autocomplete for templates."""
    client = ctx.obj if ctx and ctx.obj else get_quick_client()
    if not client:
        return []
        
    try:
        # We don't know if they want index or component templates easily here
        # So fetching index templates by default or both could be heavy
        # Let's try index templates for now
        if not incomplete:
            pattern = "*"
        else:
            pattern = f"{incomplete}*"
            
        # Get index templates
        resp = client.client.indices.get_index_template(name=pattern)
        names = [t['name'] for t in resp.get('index_templates', [])]
        
        # Also try component templates? might be too noisy.
        # Let's stick to index templates for the main autocomplete
        # Or maybe filter based on --type if click supports it (hard)
        return names
    except Exception:
        return []

def complete_policies(ctx, param, incomplete: str) -> List[str]:
    """Autocomplete for ILM policies."""
    client = ctx.obj if ctx and ctx.obj else get_quick_client()
    if not client:
        return []
        
    try:
        # Use get_lifecycle to list all
        resp = client.client.ilm.get_lifecycle()
        body = resp.body if hasattr(resp, 'body') else dict(resp)
        policies = list(body.keys())
        return [p for p in policies if p.startswith(incomplete)]
    except Exception:
        return []
