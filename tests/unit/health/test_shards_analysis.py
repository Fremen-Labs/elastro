"""Unit tests for shard size analysis."""

import json
import unittest
from pathlib import Path

from elastro.health.shards import analyze_shards, format_bytes, parse_store_size

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "health"


class TestShardAnalysis(unittest.TestCase):
    def setUp(self):
        self.rows = json.loads((FIXTURES / "cat_shards_mixed.json").read_text())

    def test_parse_store_size(self):
        self.assertEqual(parse_store_size("1.5mb"), 1572864)
        self.assertEqual(parse_store_size("512kb"), 524288)
        self.assertEqual(parse_store_size("60gb"), 60 * 1024**3)
        self.assertIsNone(parse_store_size(None))

    def test_format_bytes(self):
        self.assertEqual(format_bytes(1024), "1.0 KB")
        self.assertEqual(format_bytes(2.5 * 1024**3), "2.5 GB")

    def test_analyze_detects_oversharded_and_undersharded(self):
        analysis = analyze_shards(self.rows)
        self.assertEqual(analysis.total_shards, 6)
        self.assertEqual(analysis.unassigned_count, 1)
        self.assertEqual(analysis.oversharded_count, 4)
        self.assertEqual(analysis.undersharded_count, 1)
        self.assertGreater(analysis.avg_bytes, 0)

    def test_analyze_summary_shape(self):
        analysis = analyze_shards(self.rows)
        summary = (
            f"Total shards: {analysis.total_shards:,}\n"
            f"Avg size: {format_bytes(analysis.avg_bytes)}"
        )
        self.assertIn("Total shards: 6", summary)
        self.assertIn("Avg size:", summary)


if __name__ == "__main__":
    unittest.main()
