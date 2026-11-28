"""Unit tests for coverage TemplateManager."""

from unittest.mock import patch

import pytest

from elastro.core.errors import OperationError, ValidationError
from elastro.coverage.templates import TemplateManager


def test_beats_templates_omit_classic_index_patterns() -> None:
    filebeat = TemplateManager().apply("filebeat-logs", dry_run=True)
    metricbeat = TemplateManager().apply("metricbeat-metrics", dry_run=True)
    assert filebeat.index_template["index_patterns"] == ["logs-filebeat*"]
    assert metricbeat.index_template["index_patterns"] == ["metrics-metricbeat*"]
    assert filebeat.index_template["priority"] == 100
    assert "index.number_of_replicas" not in (
        filebeat.index_template.get("template") or {}
    ).get("settings", {})


def test_list_includes_shipped_templates() -> None:
    names = {info.name for info in TemplateManager().list()}
    assert names >= {
        "apm-traces",
        "apm-metrics",
        "filebeat-logs",
        "metricbeat-metrics",
    }


def test_apply_scratch_overrides_patterns_and_names() -> None:
    result = TemplateManager().apply(
        "apm-traces",
        dry_run=True,
        ilm_policy_name="elastro-scratch-apm",
        index_template_name="elastro-scratch-apm",
        index_patterns=["elastro-scratch-traces-*"],
    )
    assert result.ilm_policy_name == "elastro-scratch-apm"
    assert result.index_template_name == "elastro-scratch-apm"
    assert result.index_template["index_patterns"] == ["elastro-scratch-traces-*"]
    assert result.index_template["template"]["settings"]["index.lifecycle.name"] == (
        "elastro-scratch-apm"
    )


def test_apply_dry_run_does_not_put(es_client) -> None:
    result = TemplateManager(es_client).apply("apm-traces", dry_run=True)
    assert result.dry_run is True
    assert result.applied is False
    assert result.ilm_policy_name == "elastro-apm-traces"
    assert "phases" in result.ilm_policy["policy"]
    es_client.get_client().ilm.put_lifecycle.assert_not_called()
    es_client.client.indices.put_index_template.assert_not_called()


def test_apply_metricbeat_alias_and_overrides(es_client) -> None:
    es_client.client.ilm.put_lifecycle.return_value = {"acknowledged": True}
    es_client.client.indices.put_index_template.return_value = {"acknowledged": True}
    result = TemplateManager(es_client).apply(
        "metricbeat",
        ilm_policy_name="custom-metrics",
        retention_days=7,
        rollover_max_size="10gb",
        hot_max_age="6h",
        warm_min_age="6h",
    )
    assert result.applied is True
    assert result.name == "metricbeat-metrics"
    assert result.ilm_policy_name == "custom-metrics"
    phases = result.ilm_policy["policy"]["phases"]
    assert phases["delete"]["min_age"] == "7d"
    assert phases["hot"]["actions"]["rollover"]["max_primary_shard_size"] == "10gb"
    assert phases["hot"]["actions"]["rollover"]["max_age"] == "6h"
    assert phases["warm"]["min_age"] == "6h"
    settings = result.index_template["template"]["settings"]
    assert settings["index.lifecycle.name"] == "custom-metrics"
    es_client.get_client().ilm.put_lifecycle.assert_called_once()
    es_client.client.indices.put_index_template.assert_called_once()


def test_apply_unknown_name_raises_validation_error() -> None:
    with pytest.raises(ValidationError, match="Unknown coverage template"):
        TemplateManager().apply("not-a-template", dry_run=True)


def test_apply_without_client_raises() -> None:
    with pytest.raises(ValidationError, match="client is required"):
        TemplateManager().apply("apm-traces", dry_run=False)


def test_apply_ilm_failure_raises_operation_error(es_client) -> None:
    with patch("elastro.coverage.templates.IlmManager") as ilm_cls:
        ilm_cls.return_value.create_policy.side_effect = OperationError("put failed")
        with pytest.raises(OperationError, match="put failed"):
            TemplateManager(es_client).apply("apm-traces")
    es_client.client.indices.put_index_template.assert_not_called()


def test_list_include_applied_requires_client() -> None:
    with pytest.raises(ValidationError, match="applied status"):
        TemplateManager().list(include_applied=True)


def test_list_include_applied_marks_missing(es_client) -> None:
    with patch("elastro.coverage.templates.IlmManager") as ilm_cls:
        with patch("elastro.coverage.templates.IndexTemplateManager") as tmpl_cls:
            ilm_cls.return_value.get_policy.side_effect = OperationError("missing")
            tmpl_cls.return_value.get.return_value = {}
            infos = TemplateManager(es_client).list(include_applied=True)
    assert infos
    assert all(info.applied is False for info in infos)
