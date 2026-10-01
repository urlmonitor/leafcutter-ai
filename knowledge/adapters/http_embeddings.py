"""Optional SDK-free embedding gateway: POST {model,texts}, return {model,vectors}."""

from __future__ import annotations

import asyncio
import json
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import URLError
from knowledge.deadlines import remaining_seconds
from knowledge.errors import BackendUnavailable, invalid
from knowledge.semantic import validate_vector


class _NoRedirect(HTTPRedirectHandler):
    """Reject redirects so gateway credentials cannot cross endpoint boundaries."""

    def redirect_request(self, *args: object, **kwargs: object) -> None:
        """Refuse gateway redirects to keep credentials bound to the configured endpoint.

        Args:
            args: Positional redirect details supplied by urllib.
            kwargs: Keyword redirect details supplied by urllib.
        """
        return None


class HttpEmbeddingProvider:
    """A user-configured gateway adapter; no endpoint discovery or mandatory paid API."""

    provider_id = "leafcutter-http-gateway-v1"

    def __init__(
        self,
        endpoint: str,
        model: str,
        dimensions: int,
        token: str | None = None,
        timeout: float = 5.0,
    ) -> None:
        """Initialize the adapter with explicit configuration and bounded resources.

        Args:
            endpoint: Explicit embedding gateway URL using verified TLS remotely.
            model: Embedding model identifier bound to this generation.
            dimensions: Expected number of finite values in every embedding.
            token: Optional gateway bearer credential; never logged.
            timeout: Upper bound in seconds, further limited by the request deadline.
        """
        parts = urlsplit(endpoint)
        if parts.username or parts.password or parts.query or parts.fragment:
            invalid("embedding endpoint must not contain credentials, query or fragment")
        if parts.scheme != "https" and not (
            parts.scheme == "http" and parts.hostname in {"localhost", "127.0.0.1", "::1"}
        ):
            invalid("remote embedding endpoint requires verified HTTPS")
        if not model or not 1 <= dimensions <= 4096:
            invalid("embedding model and dimensions required")
        self.endpoint = endpoint
        self.model = model
        self.dimensions = dimensions
        self.token = token
        self.timeout = timeout

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed bounded texts and preserve their input order.

        Args:
            texts: Bounded source texts to embed in their original order.

        Returns:
            Validated vectors corresponding one-to-one to the input texts.
        """
        if len(texts) > 32 or any(len(text.encode()) > 32768 for text in texts):
            invalid("embedding request exceeds bounded batch/text limits")
        return await asyncio.to_thread(self._request, texts)

    def _request(self, texts: list[str]) -> list[list[float]]:
        """Call the configured gateway and validate its model-bound response.

        Args:
            texts: Bounded source texts to embed in their original order.

        Returns:
            Validated model-bound vectors returned by the configured gateway.
        """
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        request = Request(
            self.endpoint,
            data=json.dumps({"model": self.model, "texts": texts}).encode(),
            headers=headers,
            method="POST",
        )
        try:
            with build_opener(_NoRedirect()).open(
                request, timeout=remaining_seconds(self.timeout)
            ) as response:
                raw = response.read(1048577)
            if len(raw) > 1048576:
                invalid("embedding response exceeds limit")
            data = json.loads(raw)
        except (URLError, OSError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BackendUnavailable() from exc
        if not isinstance(data, dict) or not isinstance(data.get("vectors"), list):
            invalid("embedding gateway returned invalid envelope")
        if data.get("model") != self.model or len(data.get("vectors", [])) != len(texts):
            invalid("embedding gateway model or batch does not match request")
        return [validate_vector(vector, self.dimensions) for vector in data["vectors"]]
