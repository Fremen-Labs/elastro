"""Execute advertised elastro.fremenlabs.com Python snippets without a cluster."""

from __future__ import annotations

from elastro.advanced import AggregationBuilder, QueryBuilder


def test_homepage_hero_querybuilder() -> None:
    query_builder = QueryBuilder()
    bool_query = query_builder.bool()
    bool_query.must(QueryBuilder().match("name", "laptop"))
    bool_query.must(QueryBuilder().range("price", gte=500, lte=2000))
    query = query_builder.build()
    assert "bool" in query
    assert len(query["bool"]["must"]) == 2


def test_docs_python_api_chained_match_range() -> None:
    query_builder = QueryBuilder()
    query_builder.match("name", "laptop")
    query_builder.range("price", gte=500, lte=2000)
    query = query_builder.build()
    assert query["bool"]["must"][0]["match"]["name"]["query"] == "laptop"


def test_docs_aggregation_builder_build() -> None:
    agg_builder = AggregationBuilder()
    agg_builder.terms("brands", "brand")
    agg_builder.avg("avg_rating", "rating")
    agg_builder.min("min_price", "price")
    agg_builder.max("max_price", "price")
    aggregations = agg_builder.build()
    assert set(aggregations) == {"brands", "avg_rating", "min_price", "max_price"}


def test_quickstart_match_all() -> None:
    query_builder = QueryBuilder()
    query_builder.match_all()
    query = query_builder.build()
    assert query == {"match_all": {}}
