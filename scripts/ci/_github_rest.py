"""
MODULE: _github_rest
GOAL: A small stdlib-only GitHub REST client. Every request the post-merge
    follow-up workflow makes, read or write, passes through ``GitHubClient.request``.
BUSINESS CONTEXT: TQ-600a-13-iii. The notice job holds ``issues: write`` and
    nothing else, so the one place that talks to the service is also the one
    place that can be audited for what the job is able to do. Nothing here
    installs a dependency: the job runs on a bare runner.
ARCHITECTURE: ``GitHubClient(api_url, token)`` offers ``get`` / ``post`` /
    ``patch``, all delegating to ``request``.
    ``get_with_headers`` also returns the response headers (for a paginated
    ``Link``); ``same_origin_path`` turns a ``Link`` target into a request only when
    it stays on the API's origin, so the token never leaves it. Every failure that
    crosses the process boundary (HTTP status, connection, undecodable body) is raised as
    ``GitHubError`` with the HTTP status (0 when none) so callers decide what a
    failed call means; this module never swallows one. The token is never
    logged or put in an exception message. ``get_bytes`` (TQ-600a-13-xiii) is the
    one method that follows a redirect, exactly once and without the token.
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
REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
MAX_DOWNLOAD_BYTES = 10 * 1024 * 1024


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never follows a redirect on its own: a 3xx surfaces as an ``HTTPError`` the caller inspects."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, ARG002
        return None


_NO_REDIRECT_OPENER = urllib.request.build_opener(_NoRedirect)


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
        return self.request_with_headers(method, path, body, query)[0]

    def same_origin_path(self, url: str) -> str | None:
        """Return ``url`` as a path (with its query) below this client's API root, or None when it is anywhere else.

        A pagination ``Link`` is data from the service; requesting a URL on another origin would send the token
        there, so only a URL on the same scheme, host, port and path prefix is ever turned into a request.
        """
        root, target = urllib.parse.urlsplit(self._root), urllib.parse.urlsplit(url)
        if (target.scheme.lower(), target.netloc.lower()) != (root.scheme.lower(), root.netloc.lower()):
            return None
        if not (target.path == root.path or target.path.startswith(root.path.rstrip("/") + "/")):
            return None
        rest = target.path[len(root.path.rstrip("/")) :]
        return f"{rest}?{target.query}" if target.query else rest

    def request_with_headers(self, method: str, path: str, body: dict | None = None, query: dict | None = None):
        """Send one request and return ``(decoded JSON body, response headers)``; header names are lower-cased."""
        url = f"{self._root}{path}"
        if query:
            url = f"{url}?{urllib.parse.urlencode(query)}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "leafcutter-post-merge-notice",
        }
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)  # noqa: S310 -- scheme checked in __init__
        # An "unredirected" header is dropped by urllib when it follows a redirect, so the token cannot reach another origin.
        req.add_unredirected_header("Authorization", f"Bearer {self._token}")
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as response:  # noqa: S310
                if response.geturl() != req.full_url:  # a redirect was followed: whatever answered is not the API
                    logger.warning("%s %s -> redirected, refusing the answer", method, path)
                    message = f"{method} {path} was redirected; refusing the answer"
                    raise GitHubError(message)
                raw = response.read()
                headers = {name.lower(): ", ".join(response.headers.get_all(name) or []) for name in set(response.headers.keys())}
        except urllib.error.HTTPError as exc:
            logger.warning("%s %s -> HTTP %s", method, path, exc.code)
            message = f"{method} {path} failed with HTTP {exc.code}"
            raise GitHubError(message, exc.code) from exc
        except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
            logger.warning("%s %s -> %s", method, path, exc)
            message = f"{method} {path} failed: {exc}"
            raise GitHubError(message) from exc
        return self._decode(method, path, raw), headers

    @staticmethod
    def _decode(method: str, path: str, raw: bytes):
        """Decode a response body; an empty body is None, an undecodable one is an error."""
        if not raw:
            return None
        try:
            return json.loads(raw)
        except (ValueError, RecursionError) as exc:  # a hostile body nested past the interpreter's limit is not JSON we can read
            message = f"{method} {path} returned a body that is not JSON"
            raise GitHubError(message) from exc

    def get(self, path: str, query: dict | None = None):
        """GET ``path`` with an optional query mapping."""
        return self.request("GET", path, query=query)

    def get_with_headers(self, path: str, query: dict | None = None):
        """GET ``path``; return ``(decoded JSON body, response headers)`` (for a paginated ``Link`` header)."""
        return self.request_with_headers("GET", path, query=query)

    def get_bytes(self, path: str, max_bytes: int = MAX_DOWNLOAD_BYTES) -> bytes:
        """GET ``path`` and return the raw body; follows EXACTLY ONE redirect, without the token.

        The artifact zip endpoint answers with a 302 to a signed blob URL on another origin. The JSON
        ``request`` path refuses every redirect (the token must never leave the API); this method is the one
        exception: the first hop carries the token, the single redirect hop is a fresh request with no
        ``Authorization`` header (the signed URL is its own credential), and a second redirect is an error.
        A body longer than ``max_bytes`` is an error, never a truncated answer.
        """
        body, location = self._fetch(f"{self._root}{path}", True, max_bytes, path)
        if body is not None:
            return body
        target = urllib.parse.urljoin(f"{self._root}{path}", location or "")
        if urllib.parse.urlparse(target).scheme not in self._redirect_schemes():
            message = f"GET {path} redirected to a URL with a scheme this client refuses"
            raise GitHubError(message)
        body, location = self._fetch(target, False, max_bytes, path)
        if body is None:
            message = f"GET {path} was redirected more than once; refusing to follow"
            raise GitHubError(message)
        return body

    def _redirect_schemes(self) -> frozenset[str]:
        """The schemes a redirect target may have: https only, unless the configured API root is itself plain http."""
        return ALLOWED_SCHEMES if urllib.parse.urlparse(self._root).scheme == "http" else frozenset({"https"})

    @staticmethod
    def _failure(path: str, exc: Exception, first_hop: bool) -> GitHubError:
        """Log and build the error for a failed hop. The redirect hop names only the exception TYPE: its text can hold the signed URL."""
        status = getattr(exc, "code", 0) if isinstance(exc, urllib.error.HTTPError) else 0
        if not first_hop:
            logger.warning("GET %s redirect hop failed: %s", path, type(exc).__name__)
            return GitHubError(f"GET {path} redirect hop failed: {type(exc).__name__}", status)
        if status:
            logger.warning("GET %s -> HTTP %s", path, status)
            return GitHubError(f"GET {path} failed with HTTP {status}", status)
        logger.warning("GET %s -> %s", path, exc)
        return GitHubError(f"GET {path} failed: {exc}")

    def _fetch(self, url: str, send_token: bool, max_bytes: int, path: str) -> tuple[bytes | None, str | None]:
        """One no-redirect GET: ``(body, None)`` on success, ``(None, Location)`` on a redirect; else ``GitHubError``.

        The URL of a redirect target is never logged (a signed URL is a credential); ``path`` names the request.
        """
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": API_VERSION, "User-Agent": "leafcutter-post-merge-notice"}
        req = urllib.request.Request(url, headers=headers if send_token else {"User-Agent": headers["User-Agent"]}, method="GET")  # noqa: S310 -- scheme checked
        if send_token:
            req.add_unredirected_header("Authorization", f"Bearer {self._token}")
        try:
            with _NO_REDIRECT_OPENER.open(req, timeout=self._timeout) as response:
                raw = response.read(max_bytes + 1)
        except urllib.error.HTTPError as exc:
            location = exc.headers.get("Location") if exc.code in REDIRECT_STATUSES else None
            exc.close()
            if location:
                return None, location
            raise self._failure(path, exc, send_token) from (exc if send_token else None)
        except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
            raise self._failure(path, exc, send_token) from (exc if send_token else None)
        if len(raw) > max_bytes:
            message = f"GET {path} returned more than {max_bytes} bytes; refusing it"
            raise GitHubError(message)
        return raw, None

    def post(self, path: str, body: dict):
        """POST a JSON ``body`` to ``path``."""
        return self.request("POST", path, body=body)

    def patch(self, path: str, body: dict):
        """PATCH ``path`` with a JSON ``body``."""
        return self.request("PATCH", path, body=body)
