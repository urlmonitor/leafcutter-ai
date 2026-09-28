import time
import unittest
from unittest.mock import MagicMock

from config_cache import ConfigCache


class TestConfigCache(unittest.TestCase):
    def test_stale_cache_served_when_db_fails_on_refresh(self):
        fetch = MagicMock(return_value={"a": 1})
        cache = ConfigCache(fetch)
        cache.get()
        fetch.reset_mock()
        fetch.side_effect = ConnectionError
        past = time.monotonic() - 3600
        cache._last_refresh = past  # refresh is due
        cache._last_attempt = past  # retry is due too
        self.assertEqual(cache.get(), {"a": 1})
        fetch.assert_called_once()  # the refresh branch really ran
