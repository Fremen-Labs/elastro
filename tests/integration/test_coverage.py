"""Integration tests for coverage templates and checks.

Skipped automatically when Elasticsearch is not reachable.
"""

from datetime import datetime, timezone

import pytest

from elastro.core.document import DocumentManager
from elastro.core.ilm import IlmManager
from elastro.core.index import IndexManager
from elastro.coverage.templates import TemplateManager
from elastro.coverage.validators import CoverageValidator
from elastro.utils.templates import TemplateManager as IndexTemplateManager


@pytest.mark.integration
class TestCoverageIntegration:
    def test_check_pattern_finds_recent_docs(self, real_es_client) -> None:
        index = "elastro-coverage-it"
        indices = IndexManager(real_es_client)
        documents = DocumentManager(real_es_client)
        if indices.exists(index):
            indices.delete(index)
        indices.create(
            index,
            mappings={
                "properties": {
                    "@timestamp": {"type": "date"},
                    "service": {"properties": {"name": {"type": "keyword"}}},
                    "host": {"properties": {"name": {"type": "keyword"}}},
                }
            },
        )
        try:
            documents.index(
                index,
                "1",
                {
                    "@timestamp": datetime.now(timezone.utc).isoformat(),
                    "service": {"name": "it-service"},
                    "host": {"name": "it-host"},
                },
                refresh=True,
            )
            report = CoverageValidator(real_es_client).check_pattern(
                index, window="15m", min_docs=1, max_age="15m"
            )
            assert report.passed, [check.summary for check in report.checks]
            assert report.doc_count >= 1
        finally:
            if indices.exists(index):
                indices.delete(index)

    def test_apply_dry_run_does_not_create_policy(self, real_es_client) -> None:
        ilm = IlmManager(real_es_client)
        before = {item.get("name") for item in ilm.list_policies()}
        TemplateManager(real_es_client).apply("apm-traces", dry_run=True)
        after = {item.get("name") for item in ilm.list_policies()}
        assert before == after

    def test_apply_creates_ilm_policy_and_template(self, real_es_client) -> None:
        policy_name = "elastro-it-cov-traces"
        template_name = "elastro-apm-traces"
        ilm = IlmManager(real_es_client)
        templates = IndexTemplateManager(real_es_client)
        try:
            templates.delete(template_name)
        except Exception:
            pass
        try:
            ilm.delete_policy(policy_name)
        except Exception:
            pass

        result = TemplateManager(real_es_client).apply(
            "apm-traces", ilm_policy_name=policy_name
        )
        try:
            assert result.applied is True
            policy = ilm.get_policy(policy_name)
            body = policy.get("policy") if isinstance(policy, dict) else policy
            assert "phases" in (body or policy)
            fetched = templates.get(template_name)
            assert fetched
        finally:
            try:
                templates.delete(template_name)
            except Exception:
                pass
            try:
                ilm.delete_policy(policy_name)
            except Exception:
                pass
