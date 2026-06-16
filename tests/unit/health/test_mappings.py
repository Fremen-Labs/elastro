"""Unit tests for mapping field counting helpers."""

import unittest

from elastro.health.mappings import (
    count_mapping_fields,
    extract_field_limit,
    summarize_index_mapping,
)


class TestMappingHelpers(unittest.TestCase):
    def test_count_mapping_fields_includes_nested_and_multi_fields(self):
        properties = {
            "message": {
                "type": "text",
                "fields": {
                    "keyword": {"type": "keyword"},
                },
            },
            "user": {
                "type": "object",
                "properties": {
                    "id": {"type": "keyword"},
                    "name": {"type": "text"},
                },
            },
        }
        self.assertEqual(count_mapping_fields(properties), 5)

    def test_extract_field_limit_reads_index_setting(self):
        limit = extract_field_limit({"index": {"mapping.total_fields.limit": "750"}})
        self.assertEqual(limit, 750)

    def test_summarize_index_mapping_computes_ratio(self):
        summary = summarize_index_mapping(
            "logs-000001",
            {
                "mappings": {
                    "properties": {
                        "a": {"type": "keyword"},
                        "b": {"type": "keyword"},
                    }
                },
                "settings": {
                    "index": {"mapping.total_fields.limit": "10"},
                },
            },
        )
        self.assertEqual(summary["field_count"], 2)
        self.assertEqual(summary["field_limit"], 10)
        self.assertEqual(summary["field_ratio"], 0.2)


if __name__ == "__main__":
    unittest.main()
