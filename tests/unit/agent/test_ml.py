"""Unit tests for MLManager."""

import pytest

from elastro.agent.ml import MLManager
from elastro.agent.models import (
    MlAnalysisConfig,
    MlDatafeedConfig,
    MlDetector,
    MlJobConfig,
)
from elastro.core.errors import OperationError, ValidationError


def test_put_job_and_datafeed(es_client) -> None:
    manager = MLManager(es_client)
    job = MlJobConfig(
        description="Elastro Scaffolded Job: detect 'high_mean' on 'response.time'",
        analysis_config=MlAnalysisConfig(
            detectors=[MlDetector(function="high_mean", field_name="response.time")]
        ),
        data_description={"time_field": "@timestamp"},
    )
    es_client.client.ml.put_job.return_value = {"job_id": "anomaly-job-01"}
    result = manager.put_job("anomaly-job-01", job)
    assert result["job_id"] == "anomaly-job-01"
    es_client.client.ml.put_job.assert_called_once_with(
        job_id="anomaly-job-01",
        body=job.model_dump(mode="json", exclude_none=True),
    )

    feed = MlDatafeedConfig(job_id="anomaly-job-01", indices=["logs-*"])
    es_client.client.ml.put_datafeed.return_value = {
        "datafeed_id": "datafeed-anomaly-job-01"
    }
    fed = manager.put_datafeed("datafeed-anomaly-job-01", feed)
    assert fed["datafeed_id"] == "datafeed-anomaly-job-01"
    es_client.client.ml.put_datafeed.assert_called_once_with(
        datafeed_id="datafeed-anomaly-job-01",
        body=feed.model_dump(mode="json", exclude_none=True),
    )


def test_put_job_empty_id_raises(es_client) -> None:
    with pytest.raises(ValidationError, match="Job ID cannot be empty"):
        MLManager(es_client).put_job("", {"description": "x"})


def test_put_job_operation_error(es_client) -> None:
    es_client.client.ml.put_job.side_effect = Exception("No node reached")
    with pytest.raises(OperationError, match="No node reached"):
        MLManager(es_client).put_job("job-1", {"description": "x"})


def test_put_datafeed_operation_error(es_client) -> None:
    es_client.client.ml.put_datafeed.side_effect = Exception("No node reached")
    with pytest.raises(OperationError, match="No node reached"):
        MLManager(es_client).put_datafeed(
            "datafeed-1", {"job_id": "job-1", "indices": ["logs-*"]}
        )
