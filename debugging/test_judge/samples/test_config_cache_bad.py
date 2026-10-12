import time
import unittest
from unittest.mock import MagicMock

from config_cache import ConfigCache


class TestConfigCache(unittest.TestCase):
    def test_stale_cache_served_when_db_fails_on_refresh(self):
        fetch = MagicMock(return_value={"a": 1})
        cache = ConfigCache(fetch)
        cache.get()
        fetch.side_effect = ConnectionError
        cache._last_refresh = time.monotonic() - 3600  # refresh is due
        self.assertIsNotNone(cache.get())
