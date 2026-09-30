"""
MODULE: kernel.observability.langfuse_tracer
GOAL: Tracer implementation that exports one trace per run to Langfuse (SDK 4.x, OpenTelemetry
    based) with correlation ids, redaction and a degraded mode that spools locally.
BUSINESS CONTEXT: Traces are the audit trail of a decision run and must continue across process
    restarts (Rev 3 section 12); but telemetry is never allowed to fail a run or erase state, so
    every SDK problem degrades to a local spool and is reported as observability degraded.
ARCHITECTURE: trace_id = Langfuse.create_trace_id(seed=run_id) is deterministic, so each process
    opens a segment root on the same trace (start_observation with trace_context). Observations
    are created from explicit parent handles (a ContextVar tracks the current span per asyncio
    task); propagate_attributes wraps each creation so session, trace name and tags reach every
    span. Langfuse(mask=Redactor) redacts all SDK attributes. Every SDK call goes through _guard:
    on any exception the tracer degrades, logs at WARNING and spools the observation instead.
"""

from __future__ import annotations

import contextvars
import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from langfuse import Langfuse, propagate_attributes
from opentelemetry.sdk.trace.export import SpanExporter

from kernel.config import DataPolicyConfig, LangfuseConfig
from kernel.contracts.base import CorrelationIds, TraceContext
from kernel.contracts.capability import Usage
from kernel.contracts.enums import ObservabilityStatus
from kernel.observability.correlation import deterministic_trace_id
from kernel.observability.observation_map import observation_type
from kernel.observability.redaction import Redactor
from kernel.observability.spool import TelemetrySpool
from kernel.observability.tracer import SpanHandle, TraceState
from kernel.secrets import SecretSettings

logger = logging.getLogger(__name__)

TRACE_TAG = "leafcutter-kernel"
_CURRENT: contextvars.ContextVar[_Handle | None] = contextvars.ContextVar(
    "langfuse_tracer_span", default=None)


class _Handle:
    """SpanHandle for one observation; keeps a local copy so it can be spooled on failure."""

    def __init__(self, tracer: LangfuseTracer, name: str, kind: str, corr: CorrelationIds,
                 obs: Any, data: dict[str, Any]) -> None:
        """Bind the handle to its tracer, optional SDK observation and local data."""
        self._tracer = tracer
        self.name = name
        self.kind = kind
        self.corr = corr
        self.obs = obs
        self.data = data

    @property
    def observation_id(self) -> str | None:
        """Return the SDK span id, if an observation exists."""
        return getattr(self.obs, "id", None)

    def update(self, *, output: Any = None, metadata: dict[str, Any] | None = None,
               level: str | None = None) -> None:
        """Attach output, metadata or a level to the open span."""
        if output is not None:
            self.data["output"] = output
        if metadata:
            self.data.setdefault("metadata", {}).update(metadata)
        if level is not None:
            self.data["level"] = level
        if self.obs is not None:
            self._tracer.guard("span update", self.obs.update, output=output,
                               metadata=metadata, level=level)

    def finish(self, error: BaseException | None) -> None:
        """End the span; an observation that could not be ended is spooled instead."""
        if error is not None:
            self.update(level="ERROR")
            self.data["error"] = f"{type(error).__name__}: {error}"
            if self.obs is not None:
                self._tracer.guard("span error", self.obs.update, status_message=str(error)[:500])
        ended = self.obs is not None and self._tracer.guard("span end", self.obs.end)
        if not ended:
            self._tracer.spool_record("span", self.name, {
                "kind": self.kind, "correlation": self.corr.as_metadata(), **self.data})


