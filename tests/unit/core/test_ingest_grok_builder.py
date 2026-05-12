"""
Unit tests for the deterministic GrokBuilder.

Tests preset matching, segment-based inference, cross-validation,
field uniqueness, and edge cases.
"""

from elastro.core.ingest.grok_builder import GrokBuilder, GrokResult


class TestPresets:
    def test_list_presets(self) -> None:
        builder = GrokBuilder()
        presets = builder.list_presets()
        assert "apache_combined" in presets
        assert "syslog" in presets
        assert "nginx_combined" in presets

    def test_get_preset(self) -> None:
        builder = GrokBuilder()
        result = builder.get_preset("syslog")
        assert result is not None
        assert result.preset_name == "syslog"
        assert result.confidence == 1.0
        assert "timestamp" in result.fields
        assert "hostname" in result.fields

    def test_get_preset_unknown(self) -> None:
        builder = GrokBuilder()
        assert builder.get_preset("nonexistent") is None

    def test_preset_fields_extracted(self) -> None:
        builder = GrokBuilder()
        result = builder.get_preset("apache_combined")
        assert result is not None
        assert "clientip" in result.fields
        assert "verb" in result.fields
        assert "response" in result.fields


class TestSegmentInference:
    def test_ip_address(self) -> None:
        builder = GrokBuilder()
        result = builder.build_pattern(["192.168.1.1"])
        assert "IP" in result.pattern or "IPV4" in result.pattern
        assert len(result.fields) >= 1

    def test_timestamp_iso8601(self) -> None:
        builder = GrokBuilder()
        result = builder.build_pattern(["2026-01-15T10:30:00.123Z"])
        assert "TIMESTAMP_ISO8601" in result.pattern

    def test_log_level(self) -> None:
        builder = GrokBuilder()
        result = builder.build_pattern(["ERROR something went wrong"])
        assert "LOGLEVEL" in result.pattern

    def test_uuid(self) -> None:
        builder = GrokBuilder()
        result = builder.build_pattern(["550e8400-e29b-41d4-a716-446655440000"])
        assert "UUID" in result.pattern

    def test_email_address(self) -> None:
        builder = GrokBuilder()
        result = builder.build_pattern(["user@example.com"])
        assert "EMAILADDRESS" in result.pattern

    def test_quoted_string(self) -> None:
        builder = GrokBuilder()
        result = builder.build_pattern(['"GET /index.html HTTP/1.1"'])
        assert "DATA" in result.pattern or "quoted" in str(result.fields)

    def test_simple_structured_log(self) -> None:
        builder = GrokBuilder()
        result = builder.build_pattern(
            ["2026-01-15T10:30:00Z INFO Starting application"]
        )
        assert "TIMESTAMP_ISO8601" in result.pattern
        assert "LOGLEVEL" in result.pattern
        assert len(result.fields) >= 2

    def test_ip_with_port(self) -> None:
        builder = GrokBuilder()
        result = builder.build_pattern(["192.168.1.1:8080"])
        # Should detect IP or HOSTPORT
        assert any(p in result.pattern for p in ("IPV4", "IP", "HOSTPORT"))


class TestCrossValidation:
    def test_multiple_samples_all_match(self) -> None:
        builder = GrokBuilder()
        result = builder.build_pattern(
            [
                "2026-01-15T10:30:00Z INFO hello",
                "2026-01-15T10:31:00Z ERROR world",
                "2026-01-15T10:32:00Z WARN test",
            ]
        )
        assert result.matched_samples == result.total_samples
        assert result.match_rate == 100.0

    def test_partial_match_reported(self) -> None:
        builder = GrokBuilder()
        result = builder.build_pattern(
            [
                "192.168.1.1 OK",
                "totally different format here!!!",
            ]
        )
        assert result.total_samples == 2
        # At least one should match (the first, which built the pattern)
        assert result.matched_samples >= 1
        if result.matched_samples < result.total_samples:
            assert len(result.warnings) > 0


class TestConfidence:
    def test_high_specificity_patterns(self) -> None:
        builder = GrokBuilder()
        result = builder.build_pattern(["192.168.1.1 2026-01-15T10:30:00Z ERROR crash"])
        assert result.confidence > 0.3

    def test_greedy_lowers_specificity(self) -> None:
        builder = GrokBuilder()
        # Use truly unstructured text with special chars
        result = builder.build_pattern(["??? ... ---"])
        # Should have lower confidence than structured logs
        assert result.confidence <= 0.9


class TestEdgeCases:
    def test_empty_samples(self) -> None:
        builder = GrokBuilder()
        result = builder.build_pattern([])
        assert result.pattern == "%{GREEDYDATA:message}"
        assert result.confidence == 0.0

    def test_blank_samples(self) -> None:
        builder = GrokBuilder()
        result = builder.build_pattern(["", "   ", "\n"])
        assert result.confidence == 0.0

    def test_single_word(self) -> None:
        builder = GrokBuilder()
        result = builder.build_pattern(["hello"])
        assert len(result.fields) >= 1

    def test_brackets_escaped(self) -> None:
        builder = GrokBuilder()
        result = builder.build_pattern(["[2026-01-15] INFO test"])
        # Opening bracket should be escaped
        assert "\\[" in result.pattern
        # Pattern should contain LOGLEVEL for INFO
        assert "LOGLEVEL" in result.pattern

    def test_field_name_uniqueness(self) -> None:
        builder = GrokBuilder()
        result = builder.build_pattern(["192.168.1.1 10.0.0.1 172.16.0.1"])
        # All three IPs should get unique field names
        unique_fields = set(result.fields)
        assert len(unique_fields) == len(result.fields)


class TestGrokResult:
    def test_match_rate(self) -> None:
        r = GrokResult(
            pattern="test",
            matched_samples=3,
            total_samples=4,
        )
        assert r.match_rate == 75.0

    def test_match_rate_zero(self) -> None:
        r = GrokResult(pattern="test", total_samples=0)
        assert r.match_rate == 0.0

    def test_to_processor_dict(self) -> None:
        r = GrokResult(
            pattern="%{IP:clientip} %{GREEDYDATA:msg}",
            fields=["clientip", "msg"],
        )
        proc = r.to_processor_dict("message")
        assert proc["grok"]["field"] == "message"
        assert proc["grok"]["patterns"] == ["%{IP:clientip} %{GREEDYDATA:msg}"]

    def test_to_processor_dict_with_custom_defs(self) -> None:
        r = GrokResult(
            pattern="%{MYPATTERN:field}",
            custom_definitions={"MYPATTERN": r"\d+-\w+"},
        )
        proc = r.to_processor_dict()
        assert "pattern_definitions" in proc["grok"]


class TestGrokToRegex:
    def test_named_capture(self) -> None:
        regex = GrokBuilder._grok_to_regex("%{IPV4:ip}")
        assert regex is not None
        import re

        m = re.match(regex, "192.168.1.1")
        assert m is not None
        assert m.group("ip") == "192.168.1.1"

    def test_unnamed_capture(self) -> None:
        regex = GrokBuilder._grok_to_regex("%{IPV4}")
        assert regex is not None
        import re

        m = re.match(regex, "10.0.0.1")
        assert m is not None

    def test_unresolvable_returns_none(self) -> None:
        regex = GrokBuilder._grok_to_regex("%{UNKNOWN_PATTERN:x}")
        # Should still produce something (falls back to \S+)
        assert regex is not None
