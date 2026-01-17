"""Aggregation builder for Elasticsearch aggregations."""

from typing import Any, Dict, List, Optional, Union


class AggregationBuilder:
    """Builder for Elasticsearch aggregation DSL.

    This class provides a fluent interface for building Elasticsearch aggregations
    without having to manually construct complex nested dictionaries.
    """

    def __init__(self) -> None:
        """Initialize an empty aggregation builder."""
        self._aggregations: Dict[str, Dict[str, Any]] = {}

    def terms(
        self, name: str, field: str, size: int = 10, min_doc_count: Optional[int] = None
    ) -> "AggregationBuilder":
        """Add a terms aggregation.

        Args:
            name: Name of the aggregation
            field: Field to aggregate on
            size: Maximum number of buckets to return
            min_doc_count: Minimum number of documents required to form a bucket

        Returns:
            Self for method chaining
        """
        agg = {"field": field, "size": size}
        if min_doc_count is not None:
            agg["min_doc_count"] = min_doc_count

        self._aggregations[name] = {"terms": agg}
        return self

    def date_histogram(
        self, name: str, field: str, interval: str, format: Optional[str] = None
    ) -> "AggregationBuilder":
        """Add a date_histogram aggregation.

        Args:
            name: Name of the aggregation
            field: Date field to aggregate on
            interval: Time interval (e.g. 'day', 'month', '1h')
            format: Date format pattern

        Returns:
            Self for method chaining
        """
        agg = {"field": field, "interval": interval}
        if format:
            agg["format"] = format

        self._aggregations[name] = {"date_histogram": agg}
        return self

    def histogram(self, name: str, field: str, interval: float) -> "AggregationBuilder":
        """Add a histogram aggregation.

        Args:
            name: Name of the aggregation
            field: Numeric field to aggregate on
            interval: Numeric interval for the buckets

        Returns:
            Self for method chaining
        """
        self._aggregations[name] = {"histogram": {"field": field, "interval": interval}}
        return self

    def range(
        self, name: str, field: str, ranges: List[Dict[str, Any]]
    ) -> "AggregationBuilder":
        """Add a range aggregation.

        Args:
            name: Name of the aggregation
            field: Numeric field to aggregate on
            ranges: List of range definitions (e.g. [{"to": 50}, {"from": 50, "to": 100}])

        Returns:
            Self for method chaining
        """
        self._aggregations[name] = {"range": {"field": field, "ranges": ranges}}
        return self

    def avg(self, name: str, field: str) -> "AggregationBuilder":
        """Add an avg metric aggregation.

        Args:
            name: Name of the aggregation
            field: Field to calculate the average on

        Returns:
            Self for method chaining
        """
        self._aggregations[name] = {"avg": {"field": field}}
        return self

    def sum(self, name: str, field: str) -> "AggregationBuilder":
        """Add a sum metric aggregation.

        Args:
            name: Name of the aggregation
            field: Field to calculate the sum on

        Returns:
            Self for method chaining
        """
        self._aggregations[name] = {"sum": {"field": field}}
        return self

    def min(self, name: str, field: str) -> "AggregationBuilder":
        """Add a min metric aggregation.

        Args:
            name: Name of the aggregation
            field: Field to find the minimum value on

        Returns:
            Self for method chaining
        """
        self._aggregations[name] = {"min": {"field": field}}
        return self

    def max(self, name: str, field: str) -> "AggregationBuilder":
        """Add a max metric aggregation.

        Args:
            name: Name of the aggregation
            field: Field to find the maximum value on

        Returns:
            Self for method chaining
        """
        self._aggregations[name] = {"max": {"field": field}}
        return self

    def cardinality(self, name: str, field: str) -> "AggregationBuilder":
        """Add a cardinality metric aggregation (unique count).

        Args:
            name: Name of the aggregation
            field: Field to count unique values on

        Returns:
            Self for method chaining
        """
        self._aggregations[name] = {"cardinality": {"field": field}}
        return self

    def nested_agg(
        self, parent_name: str, child_builder: "AggregationBuilder"
    ) -> "AggregationBuilder":
        """Add nested aggregations to a parent aggregation.

        Args:
            parent_name: Name of the parent aggregation
            child_builder: Another AggregationBuilder with child aggregations

        Returns:
            Self for method chaining
        """
        if parent_name not in self._aggregations:
            raise ValueError(f"Parent aggregation '{parent_name}' does not exist")

        self._aggregations[parent_name]["aggs"] = child_builder.to_dict()
        return self

    def to_dict(self) -> Dict[str, Dict[str, Any]]:
        """Convert the built aggregations to a dictionary.

        Returns:
            The complete aggregations as a dictionary
        """
        return self._aggregations
