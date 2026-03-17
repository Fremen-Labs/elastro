import asyncio
from functools import wraps
from typing import Callable, Any
from elastro.core.client import ElasticsearchClient
import logging

def coro(f: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        async def run_in_loop():
            # Hunt for the client object injected by Click
            client = None
            for arg in args:
                if isinstance(arg, ElasticsearchClient):
                    client = arg
                    break
            if not client:
                for k, v in kwargs.items():
                    if isinstance(v, ElasticsearchClient):
                        client = v
                        break
            
            # Connect inside the active loop
            if client:
                try:
                    is_conn = await client.is_connected()
                    if not is_conn:
                        await client.connect()
                except Exception as e:
                    logging.getLogger("elastro.cli").debug(f"AsyncCLI connection warning: {e}")
            try:
                return await f(*args, **kwargs)
            finally:
                if client and await client.is_connected():
                    try:
                        await client.disconnect()
                    except Exception:
                        pass
        return asyncio.run(run_in_loop())
    return wrapper
