"""
Unit tests for the validation module.

This module tests the validation functionalities for Elasticsearch operations.
"""

import pytest
from typing import Dict, Any
from pydantic import ValidationError as PydanticValidationError

from elastro.core.validation import (
    IndexSettings,
    MappingProperty,
    IndexMappings,
    QueryModel,
    MatchQuery,
    TermQuery,
    BoolQuery,
    RangeQuery,
    DatastreamSettings,
    Validator,
)
from elastro.core.errors import ValidationError


class TestIndexSettings:
    """Tests for the IndexSettings model."""

    def test_valid_settings(self):
        """Test that valid settings pass validation."""
        settings = {
            "number_of_shards": 3,
            "number_of_replicas": 2,
            "refresh_interval": "5s",
            "max_result_window": 5000,
        }
        validated = IndexSettings(**settings)
        assert validated.number_of_shards == 3
        assert validated.number_of_replicas == 2
        assert validated.refresh_interval == "5s"
        assert validated.max_result_window == 5000

    def test_default_values(self):
        """Test that default values are set correctly."""
        settings = {}
        validated = IndexSettings(**settings)
        assert validated.number_of_shards == 1
        assert validated.number_of_replicas == 1
        assert validated.refresh_interval is None
        assert validated.max_result_window is None

    def test_invalid_shards(self):
        """Test that invalid number of shards raises error."""
        settings = {"number_of_shards": 0}
        with pytest.raises(PydanticValidationError):
            IndexSettings(**settings)

    def test_invalid_replicas(self):
        """Test that invalid number of replicas raises error."""
        settings = {"number_of_replicas": -1}
        with pytest.raises(PydanticValidationError):
            IndexSettings(**settings)

    def test_invalid_max_result_window(self):
        """Test that invalid max_result_window raises error."""
        settings = {"max_result_window": 20000}  # Exceeds limit of 10000
        with pytest.raises(PydanticValidationError):
            IndexSettings(**settings)


class TestMappingProperty:
    """Tests for the MappingProperty model."""

    def test_valid_property(self):
        """Test that valid mapping property passes validation."""
        property_data = {
            "type": "text",
            "analyzer": "english",
            "fields": {"keyword": {"type": "keyword"}},
        }
        validated = MappingProperty(**property_data)
        assert validated.type == "text"
        assert validated.analyzer == "english"
        assert validated.fields == {"keyword": {"type": "keyword"}}

    def test_required_fields(self):
        """Test that required fields are enforced."""
        property_data = {"analyzer": "english"}  # missing type
        with pytest.raises(PydanticValidationError):
            MappingProperty(**property_data)


class TestIndexMappings:
    """Tests for the IndexMappings model."""

    def test_valid_mappings(self):
        """Test that valid mappings pass validation."""
        mappings = {
            "properties": {
                "title": {"type": "text", "analyzer": "english"},
                "content": {"type": "text"},
                "date": {"type": "date", "format": "yyyy-MM-dd"},
                "tags": {"type": "keyword"},
            }
        }
        validated = IndexMappings(**mappings)
        assert "title" in validated.properties
        assert validated.properties["title"]["type"] == "text"

    def test_invalid_field_type(self):
        """Test that invalid field type raises validation error."""
        mappings = {"properties": {"title": {"type": "invalid_type"}}}
        with pytest.raises(ValueError):
            IndexMappings(**mappings)


class TestQueryModels:
    """Tests for the query model classes."""

    def test_match_query(self):
        """Test MatchQuery validation."""
        query = {"match": {"title": "search term"}}
        validated = MatchQuery(**query)
        assert validated.match == {"title": "search term"}

    def test_term_query(self):
        """Test TermQuery validation."""
        query = {"term": {"status": "active"}}
        validated = TermQuery(**query)
        assert validated.term == {"status": "active"}

    def test_bool_query(self):
        """Test BoolQuery validation."""
        query = {
            "bool": {
                "must": [{"match": {"title": "search"}}],
                "filter": [{"term": {"status": "active"}}],
            }
        }
        validated = BoolQuery(**query)
        assert "must" in validated.bool
        assert "filter" in validated.bool

    def test_range_query(self):
        """Test RangeQuery validation."""
        query = {"range": {"age": {"gte": 18, "lte": 65}}}
        validated = RangeQuery(**query)
        assert validated.range == {"age": {"gte": 18, "lte": 65}}


class TestDatastreamSettings:
    """Tests for the DatastreamSettings model."""

    def test_valid_settings(self):
        """Test that valid datastream settings pass validation."""
        settings = {
            "indices_config": {"number_of_shards": 1},
            "retention_config": {"min_age": "7d"},
        }
        validated = DatastreamSettings(**settings)
        assert validated.indices_config == {"number_of_shards": 1}
        assert validated.retention_config == {"min_age": "7d"}

    def test_default_values(self):
        """Test that default values are set correctly."""
        settings = {}
        validated = DatastreamSettings(**settings)
        assert validated.indices_config == {}
        assert validated.retention_config is None


