"""Unit tests for the QueryBuilder class."""

import pytest
from elastro.advanced.query_builder import QueryBuilder, BoolQueryBuilder


class TestQueryBuilder:
    """Test suite for QueryBuilder class."""

    def test_match_query(self):
        """Test creating a match query."""
        query = QueryBuilder().match(
            "title", "elasticsearch", operator="and", fuzziness="AUTO"
        )

        expected = {
            "match": {
                "title": {
                    "query": "elasticsearch",
                    "operator": "and",
                    "fuzziness": "AUTO",
                }
            }
        }

        assert query.to_dict() == expected

    def test_match_query_without_fuzziness(self):
        """Test creating a match query without fuzziness."""
        query = QueryBuilder().match("title", "elasticsearch", operator="or")

        expected = {"match": {"title": {"query": "elasticsearch", "operator": "or"}}}

        assert query.to_dict() == expected

    def test_match_phrase_query(self):
        """Test creating a match_phrase query."""
        query = QueryBuilder().match_phrase("description", "quick brown fox", slop=1)

        expected = {
            "match_phrase": {"description": {"query": "quick brown fox", "slop": 1}}
        }

        assert query.to_dict() == expected

    def test_term_query(self):
        """Test creating a term query."""
        query = QueryBuilder().term("status", "active")

        expected = {"term": {"status": "active"}}

        assert query.to_dict() == expected

    def test_terms_query(self):
        """Test creating a terms query."""
        query = QueryBuilder().terms("tags", ["elasticsearch", "python", "query"])

        expected = {"terms": {"tags": ["elasticsearch", "python", "query"]}}

        assert query.to_dict() == expected

    def test_range_query_with_all_parameters(self):
        """Test creating a range query with all parameters."""
        query = QueryBuilder().range("age", gte=25, lte=50, gt=None, lt=None)

        expected = {"range": {"age": {"gte": 25, "lte": 50}}}

        assert query.to_dict() == expected

    def test_range_query_with_partial_parameters(self):
        """Test creating a range query with partial parameters."""
        query = QueryBuilder().range("created_date", gt="2022-01-01", lt="2023-01-01")

        expected = {"range": {"created_date": {"gt": "2022-01-01", "lt": "2023-01-01"}}}

        assert query.to_dict() == expected

    def test_exists_query(self):
        """Test creating an exists query."""
        query = QueryBuilder().exists("email")

        expected = {"exists": {"field": "email"}}

        assert query.to_dict() == expected

    def test_wildcard_query(self):
        """Test creating a wildcard query."""
        query = QueryBuilder().wildcard("name", "jo*n")

        expected = {"wildcard": {"name": "jo*n"}}

        assert query.to_dict() == expected


class TestBoolQueryBuilder:
    """Test suite for BoolQueryBuilder class."""

    def test_empty_bool_query(self):
        """Test creating an empty bool query."""
        query = QueryBuilder().bool().build()

        expected = {"bool": {}}

        assert query.to_dict() == expected

    def test_must_clause_with_query_builder(self):
        """Test adding a must clause with a QueryBuilder instance."""
        match_query = QueryBuilder().match("title", "elasticsearch")
        query = QueryBuilder().bool().must(match_query).build()

        expected = {
            "bool": {
                "must": [
                    {"match": {"title": {"query": "elasticsearch", "operator": "or"}}}
                ]
            }
        }

        assert query.to_dict() == expected

    def test_must_clause_with_dict(self):
        """Test adding a must clause with a dictionary."""
        match_query_dict = {"match": {"title": "elasticsearch"}}
        query = QueryBuilder().bool().must(match_query_dict).build()

        expected = {"bool": {"must": [{"match": {"title": "elasticsearch"}}]}}

        assert query.to_dict() == expected

    def test_must_not_clause(self):
        """Test adding a must_not clause."""
        term_query = QueryBuilder().term("status", "inactive")
        query = QueryBuilder().bool().must_not(term_query).build()

        expected = {"bool": {"must_not": [{"term": {"status": "inactive"}}]}}

        assert query.to_dict() == expected

    def test_should_clause(self):
        """Test adding a should clause."""
        match_query = QueryBuilder().match("title", "elasticsearch")
        match_phrase_query = QueryBuilder().match_phrase("description", "search engine")

        query = (
            QueryBuilder().bool().should(match_query).should(match_phrase_query).build()
        )

        expected = {
            "bool": {
                "should": [
                    {"match": {"title": {"query": "elasticsearch", "operator": "or"}}},
                    {
                        "match_phrase": {
                            "description": {"query": "search engine", "slop": 0}
                        }
                    },
                ]
            }
        }

        assert query.to_dict() == expected

    def test_filter_clause(self):
        """Test adding a filter clause."""
        range_query = QueryBuilder().range("age", gte=18, lte=65)
        query = QueryBuilder().bool().filter(range_query).build()

        expected = {"bool": {"filter": [{"range": {"age": {"gte": 18, "lte": 65}}}]}}

        assert query.to_dict() == expected

    def test_minimum_should_match(self):
        """Test setting minimum_should_match."""
        query = (
            QueryBuilder()
            .bool()
            .should(QueryBuilder().match("title", "elastic"))
            .should(QueryBuilder().match("title", "search"))
            .should(QueryBuilder().match("title", "database"))
            .minimum_should_match(2)
            .build()
        )

        expected = {
            "bool": {
                "should": [
                    {"match": {"title": {"query": "elastic", "operator": "or"}}},
                    {"match": {"title": {"query": "search", "operator": "or"}}},
                    {"match": {"title": {"query": "database", "operator": "or"}}},
                ],
                "minimum_should_match": 2,
            }
        }

        assert query.to_dict() == expected

    def test_complex_bool_query(self):
        """Test creating a complex bool query with multiple clauses."""
        query = (
            QueryBuilder()
            .bool()
            .must(QueryBuilder().match("title", "elasticsearch"))
            .must_not(QueryBuilder().term("status", "inactive"))
            .should(QueryBuilder().match_phrase("description", "search engine"))
            .filter(QueryBuilder().range("created_date", gte="2022-01-01"))
            .build()
        )

        expected = {
            "bool": {
                "must": [
                    {"match": {"title": {"query": "elasticsearch", "operator": "or"}}}
                ],
                "must_not": [{"term": {"status": "inactive"}}],
                "should": [
                    {
                        "match_phrase": {
                            "description": {"query": "search engine", "slop": 0}
                        }
                    }
                ],
                "filter": [{"range": {"created_date": {"gte": "2022-01-01"}}}],
            }
        }

        assert query.to_dict() == expected
