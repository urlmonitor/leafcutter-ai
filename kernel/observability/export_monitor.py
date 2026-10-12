"""
MODULE: kernel.observability.export_monitor
GOAL: Detect failed OpenTelemetry span exports, which the SDK otherwise swallows, and build the
    default Langfuse OTLP exporter the monitor wraps.
BUSINESS CONTEXT: A resume once printed a failed OTLP export ("Read timed out") while the
    envelope said `observability: ok`. Telemetry may never fail a run, but the envelope must say
    when it was not delivered, and the undelivered spans must survive in the local spool
    (Kernel V0.1 fix C).
ARCHITECTURE: opentelemetry-sdk 1.45's BatchProcessor discards the SpanExportResult its exporter
    returns, only logs an exception the exporter raises, and `force_flush` returns True either
    way; Langfuse's `flush()` returns nothing. The one place that sees the outcome is the
    exporter itself, so ObservedSpanExporter wraps the delegate (handed to Langfuse's documented
    `span_exporter` argument) and reports a FAILURE result or a raised exception to a callback.
    The callback runs on the SDK's export thread (or the flushing thread) and must not raise.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Sequence
from importlib import metadata

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

logger = logging.getLogger(__name__)

FailureCallback = Callable[[str, Sequence[ReadableSpan]], None]
OTLP_TRACES_PATH = "api/public/otel/v1/traces"
DEFAULT_BASE_URL = "https://cloud.langfuse.com"  # the Langfuse SDK default host
DEFAULT_TIMEOUT_SECONDS = 5


class ObservedSpanExporter(SpanExporter):
    """SpanExporter that reports failed exports of its delegate and otherwise changes nothing."""

    def __init__(self, delegate: SpanExporter, on_failure: FailureCallback) -> None:
        """Wrap `delegate`; `on_failure(reason, spans)` is called for every failed batch."""
        self._delegate = delegate
        self._on_failure = on_failure

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        """Export through the delegate; report a FAILURE result or an exception, then pass it on."""
        name = type(self._delegate).__name__
        try:
            result = self._delegate.export(spans)
        except Exception as exc:
            self._report(f"{name}.export raised {type(exc).__name__}", spans)
            raise
        if result is not SpanExportResult.SUCCESS:
            self._report(f"{name}.export returned {result.name} for {len(spans)} span(s)", spans)
        return result

    def _report(self, reason: str, spans: Sequence[ReadableSpan]) -> None:
        """Call the callback; a failing callback is logged, never raised into the SDK thread."""
        try:
            self._on_failure(reason, spans)
        except (OSError, TypeError, ValueError):
            logger.warning("telemetry failure callback failed", exc_info=True)

    def shutdown(self) -> None:
        """Shut the delegate down."""
        self._delegate.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Flush the delegate (the OTLP exporter buffers nothing)."""
        return self._delegate.force_flush(timeout_millis)


def default_langfuse_exporter(*, base_url: str, public_key: str, secret_key: str,
                              timeout_seconds: int | None = None) -> SpanExporter:
    """Build the exporter Langfuse would create itself (same endpoint, headers and timeout).

    Args:
        base_url: Langfuse host, for example https://cloud.langfuse.com.
        public_key: Langfuse public key.
        secret_key: Langfuse secret key (used only for the basic-auth header).
        timeout_seconds: Per-request timeout; None reads LANGFUSE_TIMEOUT, else 5 seconds.

    Returns:
        SpanExporter: An OTLP/HTTP exporter pointed at the Langfuse OTLP endpoint.
    """
    import base64  # noqa: PLC0415

    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # noqa: PLC0415
        OTLPSpanExporter,
    )

    token = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode("ascii")
    headers = {"Authorization": f"Basic {token}", "x-langfuse-sdk-name": "python",
               "x-langfuse-sdk-version": metadata.version("langfuse"),
               "x-langfuse-public-key": public_key}
    timeout = timeout_seconds or int(os.environ.get("LANGFUSE_TIMEOUT", DEFAULT_TIMEOUT_SECONDS))
    return OTLPSpanExporter(endpoint=f"{base_url.rstrip('/')}/{OTLP_TRACES_PATH}",
                            headers=headers, timeout=timeout)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Failures are detected in a wrapping exporter, not by parsing the
#   SDK's log output or patching private processor fields: it is the only hook that receives the
#   exporter's SpanExportResult in this SDK version. (#KernelV01/C)
# - 2026-10-01 [python-coder]: The default exporter is rebuilt here (endpoint, headers, timeout
#   as Langfuse 4.16 builds them) because a custom `span_exporter` replaces Langfuse's own.
#   (#KernelV01/C)
# ====================================================================
