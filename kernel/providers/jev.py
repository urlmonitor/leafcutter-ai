"""
MODULE: kernel.providers.jev
GOAL: The live JevPort: TypeSafeJevAdapter with bounded retries, per-call timeout, payload size
    guard, batching of same-state questions, usage recording and strict error mapping, over a
    selectable transport (langchain-typesafe classifier or direct HTTP).
BUSINESS CONTEXT: Routing, decisions and research ask Jev literal questions through JevPort. A
    provider outage must surface as JevUnavailable (never a capability gap or an invented
    answer), and every answer must carry its raw distribution, model id and usage so thresholds
    are auditable (Rev 3 sections 9 and 13.4).
ARCHITECTURE: This is the only module that imports langchain_typesafe, and only lazily inside
    ClassifierTransport so the HTTP fallback works even if the beta package breaks. The adapter
    owns retry policy (the package has none): JevTransientError from a transport is retried with
    backoff, then converted to JevUnavailable. Questions of one batch share one state and are
    sent in chunks of at most max_questions_per_call. Pure mapping lives in jev_wire.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, Literal, Protocol

from pydantic import TypeAdapter

from kernel.contracts.base import canonical_json
from kernel.contracts.capability import Usage
from kernel.observability.tracer import Tracer
from kernel.providers.base import (
    JevBatch,
    JevError,
    JevInvalidResponse,
    JevResult,
    QuestionSpec,
)
from kernel.providers.jev_errors import (
    JevInvalidRequest,
    JevPayloadTooLarge,
    JevTransientError,
    JevUnavailable,
)
from kernel.providers.jev_http import HttpTransport
from kernel.providers.jev_trace import emit_generation
from kernel.providers.jev_wire import RawResponse, map_answers, parse_body, question_to_wire

if TYPE_CHECKING:
    from kernel.config import KernelConfig

logger = logging.getLogger(__name__)

MAX_BACKOFF_SECONDS = 30.0
TransportName = Literal["classifier", "http"]


class JevTransport(Protocol):
    """One request/response exchange with the provider."""

    name: str
    version: str

    async def send(self, state: dict[str, Any], questions: dict[str, dict[str, Any]],
                   *, purpose: str = "") -> RawResponse:
        """Send one request; raise JevTransientError, JevUnavailable or JevInvalidResponse."""

    async def aclose(self) -> None:
        """Release owned resources."""


class ClassifierTransport:
    """Transport over langchain-typesafe's TypeSafeClassifier (imported lazily)."""

    name = "typesafe-classifier"

    def __init__(self, *, api_key: str, model: str, timeout_seconds: float,
                 base_url: str | None = None, async_client: Any = None,
                 detach_callbacks: bool = False) -> None:
        """Create the classifier, passing the key explicitly (the class defaults to another env var).

        Args:
            api_key: Jev API key.
            model: Model name, for example jev-latest.
            timeout_seconds: Timeout for the clients the classifier creates.
            base_url: Optional API root override.
            async_client: Optional injected httpx2.AsyncClient (tests).
            detach_callbacks: Run the classifier with an empty callback list so graph-level
                LangChain handlers do not add a usage-less CHAIN observation; the adapter then
                emits the GENERATION itself.
        """
        import langchain_typesafe as lts  # noqa: PLC0415 - lazy: only vendor import site

        self._lts = lts
        self.version = lts.__version__
        kwargs: dict[str, Any] = {"api_key": api_key, "model": model, "timeout": timeout_seconds}
        if base_url:
            kwargs["base_url"] = base_url
        if async_client is not None:
            kwargs["async_client"] = async_client
        self._detach_callbacks = detach_callbacks
        self._owns_clients = async_client is None
        self._classifier = lts.TypeSafeClassifier(**kwargs)

    async def send(self, state: dict[str, Any], questions: dict[str, dict[str, Any]],
                   *, purpose: str = "") -> RawResponse:
        """Invoke the classifier and normalise its response or translate its errors."""
        from langchain_typesafe import client as lts_client  # noqa: PLC0415

        adapter: TypeAdapter[Any] = TypeAdapter(self._lts.Question)
        request = {"state": state,
                   "questions": {k: adapter.validate_python(v) for k, v in questions.items()}}
        try:
            config: dict[str, Any] = {"run_name": f"jev.{purpose}" if purpose else "jev"}
            if self._detach_callbacks:
                config["callbacks"] = []
            # langchain_typesafe types the request as a TypedDict built at runtime
            response = await self._classifier.ainvoke(
                request, config=config)  # type: ignore[arg-type]
        except lts_client.TypeSafeAPIResponseValidationError as exc:
            reason = f"jev response failed validation at {exc.field_path}"
            raise JevInvalidResponse(reason) from exc
        except lts_client.TypeSafeAPIError as exc:
            raise _translate_api_error(exc) from exc
        except lts_client.TypeSafeAPIConnectionError as exc:
            reason = f"connection problem calling jev ({type(exc).__name__})"
            raise JevTransientError(reason) from exc
        return parse_body(response.model_dump(mode="json"), response.request_id)

    async def aclose(self) -> None:
        """Close the clients the classifier created."""
        if self._owns_clients:
            if self._classifier.async_client is not None:
                await self._classifier.async_client.aclose()
            if self._classifier.client is not None:
                self._classifier.client.close()


