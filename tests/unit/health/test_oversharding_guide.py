"""Unit tests for oversharding finding guide content."""

from elastro.health.finding_guides.oversharding import build_oversharding_guide
from elastro.health.rules.engine import RuleContext
from elastro.health.rules.oversharding import oversharding_findings


class TestOvershardingGuide:
    def test_build_guide_includes_elastic_specific_guidance(self):
        analysis = {
            "oversharded_count": 29,
            "measured_shards": 120,
            "total_shards": 150,
            "avg_bytes": 512 * 1024,
            "overshard_threshold_bytes": 1024 * 1024,
            "oversharded": [
                {
                    "index": "logs-000042",
                    "shard": "0",
                    "store_bytes": 2048,
                },
                {
                    "index": "logs-000042",
                    "shard": "1",
                    "store_bytes": 4096,
                },
                {
                    "index": "metrics-000010",
                    "shard": "0",
                    "store_bytes": 800,
                },
            ],
        }
        detail, metadata, affected = build_oversharding_guide(
            analysis,
            es_version="8.15.2",
        )

        assert "29" in detail
        assert "10GB and 50GB" in detail
        assert "search thread pool" in detail
        assert "max_primary_shard_size" in detail
        assert affected[0] == "logs-000042"
        sections = metadata["detail_sections"]
        assert sections["top_indices"][0]["index"] == "logs-000042"
        assert sections["top_indices"][0]["oversharded_shard_count"] == 2
        assert len(sections["resolution"]) >= 4
        assert any("elastic.co" in ref for ref in sections["references"])

    def test_rule_emits_detail_and_metadata(self):
        ctx = RuleContext(
            es_version="8.15.2",
            collector_data={
                "shards": {
                    "analysis": {
                        "oversharded_count": 29,
                        "undersharded_count": 0,
                        "measured_shards": 100,
                        "total_shards": 100,
                        "avg_bytes": 1024,
                        "overshard_threshold_bytes": 1024 * 1024,
                        "undershard_threshold_bytes": 50 * 1024**3,
                        "oversharded": [
                            {
                                "index": "logs-000001",
                                "shard": "0",
                                "store_bytes": 512,
                            }
                        ],
                    }
                }
            },
        )
        findings = oversharding_findings(ctx)
        oversharded = next(item for item in findings if item.id == "shards.oversharded")

        assert oversharded.detail is not None
        assert "OVERSHARDED" in oversharded.summary
        assert oversharded.metadata.get("detail_sections") is not None
        assert oversharded.remediation is not None
        assert "health shards --analyze" in oversharded.remediation.command