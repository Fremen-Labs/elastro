"""Unit tests for health scoring."""

import unittest

from elastro.health.scoring import (
    compute_fallback_score,
    compute_weighted_score,
    indicator_status_score,
)


class TestScoring(unittest.TestCase):
    def test_indicator_status_score(self):
        self.assertEqual(indicator_status_score("green"), 100)
        self.assertEqual(indicator_status_score("yellow"), 50)
        self.assertEqual(indicator_status_score("red"), 0)

    def test_compute_fallback_score(self):
        self.assertEqual(compute_fallback_score("green"), 100)
        self.assertEqual(compute_fallback_score("yellow"), 70)

    def test_compute_weighted_score_empty(self):
        self.assertEqual(compute_weighted_score({}), 0)


if __name__ == "__main__":
    unittest.main()
