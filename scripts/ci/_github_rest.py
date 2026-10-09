"""
MODULE: _github_rest
GOAL: A small stdlib-only GitHub REST client. Every request the post-merge
    follow-up workflow makes, read or write, passes through ``GitHubClient.request``.
BUSINESS CONTEXT: TQ-600a-13-iii. The notice job holds ``issues: write`` and
    nothing else, so the one place that talks to the service is also the one
    place that can be audited for what the job is able to do. Nothing here
    installs a dependency: the job runs on a bare runner.
ARCHITECTURE: ``GitHubClient(api_url, token)`` offers ``get`` / ``post`` /
    ``patch``, all delegating to ``request``. Every failure that crosses the
    process boundary (HTTP status, connection, undecodable body) is raised as
    ``GitHubError`` with the HTTP status (0 when none) so callers decide what a
    failed call means; this module never swallows one. The token is never
    logged or put in an exception message.
"""

from __future__ import annotations

import http.client
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger("github_rest")

API_VERSION = "2022-11-28"
DEFAULT_TIMEOUT_SECONDS = 30
ALLOWED_SCHEMES = frozenset({"http", "https"})


class GitHubError(RuntimeError):
    """A request to the service failed; ``status`` is the HTTP status, or 0 when none was received."""

    def __init__(self, message: str, status: int = 0) -> None:
        super().__init__(message)
        self.status = status


class GitHubClient:
    """Authenticated JSON client for one GitHub API root."""

    def __init__(self, api_url: str, token: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        scheme = urllib.parse.urlparse(api_url).scheme
        if scheme not in ALLOWED_SCHEMES:
            message = f"refusing API URL with scheme {scheme!r}"
            raise GitHubError(message)
        self._root = api_url.rstrip("/")
        self._token = token
        self._timeout = timeout

    def request(self, method: str, path: str, body: dict | None = None, query: dict | None = None):
        """Send one request and return the decoded JSON body (None for an empty body)."""
        url = f"{self._root}{path}"
        if query:
            url = f"{url}?{urllib.parse.urlencode(query)}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self._token}",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "leafcutter-post-merge-notice",
        }
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)  # noqa: S310 -- scheme checked in __init__
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as response:  # noqa: S310
                raw = response.read()
        except urllib.error.HTTPError as exc:
            logger.warning("%s %s -> HTTP %s", method, path, exc.code)
            message = f"{method} {path} failed with HTTP {exc.code}"
            raise GitHubError(message, exc.code) from exc
        except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
            logger.warning("%s %s -> %s", method, path, exc)
            message = f"{method} {path} failed: {exc}"
            raise GitHubError(message) from exc
        return self._decode(method, path, raw)

    @staticmethod
    def _decode(method: str, path: str, raw: bytes):
        """Decode a response body; an empty body is None, an undecodable one is an error."""
        if not raw:
            return None
        try:
            return json.loads(raw)
        except ValueError as exc:
            message = f"{method} {path} returned a body that is not JSON"
            raise GitHubError(message) from exc

    def get(self, path: str, query: dict | None = None):
        """GET ``path`` with an optional query mapping."""
        return self.request("GET", path, query=query)

    def post(self, path: str, body: dict):
        """POST a JSON ``body`` to ``path``."""
        return self.request("POST", path, body=body)

    def patch(self, path: str, body: dict):
        """PATCH ``path`` with a JSON ``body``."""
        return self.request("PATCH", path, body=body)
