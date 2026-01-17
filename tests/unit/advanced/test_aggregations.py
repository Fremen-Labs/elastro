"""Unit tests for AggregationBuilder."""

import pytest
from elastro.advanced.aggregations import AggregationBuilder


class TestAggregationBuilder:
    """Tests for the AggregationBuilder class."""

    def test_init_creates_empty_aggregations(self):
        """Test that initialization creates an empty aggregations dict."""
        builder = AggregationBuilder()
        assert builder.to_dict() == {}

    def test_terms_aggregation(self):
        """Test terms aggregation creation."""
        builder = AggregationBuilder()
        result = builder.terms("my_terms", "field1", size=15, min_doc_count=2)

        # Verify method chaining works
        assert result is builder

        # Verify the aggregation was built correctly
        expected = {
            "my_terms": {"terms": {"field": "field1", "size": 15, "min_doc_count": 2}}
        }
        assert builder.to_dict() == expected

    def test_terms_aggregation_without_optional_params(self):
        """Test terms aggregation without optional parameters."""
        builder = AggregationBuilder()
        builder.terms("my_terms", "field1")

        expected = {"my_terms": {"terms": {"field": "field1", "size": 10}}}
        assert builder.to_dict() == expected

    def test_date_histogram_aggregation(self):
        """Test date_histogram aggregation creation with all parameters."""
        builder = AggregationBuilder()
        result = builder.date_histogram(
            "my_date_histogram", "date_field", "day", "yyyy-MM-dd"
        )

        # Verify method chaining works
        assert result is builder

        # Verify the aggregation was built correctly
        expected = {
            "my_date_histogram": {
                "date_histogram": {
                    "field": "date_field",
                    "interval": "day",
                    "format": "yyyy-MM-dd",
                }
            }
        }
        assert builder.to_dict() == expected

    def test_date_histogram_without_format(self):
        """Test date_histogram aggregation without format parameter."""
        builder = AggregationBuilder()
        builder.date_histogram("my_date_histogram", "date_field", "month")

        expected = {
            "my_date_histogram": {
                "date_histogram": {"field": "date_field", "interval": "month"}
            }
        }
        assert builder.to_dict() == expected

    def test_histogram_aggregation(self):
        """Test histogram aggregation creation."""
        builder = AggregationBuilder()
        result = builder.histogram("my_histogram", "numeric_field", 5.0)

        # Verify method chaining works
        assert result is builder

        # Verify the aggregation was built correctly
        expected = {
            "my_histogram": {"histogram": {"field": "numeric_field", "interval": 5.0}}
        }
        assert builder.to_dict() == expected

    def test_range_aggregation(self):
        """Test range aggregation creation."""
        builder = AggregationBuilder()
        ranges = [{"to": 50}, {"from": 50, "to": 100}, {"from": 100}]
        result = builder.range("my_range", "numeric_field", ranges)

        # Verify method chaining works
        assert result is builder

        # Verify the aggregation was built correctly
        expected = {"my_range": {"range": {"field": "numeric_field", "ranges": ranges}}}
        assert builder.to_dict() == expected

    def test_metric_aggregations(self):
        """Test all metric aggregation types."""
        builder = AggregationBuilder()
        builder.avg("avg_agg", "value_field")
        builder.sum("sum_agg", "value_field")
        builder.min("min_agg", "value_field")
        builder.max("max_agg", "value_field")
        builder.cardinality("unique_count", "category_field")

        expected = {
            "avg_agg": {"avg": {"field": "value_field"}},
            "sum_agg": {"sum": {"field": "value_field"}},
            "min_agg": {"min": {"field": "value_field"}},
            "max_agg": {"max": {"field": "value_field"}},
            "unique_count": {"cardinality": {"field": "category_field"}},
        }
        assert builder.to_dict() == expected

    def test_nested_aggregations(self):
        """Test adding nested aggregations."""
        parent_builder = AggregationBuilder()
        parent_builder.terms("top_terms", "category")

        child_builder = AggregationBuilder()
        child_builder.avg("avg_price", "price")
        child_builder.max("max_price", "price")

        result = parent_builder.nested_agg("top_terms", child_builder)

        # Verify method chaining works
        assert result is parent_builder

        # Verify the nested aggregation was built correctly
        expected = {
            "top_terms": {
                "terms": {"field": "category", "size": 10},
                "aggs": {
                    "avg_price": {"avg": {"field": "price"}},
                    "max_price": {"max": {"field": "price"}},
                },
            }
        }
        assert parent_builder.to_dict() == expected

    def test_nested_agg_with_nonexistent_parent(self):
        """Test that nested_agg raises error for nonexistent parent."""
        parent_builder = AggregationBuilder()
        child_builder = AggregationBuilder()
        child_builder.avg("avg_price", "price")

        with pytest.raises(ValueError) as excinfo:
            parent_builder.nested_agg("nonexistent", child_builder)

        assert "Parent aggregation 'nonexistent' does not exist" in str(excinfo.value)

    def test_multiple_aggregations(self):
        """Test building multiple aggregations together."""
        builder = AggregationBuilder()
        builder.terms("categories", "category", size=5)
        builder.date_histogram("sales_over_time", "sale_date", "month")

        expected = {
            "categories": {"terms": {"field": "category", "size": 5}},
            "sales_over_time": {
                "date_histogram": {"field": "sale_date", "interval": "month"}
            },
        }
        assert builder.to_dict() == expected