class TestValidator:
    """Tests for the Validator class."""

    @pytest.fixture
    def validator(self):
        """Fixture to create a Validator instance."""
        return Validator()

    def test_validate_index_settings_valid(self, validator):
        """Test validating valid index settings."""
        settings = {
            "settings": {"index": {"number_of_shards": 3, "number_of_replicas": 2}}
        }
        validated = validator.validate_index_settings(settings)
        assert validated["number_of_shards"] == 3
        assert validated["number_of_replicas"] == 2

    def test_validate_index_settings_flat(self, validator):
        """Test validating flat index settings structure."""
        settings = {"number_of_shards": 3, "number_of_replicas": 2}
        validated = validator.validate_index_settings(settings)
        assert validated["number_of_shards"] == 3
        assert validated["number_of_replicas"] == 2

    def test_validate_index_settings_invalid(self, validator):
        """Test validating invalid index settings."""
        settings = {"settings": {"index": {"number_of_shards": 0}}}  # Invalid
        with pytest.raises(ValidationError):
            validator.validate_index_settings(settings)

    def test_validate_index_mappings_valid(self, validator):
        """Test validating valid index mappings."""
        mappings = {
            "mappings": {
                "properties": {"title": {"type": "text"}, "created": {"type": "date"}}
            }
        }
        validated = validator.validate_index_mappings(mappings)
        assert "properties" in validated
        assert "title" in validated["properties"]

    def test_validate_index_mappings_flat(self, validator):
        """Test validating flat index mappings structure."""
        mappings = {
            "properties": {"title": {"type": "text"}, "created": {"type": "date"}}
        }
        validated = validator.validate_index_mappings(mappings)
        assert "properties" in validated
        assert "title" in validated["properties"]

    def test_validate_index_mappings_invalid(self, validator):
        """Test validating invalid index mappings."""
        mappings = {
            "mappings": {
                "properties": {"status": {"type": "invalid_type"}}  # Invalid type
            }
        }
        with pytest.raises(ValidationError):
            validator.validate_index_mappings(mappings)

    def test_validate_document_no_schema(self, validator):
        """Test validating document without schema."""
        document = {"title": "Test", "content": "Content"}
        validated = validator.validate_document_schema(document)
        assert validated == document

    def test_validate_document_invalid_type(self, validator):
        """Test validating document with invalid type."""
        document = "not a dict"
        with pytest.raises(ValidationError):
            validator.validate_document_schema(document)

    def test_validate_document_with_schema(self, validator):
        """Test validating document with schema."""
        schema = {
            "title": {"type": "text"},
            "count": {"type": "integer"},
            "active": {"type": "boolean"},
        }
        document = {"title": "Test", "count": 5, "active": True}
        validated = validator.validate_document_schema(document, schema)
        assert validated["title"] == "Test"
        assert validated["count"] == 5
        assert validated["active"] is True

    def test_validate_document_schema_failure(self, validator):
        """Test validation failure with schema."""
        schema = {"count": {"type": "integer"}}
        document = {"count": "not an integer"}
        with pytest.raises(ValidationError):
            validator.validate_document_schema(document, schema)

    def test_validate_query_match(self, validator):
        """Test validating match query."""
        query = {"match": {"title": "test"}}
        validated = validator.validate_query(query)
        assert validated["match"] == {"title": "test"}

    def test_validate_query_term(self, validator):
        """Test validating term query."""
        query = {"term": {"status": "active"}}
        validated = validator.validate_query(query)
        assert validated["term"] == {"status": "active"}

    def test_validate_query_bool(self, validator):
        """Test validating bool query."""
        query = {
            "bool": {
                "must": [{"match": {"title": "test"}}],
                "must_not": [{"term": {"status": "inactive"}}],
            }
        }
        validated = validator.validate_query(query)
        assert "bool" in validated
        assert "must" in validated["bool"]

    def test_validate_query_range(self, validator):
        """Test validating range query."""
        query = {"range": {"age": {"gte": 18}}}
        validated = validator.validate_query(query)
        assert validated["range"] == {"age": {"gte": 18}}

    def test_validate_query_unknown_type(self, validator):
        """Test validating unknown query type."""
        query = {"custom_query": {"field": "value"}}
        validated = validator.validate_query(query)
        assert validated["custom_query"] == {"field": "value"}

    def test_validate_datastream_settings_valid(self, validator):
        """Test validating valid datastream settings."""
        settings = {
            "indices_config": {"number_of_shards": 1},
            "retention_config": {"min_age": "7d"},
        }
        validated = validator.validate_datastream_settings(settings)
        assert validated["indices_config"] == {"number_of_shards": 1}
        assert validated["retention_config"] == {"min_age": "7d"}

    def test_validate_datastream_settings_empty(self, validator):
        """Test validating empty datastream settings."""
        settings = {}
        validated = validator.validate_datastream_settings(settings)
        assert validated["indices_config"] == {}
        assert validated["retention_config"] is None
