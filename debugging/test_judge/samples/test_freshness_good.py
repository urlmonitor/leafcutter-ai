import unittest

from freshness import fresh_rows


class TestFreshness(unittest.TestCase):
    def test_only_filled_rows_are_fresh(self):
        rows = [{"id": 1, "buy_volume": None}, {"id": 2, "buy_volume": 1500.0}]
        result = fresh_rows(rows)
        self.assertEqual([r["id"] for r in result], [2])  # control row passes, NULL row excluded
