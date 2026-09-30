"""
MODULE: kernel.providers.jev_http
GOAL: Direct-HTTP transport for TypeSafe System One (the judge.py request shape), used as the
    config-selectable fallback behind the same Jev adapter.
BUSINESS CONTEXT: langchain-typesafe is a 0.0.x beta pre-release; if its API shifts, the kernel
    must keep reaching Jev without a code change, so the raw /v1/systemone call stays available.
ARCHITECTURE: Implements the JevTransport protocol (send -> RawResponse) on httpx.AsyncClient.
    Transient failures (429, 5xx, timeouts, connection errors) raise JevTransientError; rejected
    credentials and other 4xx raise JevUnavailable; a malformed 2xx raises JevInvalidResponse.
    No retry happens here, the adapter owns retry policy.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from kernel.providers.base import JevInvalidResponse, JevUnavailable
from kernel.providers.jev_errors import JevTransientError
from kernel.providers.jev_wire import RawResponse, parse_body

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.typesafe.ai"
ENDPOINT_PATH = "/v1/systemone"
REQUEST_ID_HEADER = "x-typesafe-request-id"
_AUTH_STATUSES = frozenset({401, 403})


def retry_after_seconds(headers: httpx.Headers) -> float | None:
    """Return the server-requested delay from retry-after(-ms) headers, if valid."""
    for name, scale in (("retry-after-ms", 0.001), ("retry-after", 1.0)):
        raw = headers.get(name)
        if raw is None:
            continue
        try:
            value = float(raw.strip()) * scale
        except ValueError:
            continue
        if 0 <= value < float("inf"):
            return value
    return None


class HttpTransport:
    """Posts one System One request and returns the decoded response."""

    name = "http-direct"
    version = "1"

    def __init__(self, *, api_key: str, model: str, timeout_seconds: float,
                 base_url: str = DEFAULT_BASE_URL,
                 client: httpx.AsyncClient | None = None) -> None:
        """Create the transport.

        Args:
            api_key: Provider API key, sent only as a bearer header.
            model: Model name sent with every request (for example jev-latest).
            timeout_seconds: Per-request timeout for the client created here.
            base_url: API root; override for a gateway or test server.
            client: Optional injected client (tests, custom transport); never closed here
                unless the transport created it.
        """
        self._api_key = api_key
        self._model = model
        self._url = f"{base_url.rstrip('/')}{ENDPOINT_PATH}"
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)

    async def send(self, state: dict[str, Any], questions: dict[str, dict[str, Any]],
                   *, purpose: str = "") -> RawResponse:
        """Send one request.

        Args:
            state: JSON state shared by all questions.
            questions: Wire question objects keyed by id.
            purpose: Informational label for log lines.

        Returns:
            RawResponse: Decoded answers, model and usage.

        Raises:
            JevTransientError: Rate limit, 5xx, timeout or connection failure.
            JevUnavailable: Credentials rejected or request refused.
            JevInvalidResponse: The 2xx body is not valid JSON of the expected shape.
        """
        payload = {"model": self._model, "state": state, "questions": questions}
        headers = {"Authorization": f"Bearer {self._api_key}"}
        try:
            response = await self._client.post(self._url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            reason = f"timeout calling jev ({purpose})"
            raise JevTransientError(reason) from exc
        except httpx.HTTPError as exc:
            reason = f"connection error calling jev ({type(exc).__name__})"
            raise JevTransientError(reason) from exc
        return self._parse(response)

    def _parse(self, response: httpx.Response) -> RawResponse:
        """Map an HTTP response to RawResponse or the matching error."""
        status = response.status_code
        if status == 429 or status >= 500:
            reason = f"jev answered HTTP {status}"
            raise JevTransientError(reason, retry_after_seconds(response.headers))
        if status in _AUTH_STATUSES:
            reason = f"jev rejected the credentials (HTTP {status})"
            raise JevUnavailable(reason)
        if status >= 400:
            reason = f"jev refused the request (HTTP {status})"
            raise JevUnavailable(reason)
        try:
            body = response.json()
        except ValueError as exc:
            reason = "jev response is not valid JSON"
            raise JevInvalidResponse(reason) from exc
        return parse_body(body, response.headers.get(REQUEST_ID_HEADER))

    async def aclose(self) -> None:
        """Close the HTTP client if this transport created it."""
        if self._owns_client:
            await self._client.aclose()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:00 [python-coder]: Error bodies are never copied into messages (they can echo
#   classified state); only the status code is reported. (#KernelBootstrapV0/P3)
# ====================================================================
