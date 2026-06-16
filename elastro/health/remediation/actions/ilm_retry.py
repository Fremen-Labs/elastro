"""Retry a stuck ILM lifecycle step for an index."""

from __future__ import annotations

from elastro.core.ilm import IlmManager
from elastro.core.index import IndexManager
from elastro.core.logger import get_logger

logger = get_logger(__name__)


def planned_ilm_retry(index_name: str) -> str:
    return f"POST /{index_name}/_ilm/retry"


def ilm_retry(index_manager: IndexManager, index_name: str, **kwargs: object) -> str:
    """Retry ILM execution for the given index."""
    logger.info("Retrying ILM lifecycle for index %s", index_name)
    IlmManager(index_manager._client).retry_lifecycle(index_name)
    return f"ILM retry requested for {index_name}"