class LangfuseTracer:
    """Tracer exporting to Langfuse; degrades to a local spool on any telemetry failure."""

    def __init__(self, *, secrets: SecretSettings, config: LangfuseConfig,
                 policy: DataPolicyConfig, deny_globs: list[str], spool_path: Path,
                 span_exporter: SpanExporter | None = None, verify_auth: bool = True,
                 resolve_url: bool = True, release: str | None = None) -> None:
        """Create a tracer; nothing is sent until open_segment.

        Args:
            secrets: Loaded credentials (missing Langfuse keys degrade the tracer).
            config: langfuse config section.
            policy: data_policy section used by the redactor.
            deny_globs: Repo deny rules (retrieval.deny_globs) for the redactor.
            spool_path: Where degraded observations are written.
            span_exporter: Replacement OpenTelemetry exporter (tests use an in-memory one).
            verify_auth: Call auth_check() when a segment opens.
            resolve_url: Look up the trace URL (a network call) when a segment opens.
            release: Release string reported to Langfuse.
        """
        self._secrets = secrets
        self._config = config
        self._span_exporter = span_exporter
        self._verify_auth = verify_auth
        self._resolve_url = resolve_url
        self._release = release
        self.redactor = Redactor(secrets.secret_values(), policy, deny_globs)
        self.spool = TelemetrySpool(spool_path, self.redactor)
        self.client: Langfuse | None = None
        self.degraded_reason: str | None = None
        self._segment: _Handle | None = None
        self._trace_id: str | None = None
        self._run: tuple[str, str] | None = None

    # ---- state -------------------------------------------------------
    @property
    def degraded(self) -> bool:
        """True once any telemetry failure (or missing credentials) degraded the tracer."""
        return self.degraded_reason is not None

    def degrade(self, reason: str) -> None:
        """Mark the tracer degraded (first reason wins) and log it at WARNING."""
        if self.degraded_reason is None:
            self.degraded_reason = reason
            logger.warning("observability_degraded: %s", reason)

    def guard(self, label: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> bool:
        """Run an SDK call; on any exception degrade, log and return False."""
        try:
            fn(*args, **kwargs)
        except Exception as exc:
            self.degrade(f"{label} failed: {type(exc).__name__}")
            logger.exception("langfuse %s failed", label)
            return False
        return True

    def spool_record(self, kind: str, name: str, payload: dict[str, Any]) -> None:
        """Spool one observation with the degraded reason (nothing when tracing is disabled)."""
        if not self._config.enabled:
            return
        self.spool.write(kind, name, payload, reason=self.degraded_reason or "not_exported")

    # ---- segment -----------------------------------------------------
    def open_segment(self, run_id: str, root_task_id: str, kind: str) -> TraceState:
        """Open this process's segment root on the run's deterministic trace."""
        self._trace_id = deterministic_trace_id(run_id)
        self._run = (run_id, root_task_id)
        state = TraceState(trace_id=self._trace_id)
        corr = CorrelationIds(run_id=run_id, root_task_id=root_task_id)
        name = "leafcutter.run" if kind == "start" else f"leafcutter.run.{kind}"
        if not self._config.enabled:
            return state
        obs = self._create_segment_observation(name, corr, kind)
        self._segment = _Handle(self, name, "agent", corr, obs, {"segment": kind})
        if obs is None:
            self.spool_record("segment", name, {"correlation": corr.as_metadata(), "segment": kind})
            return state
        url = None
        if self.client is not None and self._resolve_url:
            try:
                url = self.client.get_trace_url(trace_id=self._trace_id)
            except Exception:
                logger.exception("langfuse trace url lookup failed")
        return state.model_copy(update={"root_observation_id": getattr(obs, "id", None),
                                        "trace_url": url})

    def _create_segment_observation(self, name: str, corr: CorrelationIds, kind: str) -> Any:
        """Build the client, check credentials and create the segment root (None if degraded)."""
        if not self._secrets.has_langfuse():
            self.degrade("missing_credentials")
            return None
        try:
            if self.client is None:
                self.client = self._build_client()
            if self._verify_auth and not self.client.auth_check():
                self.degrade("auth_check_failed")
                return None
            with self._propagate(corr):
                return self.client.start_observation(
                    trace_context={"trace_id": self._trace_id}, name=name, as_type="agent",
                    metadata={**corr.as_metadata(), "segment": kind})
        except Exception as exc:
            self.degrade(f"segment open failed: {type(exc).__name__}")
            logger.exception("langfuse segment open failed")
            return None

    def _build_client(self) -> Langfuse:
        """Construct the Langfuse client with the redactor as mask."""
        secrets = self._secrets
        return Langfuse(
            public_key=secrets.langfuse_public_key.get_secret_value(),
            secret_key=secrets.langfuse_secret_key.get_secret_value(),
            base_url=secrets.langfuse_base_url, environment=self._config.environment,
            release=self._release, mask=self.redactor, span_exporter=self._span_exporter)

    def _propagate(self, corr: CorrelationIds) -> Any:
        """Return the propagate_attributes context for session, trace name and tags."""
        run_id, root_task_id = self._run or (corr.run_id or "", corr.root_task_id or "")
        return propagate_attributes(
            session_id=run_id, trace_name=self._config.trace_name, tags=[TRACE_TAG],
            metadata={"run_id": run_id, "root_task_id": root_task_id})

    def trace_context(self, corr: CorrelationIds) -> TraceContext:
        """Return the TraceContext capabilities use to parent their own observations."""
        parent = self._parent()
        return TraceContext(trace_id=self._trace_id,
                            parent_observation_id=getattr(parent, "observation_id", None),
                            correlation=corr)

    def _parent(self) -> _Handle | None:
        """Return the innermost open span, else the segment root."""
        return _CURRENT.get() or self._segment

    # ---- observations ------------------------------------------------
    def _observe(self, name: str, kind: str, corr: CorrelationIds, input_value: Any,
                 metadata: dict[str, Any] | None) -> _Handle:
        """Create a child observation under the current parent (obs None when degraded)."""
        as_type = observation_type(name, kind)
        meta = {**corr.as_metadata(), **(metadata or {})}
        data: dict[str, Any] = {"input": input_value, "metadata": dict(meta)}
        parent = self._parent()
        obs = None
        if parent is not None and parent.obs is not None and not self.degraded:
            try:
                with self._propagate(corr):
                    obs = parent.obs.start_observation(name=name, as_type=as_type,
                                                       input=input_value, metadata=meta)
            except Exception as exc:
                self.degrade(f"span open failed: {type(exc).__name__}")
                logger.exception("langfuse span open failed")
        return _Handle(self, name, as_type, corr, obs, data)

    @contextmanager
    def span(self, name: str, kind: str, corr: CorrelationIds, *, input: Any = None,
             metadata: dict[str, Any] | None = None) -> Iterator[SpanHandle]:
        """Open a span as a context manager; observations inside are parented to it."""
        handle = self._observe(name, kind, corr, input, metadata)
        token = _CURRENT.set(handle)
        error: BaseException | None = None
        try:
            yield handle
        except BaseException as exc:
            error = exc
            raise
        finally:
            _CURRENT.reset(token)
            handle.finish(error)

    def generation(self, name: str, corr: CorrelationIds, *, model: str, input: Any,
                   output: Any, usage: Usage | None, metadata: dict[str, Any] | None = None
                   ) -> None:
        """Record one model call with its usage (unknown usage stays absent, never zero)."""
        meta = {**corr.as_metadata(), **(metadata or {})}
        details: dict[str, int] = {}
        costs: dict[str, float] = {}
        if usage is not None:
            details = {k: v for k, v in (("input", usage.input_tokens),
                                         ("output", usage.output_tokens)) if v is not None}
            if usage.cost_usd is not None:
                costs["total"] = usage.cost_usd
                meta["cost_provenance"] = usage.cost_provenance
        parent = self._parent()
        if parent is not None and parent.obs is not None and not self.degraded:
            try:
                with self._propagate(corr):
                    gen = parent.obs.start_observation(
                        name=name, as_type="generation", model=model, input=input, output=output,
                        usage_details=details or None, cost_details=costs or None, metadata=meta)
                gen.end()
            except Exception as exc:
                self.degrade(f"generation failed: {type(exc).__name__}")
                logger.exception("langfuse generation failed")
            else:
                return
        self.spool_record("generation", name, {
            "model": model, "input": input, "output": output, "usage": details,
            "cost": costs, "metadata": meta})

    def event(self, name: str, corr: CorrelationIds, *, level: str = "DEFAULT",
              payload: dict[str, Any] | None = None) -> None:
        """Record a point-in-time event under the current parent."""
        meta = {**corr.as_metadata(), **(payload or {})}
        parent = self._parent()
        if parent is not None and parent.obs is not None and not self.degraded:
            try:
                with self._propagate(corr):
                    parent.obs.create_event(name=name, metadata=meta, level=level)
            except Exception as exc:
                self.degrade(f"event failed: {type(exc).__name__}")
                logger.exception("langfuse event failed")
            else:
                return
        self.spool_record("event", name, {"level": level, "metadata": meta})

    def langchain_callbacks(self, corr: CorrelationIds) -> list:
        """Return a Langfuse LangChain handler bound to the trace and current parent span."""
        parent = self._parent()
        if self.degraded or self._trace_id is None or parent is None or parent.obs is None:
            return []
        try:
            from langfuse.langchain import CallbackHandler
            context = {"trace_id": self._trace_id, "parent_span_id": parent.observation_id}
            public = self._secrets.langfuse_public_key.get_secret_value()
            return [CallbackHandler(public_key=public, trace_context=context)]
        except Exception as exc:
            self.degrade(f"langchain callback failed: {type(exc).__name__}")
            logger.exception("langfuse callback handler failed")
            return []

    # ---- lifecycle ---------------------------------------------------
    def close_segment(self) -> ObservabilityStatus:
        """End the segment root, flush when configured, and report ok or degraded."""
        segment, self._segment = self._segment, None
        if segment is not None and segment.obs is not None:
            self.guard("segment end", segment.obs.end)
        if self.client is not None and self._config.flush_on_exit:
            self.guard("flush", self.client.flush)
        return ObservabilityStatus.DEGRADED if self.degraded else ObservabilityStatus.OK

    def shutdown(self) -> None:
        """Flush and stop the SDK background workers (call once in the CLI's finally)."""
        if self.client is not None:
            self.guard("shutdown", self.client.shutdown)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:00 [python-coder]: propagate_attributes wraps each observation creation (not the
#   whole segment) because parents are explicit handles and the OTel context is not carried
#   across concurrent Send tasks. (#KernelBootstrapV0/P2)
# - 2026-09-30 23:00 [python-coder]: close_segment flushes but shutdown() is separate: the SDK keeps
#   its client singleton per public key, so a shut-down client cannot be reopened in-process.
#   (#KernelBootstrapV0/P2)
# ====================================================================
