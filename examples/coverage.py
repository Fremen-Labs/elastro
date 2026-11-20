#!/usr/bin/env python3
"""Coverage templates, data-arrival checks, and a readiness report."""

from elastro import ElasticsearchClient
from elastro.coverage.readiness import ReadinessReporter
from elastro.coverage.templates import TemplateManager
from elastro.coverage.validators import CoverageValidator


def main() -> None:
    client = ElasticsearchClient()
    client.connect()

    templates = TemplateManager(client)
    print("Available templates:")
    for info in templates.list():
        print(f"  {info.name}: {info.description}")

    planned = templates.apply("apm-traces", dry_run=True)
    print(f"Dry-run ILM policy: {planned.ilm_policy_name}")
    print(f"Dry-run index template: {planned.index_template_name}")

    validator = CoverageValidator(client)
    report = validator.check_all(window="15m", min_docs=1)
    print(f"Coverage passed={report.passed} docs={report.doc_count}")
    for check in report.checks:
        print(f"  [{check.name}] passed={check.passed} {check.summary}")

    ready = ReadinessReporter(client).report(window="15m")
    print(f"Readiness passed={ready.passed} findings={len(ready.health_findings)}")


if __name__ == "__main__":
    main()
