"""
Unit tests for the ES|QL fluent query builder.
"""

import pytest

from elastro.core.esql.builder import ESQLQuery, _format_value

# ---------------------------------------------------------------------------
# Source command tests
# ---------------------------------------------------------------------------


class TestSourceCommands:
    """Test FROM and ROW source commands."""

    def test_from_simple(self):
        q = ESQLQuery("logs-*").build()
        assert q == "FROM logs-*"

    def test_from_classmethod(self):
        q = ESQLQuery.from_("logs-*").build()
        assert q == "FROM logs-*"

    def test_from_with_metadata(self):
        q = ESQLQuery.from_("logs-*", metadata=["_index", "_id"]).build()
        assert q == "FROM logs-* METADATA _index, _id"

    def test_row_single_field(self):
        q = ESQLQuery.row(name="Alice").build()
        assert q == 'ROW name = "Alice"'

    def test_row_multiple_fields(self):
        q = ESQLQuery.row(x=1, y=2.5, active=True).build()
        assert "x = 1" in q
        assert "y = 2.5" in q
        assert "active = true" in q

    def test_row_null_value(self):
        q = ESQLQuery.row(val=None).build()
        assert "val = null" in q

    def test_empty_query_raises(self):
        with pytest.raises(ValueError, match="empty"):
            ESQLQuery().build()


# ---------------------------------------------------------------------------
# Processing command tests
# ---------------------------------------------------------------------------


class TestProcessingCommands:
    """Test all processing commands."""

    def test_where(self):
        q = ESQLQuery("logs-*").where("status >= 400").build()
        assert "| WHERE status >= 400" in q

    def test_where_chained(self):
        q = (
            ESQLQuery("logs-*")
            .where("status >= 400")
            .where("@timestamp > now() - 1h")
            .build()
        )
        assert q.count("WHERE") == 2

    def test_eval_single(self):
        q = ESQLQuery("logs-*").eval("rate = bytes / duration").build()
        assert "| EVAL rate = bytes / duration" in q

    def test_eval_multiple(self):
        q = ESQLQuery("logs-*").eval("a = 1", "b = 2").build()
        assert "| EVAL a = 1, b = 2" in q

    def test_stats_without_by(self):
        q = ESQLQuery("logs-*").stats("total = COUNT(*)").build()
        assert "| STATS total = COUNT(*)" in q
        assert "BY" not in q

    def test_stats_with_by_string(self):
        q = ESQLQuery("logs-*").stats("avg_bytes = AVG(bytes)", by="host").build()
        assert "| STATS avg_bytes = AVG(bytes) BY host" in q

    def test_stats_with_by_list(self):
        q = ESQLQuery("logs-*").stats("cnt = COUNT(*)", by=["host", "service"]).build()
        assert "BY host, service" in q

    def test_sort_asc(self):
        q = ESQLQuery("logs-*").sort("name").build()
        assert "| SORT name ASC" in q

    def test_sort_desc(self):
        q = ESQLQuery("logs-*").sort("timestamp", desc=True).build()
        assert "| SORT timestamp DESC" in q

    def test_sort_explicit_order(self):
        q = ESQLQuery("logs-*").sort("age", order="DESC").build()
        assert "| SORT age DESC" in q

    def test_sort_multiple_fields(self):
        q = ESQLQuery("logs-*").sort("host", "service", desc=True).build()
        assert "host DESC" in q
        assert "service DESC" in q

    def test_limit(self):
        q = ESQLQuery("logs-*").limit(25).build()
        assert "| LIMIT 25" in q

    def test_limit_invalid_raises(self):
        with pytest.raises(ValueError, match="positive integer"):
            ESQLQuery("logs-*").limit(-1).build()

    def test_limit_zero_raises(self):
        with pytest.raises(ValueError, match="positive integer"):
            ESQLQuery("logs-*").limit(0)

    def test_keep(self):
        q = ESQLQuery("logs-*").keep("name", "age", "status").build()
        assert "| KEEP name, age, status" in q

    def test_drop(self):
        q = ESQLQuery("logs-*").drop("_id", "_score").build()
        assert "| DROP _id, _score" in q

    def test_rename(self):
        q = ESQLQuery("logs-*").rename(old_name="new_name").build()
        assert "| RENAME old_name AS new_name" in q

    def test_dissect(self):
        q = ESQLQuery("logs-*").dissect("message", "%{ip} %{method}").build()
        assert '| DISSECT message "%{ip} %{method}"' in q

    def test_dissect_with_separator(self):
        q = ESQLQuery("logs-*").dissect("tags", "%{tag}", append_separator=",").build()
        assert 'APPEND_SEPARATOR=","' in q

    def test_grok(self):
        q = ESQLQuery("logs-*").grok("message", "%{IP:client} %{WORD:method}").build()
        assert '| GROK message "%{IP:client} %{WORD:method}"' in q

    def test_enrich_basic(self):
        q = ESQLQuery("logs-*").enrich("geo-policy").build()
        assert "| ENRICH geo-policy" in q

    def test_enrich_full(self):
        q = (
            ESQLQuery("logs-*")
            .enrich("geo-policy", on="client_ip", with_fields=["country", "city"])
            .build()
        )
        assert "ON client_ip" in q
        assert "WITH country, city" in q

    def test_mv_expand(self):
        q = ESQLQuery("logs-*").mv_expand("tags").build()
        assert "| MV_EXPAND tags" in q

    def test_pipe_raw(self):
        q = ESQLQuery("logs-*").pipe("WHERE custom_condition = true").build()
        assert "| WHERE custom_condition = true" in q


