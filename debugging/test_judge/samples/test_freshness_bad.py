import unittest

from freshness import fresh_rows


class TestFreshness(unittest.TestCase):
    def test_no_null_volumes_in_recent_rows(self):
        rows = [{"id": 1, "buy_volume": None}, {"id": 2, "buy_volume": None}]
        for r in fresh_rows(rows):
            self.assertIsNotNone(r["buy_volume"])
