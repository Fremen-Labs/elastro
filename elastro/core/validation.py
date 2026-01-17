"""
Validation module.

This module provides functionality for validating Elasticsearch operations.
"""

from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, ValidationError as PydanticValidationError, Field, field_validator, ConfigDict
from elastro.core.errors import ValidationError


class IndexSettings(BaseModel):
    """Pydantic model for index settings validation."""
    number_of_shards: int = Field(ge=1, default=1)
    number_of_replicas: int = Field(ge=0, default=1)
    refresh_interval: Optional[str] = None
    max_result_window: Optional[int] = Field(None, ge=1, le=10000)

    model_config = ConfigDict(extra="allow")


class MappingProperty(BaseModel):
    """Pydantic model for mapping property validation."""
    type: str
    analyzer: Optional[str] = None
    format: Optional[str] = None
    fields: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="allow")


class IndexMappings(BaseModel):
    """Pydantic model for index mappings validation."""
    properties: Dict[str, Dict[str, Any]]

    @field_validator('properties')
    def validate_properties(cls, v):
        """Validate that properties conform to Elasticsearch mapping types."""
        valid_types = {
            "text", "keyword", "date", "long", "integer",
            "short", "byte", "double", "float", "boolean",
            "object", "nested", "geo_point", "geo_shape",
            "ip", "scaled_float", "flattened", "half_float",
            "binary", "search_as_you_type", "alias"
        }

        for field, config in v.items():
            if "type" in config and config["type"] not in valid_types:
                raise ValueError(f"Invalid field type '{config['type']}' for field '{field}'")
        return v

    model_config = ConfigDict(extra="allow")


class QueryModel(BaseModel):
    """Base model for query validation."""
    model_config = ConfigDict(extra="allow")


class MatchQuery(QueryModel):
    """Model for match query validation."""
    match: Dict[str, Any]


class TermQuery(QueryModel):
    """Model for term query validation."""
    term: Dict[str, Any]


class BoolQuery(QueryModel):
    """Model for bool query validation."""
    bool: Dict[str, List[Dict[str, Any]]]


class RangeQuery(QueryModel):
    """Model for range query validation."""
    range: Dict[str, Dict[str, Any]]


class DatastreamSettings(BaseModel):
    """Pydantic model for datastream settings validation."""
    indices_config: Dict[str, Any] = Field(default_factory=dict)
    retention_config: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="allow")


class Validator:
    """
    Validator for Elasticsearch operations.

    This class provides methods for validating index settings, mappings,
    documents, queries, and other Elasticsearch operations.
    """

    def validate_index_settings(self, settings: Dict[str, Any]) -> None:
        """
        Validate index settings.

        Args:
            settings: Index settings

        Raises:
            ValidationError: If settings validation fails
        """
        try:
            # Extract the settings from the expected Elasticsearch format
            index_settings = settings.get("settings", {}).get("index", {})
            if not index_settings and "number_of_shards" in settings:
                # If directly provided without nesting
                index_settings = settings

            validated_settings = IndexSettings(**index_settings)
            return validated_settings.model_dump(exclude_none=True)
        except PydanticValidationError as e:
            error_messages = [f"{err['loc'][0]}: {err['msg']}" for err in e.errors()]
            raise ValidationError(f"Invalid index settings: {', '.join(error_messages)}")

    def validate_index_mappings(self, mappings: Dict[str, Any]) -> None:
        """
        Validate index mappings.

        Args:
            mappings: Index mappings

        Raises:
            ValidationError: If mappings validation fails
        """
        try:
            # Handle the case where mappings might be nested under 'mappings'
            if "mappings" in mappings and isinstance(mappings["mappings"], dict):
                mappings_data = mappings["mappings"]
            else:
                mappings_data = mappings

            validated_mappings = IndexMappings(**mappings_data)
            return validated_mappings.model_dump(exclude_none=True)
        except PydanticValidationError as e:
            error_messages = [f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in e.errors()]
            raise ValidationError(f"Invalid index mappings: {', '.join(error_messages)}")

    def validate_document_schema(
        self, document: Dict[str, Any], schema: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Validate document against schema.

        Args:
            document: Document data
            schema: Schema for validation

        Raises:
            ValidationError: If document validation fails
        """
        if not schema:
            # If no schema provided, we just check that document is a valid JSON object
            if not isinstance(document, dict):
                raise ValidationError("Document must be a valid JSON object")
            return document

        try:
            # Instead of dynamically creating a model, we'll manually validate the document
            # based on the schema
            for field_name, field_config in schema.items():
                field_type = field_config.get("type")
                if field_name in document:
                    value = document[field_name]
                    
                    # Validate based on Elasticsearch types
                    if field_type == "text" or field_type == "keyword":
                        if value is not None and not isinstance(value, str):
                            raise ValidationError(f"Field '{field_name}' must be a string")
                    elif field_type == "integer" or field_type == "long":
                        if value is not None and not isinstance(value, int):
                            raise ValidationError(f"Field '{field_name}' must be an integer")
                    elif field_type == "float" or field_type == "double":
                        if value is not None and not (isinstance(value, float) or isinstance(value, int)):
                            raise ValidationError(f"Field '{field_name}' must be a number")
                    elif field_type == "boolean":
                        if value is not None and not isinstance(value, bool):
                            raise ValidationError(f"Field '{field_name}' must be a boolean")
                    elif field_type == "date":
                        if value is not None and not isinstance(value, str):
                            raise ValidationError(f"Field '{field_name}' must be a string for date")
            
            return document
            
        except Exception as e:
            if isinstance(e, ValidationError):
                raise
            raise ValidationError(f"Document validation failed: {str(e)}")

    def validate_query(self, query: Dict[str, Any]) -> None:
        """
        Validate Elasticsearch query.

        Args:
            query: Elasticsearch query

        Raises:
            ValidationError: If query validation fails
        """
        try:
            # Determine query type
            if "match" in query:
                model_cls = MatchQuery
            elif "term" in query:
                model_cls = TermQuery
            elif "bool" in query:
                model_cls = BoolQuery
            elif "range" in query:
                model_cls = RangeQuery
            else:
                # For other query types, use base query model
                model_cls = QueryModel

            validated_query = model_cls(**query)
            return validated_query.model_dump(exclude_none=True)
        except PydanticValidationError as e:
            error_messages = [f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in e.errors()]
            raise ValidationError(f"Invalid query: {', '.join(error_messages)}")

    def validate_datastream_settings(self, settings: Dict[str, Any]) -> None:
        """
        Validate datastream settings.

        Args:
            settings: Datastream settings

        Raises:
            ValidationError: If settings validation fails
        """
        try:
            validated_settings = DatastreamSettings(**settings)
            result = validated_settings.model_dump(exclude_none=True)
            # Ensure retention_config is always in the result, even if None
            if "retention_config" not in result:
                result["retention_config"] = None
            return result
        except PydanticValidationError as e:
            error_messages = [f"{err['loc'][0]}: {err['msg']}" for err in e.errors()]
            raise ValidationError(f"Invalid datastream settings: {', '.join(error_messages)}")