# ---------------------------------------------------------------------------
# Full pipeline tests
# ---------------------------------------------------------------------------


class TestFullPipeline:
    """Test complex multi-command queries."""

    def test_analytics_pipeline(self):
        q = (
            ESQLQuery("logs-*")
            .where("status_code >= 400")
            .where("@timestamp > now() - 1h")
            .stats("avg_response = AVG(response_time)", by="service.name")
            .sort("avg_response", desc=True)
            .limit(25)
            .build()
        )
        parts = q.split("\n| ")
        assert len(parts) == 6
        assert parts[0] == "FROM logs-*"
        assert parts[1] == "WHERE status_code >= 400"
        assert parts[5] == "LIMIT 25"

    def test_transform_pipeline(self):
        q = (
            ESQLQuery.from_("metrics-*", metadata=["_index"])
            .where("cpu > 90")
            .eval("cpu_pct = cpu / 100")
            .keep("host", "cpu_pct", "@timestamp")
            .sort("cpu_pct", desc=True)
            .limit(100)
            .build()
        )
        assert "FROM metrics-* METADATA _index" in q
        assert "EVAL cpu_pct = cpu / 100" in q
        assert "KEEP host, cpu_pct, @timestamp" in q

    def test_str_method(self):
        q = ESQLQuery("test-index").limit(5)
        assert str(q) == "FROM test-index\n| LIMIT 5"

    def test_repr_method(self):
        q = ESQLQuery("test-index").where("x > 1").limit(5)
        assert repr(q) == "ESQLQuery(commands=3)"


# ---------------------------------------------------------------------------
# Request body tests
# ---------------------------------------------------------------------------


class TestRequestBody:
    """Test to_request_body() serialization."""

    def test_basic_body(self):
        body = ESQLQuery("logs-*").limit(10).to_request_body()
        assert body["query"] == "FROM logs-*\n| LIMIT 10"
        assert "params" not in body
        assert "filter" not in body
        assert "columnar" not in body

    def test_body_with_params(self):
        body = ESQLQuery("logs-*").where("host = ?").to_request_body(params=["web-01"])
        assert body["params"] == ["web-01"]

    def test_body_with_filter(self):
        dsl_filter = {"term": {"environment": "production"}}
        body = ESQLQuery("logs-*").to_request_body(filter=dsl_filter)
        assert body["filter"] == dsl_filter

    def test_body_columnar(self):
        body = ESQLQuery("logs-*").to_request_body(columnar=True)
        assert body["columnar"] is True


# ---------------------------------------------------------------------------
# Value formatting tests
# ---------------------------------------------------------------------------


class TestFormatValue:
    """Test _format_value helper."""

    def test_string(self):
        assert _format_value("hello") == '"hello"'

    def test_string_with_quotes(self):
        assert _format_value('say "hi"') == '"say \\"hi\\""'

    def test_integer(self):
        assert _format_value(42) == "42"

    def test_float(self):
        assert _format_value(3.14) == "3.14"

    def test_bool_true(self):
        assert _format_value(True) == "true"

    def test_bool_false(self):
        assert _format_value(False) == "false"

    def test_none(self):
        assert _format_value(None) == "null"