def _translate_api_error(exc: Any) -> Exception:
    """Map a TypeSafeAPIError to a transient error or JevUnavailable (status only, no body)."""
    status = getattr(exc, "status", 0)
    if status == 429 or status >= 500:
        delay_ms = getattr(exc, "retry_after_ms", None)
        delay = delay_ms / 1000.0 if delay_ms is not None else None
        return JevTransientError(f"jev answered HTTP {status}", delay)
    if status in (401, 403):
        return JevUnavailable(f"jev rejected the credentials (HTTP {status})")
    return JevUnavailable(f"jev refused the request (HTTP {status})")


def _sum_known(values: list[int | None]) -> int | None:
    """Sum counts; any unknown makes the total unknown (None), never a silent partial."""
    if any(v is None for v in values):
        return None
    return sum(v for v in values if v is not None)


class TypeSafeJevAdapter:
    """JevPort implementation over a JevTransport."""

    def __init__(self, transport: JevTransport, *, timeout_seconds: float,
                 max_questions_per_call: int, max_state_chars: int, max_retries: int,
                 retry_backoff_seconds: float, price_per_input_token_usd: float | None = None,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
                 tracer: Tracer | None = None, model_name: str | None = None) -> None:
        """Create the adapter.

        Args:
            transport: Provider transport.
            timeout_seconds: Hard deadline per provider call (each attempt).
            max_questions_per_call: Questions per provider call; larger batches are chunked.
            max_state_chars: Serialised state limit; above it JevPayloadTooLarge is raised.
            max_retries: Retries after the first attempt, transient errors only.
            retry_backoff_seconds: Base delay, doubled per retry (capped), unless the server
                asks for a specific delay.
            price_per_input_token_usd: Used to estimate cost; None leaves cost unknown.
            sleep: Awaitable sleep (injected in tests).
            tracer: When set, every assess call emits one `jev.<purpose>` GENERATION through it
                (parented to the current span of the caller, correlated by `batch.correlation`).
            model_name: Configured model, reported when the provider does not name one.
        """
        self._transport = transport
        self._timeout = timeout_seconds
        self._chunk = max_questions_per_call
        self._max_state_chars = max_state_chars
        self._max_retries = max_retries
        self._backoff = retry_backoff_seconds
        self._price = price_per_input_token_usd
        self._sleep = sleep
        self._tracer = tracer
        self._model_name = model_name

    @classmethod
    def from_config(cls, cfg: KernelConfig, api_key: str, *,
                    transport: TransportName | None = None, base_url: str | None = None,
                    client: Any = None, tracer: Tracer | None = None) -> TypeSafeJevAdapter:
        """Build an adapter from the kernel config.

        Args:
            cfg: Validated kernel config (jev section and limits.max_retries are used).
            api_key: Jev API key value (from kernel.secrets).
            transport: "classifier" (langchain-typesafe) or "http" (direct fallback); None
                reads `jev.transport` from the config.
            base_url: Optional API root override.
            client: Optional injected async HTTP client matching the transport (tests).
            tracer: Optional Tracer. When given the adapter emits one GENERATION per call and
                the classifier transport detaches inherited LangChain callbacks, so Langfuse
                shows one observation per call instead of a duplicate usage-less CHAIN.

        Returns:
            TypeSafeJevAdapter: Ready adapter.
        """
        jev = cfg.jev
        if (transport or jev.transport) == "http":
            tr: JevTransport = HttpTransport(
                api_key=api_key, model=jev.model, timeout_seconds=jev.timeout_seconds,
                **({"base_url": base_url} if base_url else {}), client=client)
        else:
            tr = ClassifierTransport(
                api_key=api_key, model=jev.model, timeout_seconds=jev.timeout_seconds,
                base_url=base_url, async_client=client,
                detach_callbacks=tracer is not None)
        return cls(tr, timeout_seconds=jev.timeout_seconds,
                   max_questions_per_call=jev.max_questions_per_call,
                   max_state_chars=jev.max_state_chars, max_retries=cfg.limits.max_retries,
                   retry_backoff_seconds=jev.retry_backoff_seconds,
                   price_per_input_token_usd=jev.price_per_input_token_usd, tracer=tracer,
                   model_name=jev.model)

    @property
    def adapter_version(self) -> str:
        """Identify the transport and its version (for trace records)."""
        return f"{self._transport.name}/{self._transport.version}"

    async def aclose(self) -> None:
        """Release transport resources."""
        await self._transport.aclose()

    async def assess(self, batch: JevBatch) -> JevResult:
        """Answer every question of the batch (see JevPort.assess for the error contract)."""
        started = time.perf_counter()
        try:
            result = await self._assess(batch)
        except JevError as exc:
            self._trace(batch, started, error=exc)
            raise
        self._trace(batch, started, result=result)
        return result

    def _trace(self, batch: JevBatch, started: float, *, result: JevResult | None = None,
               error: JevError | None = None) -> None:
        """Emit the GENERATION for this call when a tracer is configured."""
        if self._tracer is None:
            return
        emit_generation(
            self._tracer, batch, adapter_version=self.adapter_version,
            model_name=self._model_name, state_chars=len(canonical_json(batch.state)),
            latency_ms=int((time.perf_counter() - started) * 1000), result=result, error=error)

    async def _assess(self, batch: JevBatch) -> JevResult:
        """Validate, send (chunked, with retry) and map the answers."""
        ids = [q.id for q in batch.questions]
        if len(set(ids)) != len(ids):
            reason = "duplicate question ids in batch"
            raise JevInvalidRequest(reason)
        size = len(canonical_json(batch.state))
        if size > self._max_state_chars:
            raise JevPayloadTooLarge(size, self._max_state_chars)
        wires = {q.id: question_to_wire(q) for q in batch.questions}
        started = time.perf_counter()
        raws: list[RawResponse] = []
        attempts = 0
        for start in range(0, len(ids), self._chunk):
            chunk = batch.questions[start:start + self._chunk]
            raw, used = await self._send_with_retry(batch, chunk, wires)
            raws.append(raw)
            attempts += used
        latency_ms = int((time.perf_counter() - started) * 1000)
        answers: dict[str, Any] = {}
        for raw, start in zip(raws, range(0, len(ids), self._chunk), strict=True):
            answers.update(map_answers(raw.answers, batch.questions[start:start + self._chunk]))
        return self._result(batch, raws, answers, attempts, latency_ms)

    async def _send_with_retry(self, batch: JevBatch, chunk: list[QuestionSpec],
                               wires: dict[str, dict[str, Any]]) -> tuple[RawResponse, int]:
        """Send one chunk, retrying transient failures; return (response, attempts used)."""
        payload = {q.id: wires[q.id] for q in chunk}
        last: JevTransientError | None = None
        for attempt in range(self._max_retries + 1):
            try:
                async with asyncio.timeout(self._timeout):
                    raw = await self._transport.send(batch.state, payload, purpose=batch.purpose)
            except TimeoutError as exc:
                last = JevTransientError(f"jev call exceeded {self._timeout}s")
                last.__cause__ = exc
            except JevTransientError as exc:
                last = exc
            else:
                return raw, attempt + 1
            if attempt < self._max_retries:
                delay = last.retry_after_seconds
                if delay is None:
                    delay = self._backoff * (2 ** attempt)
                logger.warning("jev transient failure (%s), retry %d/%d", last.reason,
                               attempt + 1, self._max_retries)
                await self._sleep(min(delay, MAX_BACKOFF_SECONDS))
        reason = f"jev unavailable after {self._max_retries + 1} attempts: {last.reason if last else "no attempt"}"
        raise JevUnavailable(reason) from last

    def _result(self, batch: JevBatch, raws: list[RawResponse], answers: dict[str, Any],
                attempts: int, latency_ms: int) -> JevResult:
        """Assemble the JevResult with usage; unknown values stay None."""
        model = next((r.model for r in raws if r.model), None)
        tokens_in = _sum_known([r.input_tokens for r in raws])
        cost = tokens_in * self._price if tokens_in is not None and self._price is not None \
            else None
        usage = Usage(
            provider="jev", model_id=model, input_tokens=tokens_in,
            output_tokens=_sum_known([r.output_tokens for r in raws]), duration_ms=latency_ms,
            cost_usd=cost, cost_provenance="estimated" if cost is not None else "unavailable",
            calls=attempts)
        ids = [r.request_id for r in raws if r.request_id]
        logger.info("jev purpose=%s model=%s adapter=%s questions=%d calls=%d latency_ms=%d",
                    batch.purpose, model, self.adapter_version, len(answers), attempts,
                    latency_ms)
        return JevResult(model_id=model, request_id=",".join(ids) or None, answers=answers,
                         usage=usage, latency_ms=latency_ms,
                         input_fingerprint=batch.input_fingerprint(),
                         adapter_version=self.adapter_version)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-02 [python-coder]: mypy: optional clients are guarded and the retry reason is None-safe (#KernelBootstrapV0/GROUND)
# - 2026-10-01 00:30 [python-coder]: With a tracer the adapter emits the GENERATION and the
#   classifier runs with callbacks=[] (an explicit empty list overrides the inherited graph-level
#   handler), so the usage-less LangChain CHAIN is not duplicated. Without a tracer behaviour is
#   unchanged. (#KernelBootstrapV0/OBS)
# - 2026-09-30 23:59 [python-coder]: Transport defaults from `jev.transport`; results carry
#   adapter_version. (#KernelBootstrapV0/INT)
# - 2026-09-30 23:00 [python-coder]: Retry lives in the adapter because langchain-typesafe has
#   none; unknown token counts make totals and cost None rather than partial sums.
#   (#KernelBootstrapV0/P3)
# - 2026-09-30 23:00 [python-coder]: Transport is selected by a constructor argument because
#   P1's JevConfig has no transport key (orchestrator may add jev.transport). (#KernelBootstrapV0/P3)
# ====================================================================
