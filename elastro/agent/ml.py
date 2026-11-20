"""Put ML anomaly jobs and datafeeds."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Union

from pydantic import BaseModel

from elastro.agent.models import dump_payload
from elastro.core.base import BaseManager
from elastro.core.errors import ElasticModuleError, OperationError, ValidationError
from elastro.core.logger import get_logger

logger = get_logger(__name__)


class MLManager(BaseManager):
    """Thin wrapper around Elasticsearch ML job and datafeed APIs."""

    def _es(self) -> Any:
        self._ensure_connected()
        return self._client.get_client()

    def put_job(
        self, job_id: str, body: Union[Mapping[str, Any], BaseModel]
    ) -> Dict[str, Any]:
        """Create an anomaly detection job."""
        if not job_id:
            raise ValidationError("Job ID cannot be empty")
        payload = dump_payload(body)
        if not payload:
            raise ValidationError("Job body cannot be empty")

        try:
            logger.debug("ml put_job job_id=%s", job_id)
            response = self._es().ml.put_job(job_id=job_id, body=payload)
            return self._handle_response(response)
        except ElasticModuleError:
            raise
        except Exception as exc:
            logger.error("ml put_job failed job_id=%s: %s", job_id, exc, exc_info=True)
            raise OperationError(f"Failed to put ML job {job_id}: {exc}") from exc

    def put_datafeed(
        self, datafeed_id: str, body: Union[Mapping[str, Any], BaseModel]
    ) -> Dict[str, Any]:
        """Create a datafeed attached to an anomaly detection job."""
        if not datafeed_id:
            raise ValidationError("Datafeed ID cannot be empty")
        payload = dump_payload(body)
        if not payload:
            raise ValidationError("Datafeed body cannot be empty")

        try:
            logger.debug("ml put_datafeed datafeed_id=%s", datafeed_id)
            response = self._es().ml.put_datafeed(datafeed_id=datafeed_id, body=payload)
            return self._handle_response(response)
        except ElasticModuleError:
            raise
        except Exception as exc:
            logger.error(
                "ml put_datafeed failed datafeed_id=%s: %s",
                datafeed_id,
                exc,
                exc_info=True,
            )
            raise OperationError(
                f"Failed to put ML datafeed {datafeed_id}: {exc}"
            ) from exc
