"""Gated live CLI/API smoke. Skips when Elasticsearch is not reachable."""

from __future__ import annotations

import json
from typing import Any

import pytest
from click.testing import CliRunner

from elastro.cli.cli import cli
from elastro.core.cluster import ClusterManager
from elastro.health.manager import HealthManager

_SCRATCH_INDEX = "elastro-cli-smoke-live"


def _invoke(real_es_client, *args: str):
    return CliRunner().invoke(cli, list(args), obj=real_es_client)


def _json_payload(output: str) -> Any:
    text = output.strip()
    start = text.find("{")
    array = text.find("[")
    if start == -1 or (array != -1 and array < start):
        start = array
    if start == -1:
        raise AssertionError(f"no JSON in output: {output[-500:]}")
    return json.loads(text[start:])


@pytest.mark.integration
def test_live_allocation_explain_green_or_unassigned(real_es_client) -> None:
    result = ClusterManager(real_es_client).allocation_explain()
    assert isinstance(result, dict)
    if result.get("message"):
        assert "no unassigned shards" in str(result["message"]).lower()
    else:
        assert "index" in result or "current_state" in result


@pytest.mark.integration
def test_live_cluster_health_smoke(real_es_client) -> None:
    health = HealthManager(real_es_client).cluster_health()
    assert health.get("status") in {"green", "yellow", "red"}


@pytest.mark.integration
def test_live_cli_health_status_json(real_es_client) -> None:
    result = _invoke(real_es_client, "-o", "json", "health", "status")
    assert result.exit_code in (0, 2), result.output
    payload = _json_payload(result.stdout)
    assert payload.get("status") in {"green", "yellow", "red"}
    assert "_ __|" not in result.output


@pytest.mark.integration
def test_live_cli_cluster_allocation(real_es_client) -> None:
    result = _invoke(real_es_client, "-o", "json", "cluster", "allocation")
    assert result.exit_code == 0, result.output


@pytest.mark.integration
def test_live_cli_coverage_templates_list_no_cluster_needed(real_es_client) -> None:
    result = _invoke(real_es_client, "-o", "json", "coverage", "templates", "list")
    assert result.exit_code == 0, result.output
    rows = _json_payload(result.stdout)
    assert isinstance(rows, list)
    assert rows


@pytest.mark.integration
def test_live_cli_scratch_template_apply_and_cleanup(real_es_client) -> None:
    from elastro.core.ilm import IlmManager

    policy = "elastro-scratch-apm-traces"
    template = "elastro-scratch-apm-traces"
    pattern = "elastro-scratch-traces-*"
    es = real_es_client.get_client()
    try:
        result = _invoke(
            real_es_client,
            "-o",
            "json",
            "coverage",
            "templates",
            "apply",
            "apm-traces",
            "--yes",
            "--policy-name",
            policy,
            "--template-name",
            template,
            "--index-pattern",
            pattern,
        )
        assert result.exit_code == 0, result.output
        payload = _json_payload(result.stdout)
        assert payload.get("applied") is True
        assert payload.get("index_template_name") == template
        got = es.indices.get_index_template(name=template)
        names = [
            item.get("name")
            for item in (got.get("index_templates") or [])
            if isinstance(item, dict)
        ]
        assert template in names or got
    finally:
        try:
            es.indices.delete_index_template(name=template)
        except Exception:
            pass
        try:
            IlmManager(real_es_client).delete_policy(policy)
        except Exception:
            pass


@pytest.mark.integration
def test_live_cli_coverage_templates_apply_dry_run(real_es_client) -> None:
    result = _invoke(
        real_es_client,
        "-o",
        "json",
        "coverage",
        "templates",
        "apply",
        "apm-traces",
        "--dry-run",
    )
    assert result.exit_code == 0, result.output


@pytest.mark.integration
def test_live_cli_coverage_check_filebeat_pattern(real_es_client) -> None:
    result = _invoke(
        real_es_client,
        "-o",
        "json",
        "coverage",
        "check",
        "--pattern",
        "filebeat-*",
        "--window",
        "15m",
    )
    assert result.exit_code in (0, 2), result.output
    payload = _json_payload(result.stdout)
    assert payload.get("target") == "pattern:filebeat-*"


@pytest.mark.integration
def test_live_cli_coverage_service_does_not_count_stream_names(real_es_client) -> None:
    result = _invoke(
        real_es_client,
        "-o",
        "json",
        "coverage",
        "check",
        "--service",
        "elasticsearch",
        "--window",
        "15m",
    )
    payload = _json_payload(result.stdout)
    streams = next(
        item
        for item in payload.get("checks") or []
        if item.get("name") == "streams_present"
    )
    if int(payload.get("doc_count") or 0) == 0:
        assert result.exit_code == 2, result.output
        assert streams.get("passed") is False
        assert "service.name=elasticsearch" in (streams.get("summary") or "")
    else:
        assert result.exit_code in (0, 2), result.output
        assert streams.get("passed") is True


@pytest.mark.integration
def test_live_cli_feature_disk_excludes_tls_finding(real_es_client) -> None:
    result = _invoke(
        real_es_client,
        "-o",
        "json",
        "health",
        "assess",
        "--feature",
        "disk",
        "--no-verbose-report",
    )
    assert result.exit_code in (0, 2), result.output
    payload = _json_payload(result.stdout)
    ids = {item.get("id") for item in payload.get("findings") or []}
    assert "security.tls.plain_http" not in ids


@pytest.mark.integration
def test_live_cli_index_then_search_with_refresh(real_es_client) -> None:
    from elastro.core.document import DocumentManager
    from elastro.core.index import IndexManager

    indices = IndexManager(real_es_client)
    docs = DocumentManager(real_es_client)
    if indices.exists(_SCRATCH_INDEX):
        indices.delete(_SCRATCH_INDEX)
    try:
        create = _invoke(
            real_es_client,
            "index",
            "create",
            _SCRATCH_INDEX,
            "--shards",
            "1",
            "--replicas",
            "0",
        )
        assert create.exit_code == 0, create.output
        indexed = CliRunner().invoke(
            cli,
            ["doc", "index", _SCRATCH_INDEX, "--id", "1"],
            obj=real_es_client,
            input='{"name":"Laptop","category":"electronics"}\n',
        )
        assert indexed.exit_code == 0, indexed.output
        search = _invoke(
            real_es_client,
            "doc",
            "search",
            _SCRATCH_INDEX,
            "--term",
            "category=electronics",
        )
        assert search.exit_code == 0, search.output
        hits = docs.search(
            _SCRATCH_INDEX,
            {"term": {"category": "electronics"}},
        )
        total = hits.get("hits", {}).get("total", {})
        count = total.get("value", total) if isinstance(total, dict) else total
        assert int(count) >= 1
    finally:
        if indices.exists(_SCRATCH_INDEX):
            indices.delete(_SCRATCH_INDEX)


@pytest.mark.integration
def test_live_cli_utils_templates_lists(real_es_client) -> None:
    result = _invoke(real_es_client, "-o", "json", "utils", "templates")
    assert result.exit_code == 0, result.output


@pytest.mark.integration
def test_live_cli_fleet_status_does_not_require_es(real_es_client) -> None:
    result = _invoke(real_es_client, "coverage", "fleet", "status")
    assert result.exit_code == 2, result.output
    assert "Fleet is disabled" in result.output or "Fleet" in result.output
