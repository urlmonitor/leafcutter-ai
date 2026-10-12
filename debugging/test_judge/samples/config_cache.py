"""Config cache that serves stale values when the DB is down (ConfigCache shape)."""
import time

REFRESH_SECONDS = 60
RETRY_SECONDS = 10


class ConfigCache:
    def __init__(self, fetch):
        self._fetch = fetch
        self._value = None
        self._last_refresh = 0.0
        self._last_attempt = 0.0

    def get(self):
        now = time.monotonic()
        refresh_due = now - self._last_refresh >= REFRESH_SECONDS
        retry_due = now - self._last_attempt >= RETRY_SECONDS
        if refresh_due and retry_due:
            self._last_attempt = now
            try:
                self._value = self._fetch()
                self._last_refresh = now
            except ConnectionError:
                pass  # serve the stale value
        return self._value
