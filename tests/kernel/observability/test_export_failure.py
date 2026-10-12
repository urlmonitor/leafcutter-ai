"""
MODULE: tests.kernel.observability.test_export_failure
GOAL: A failed OpenTelemetry span export marks the segment `observability: degraded` with a
    reason and spools the undelivered spans, never breaks the run, and a successful export stays
    ok.
BUSINESS CONTEXT: A live resume printed "Read timed out" for the OTLP export while the envelope
    said `observability: ok`: opentelemetry-sdk 1.45's batch processor discards the exporter's
    result and `flush()` returns nothing, so the tracer never noticed (Kernel V0.1 fix C).
ARCHITECTURE: The real Langfuse client and span processor run over an injected exporter that
    fails the way the OTLP exporter does (returns FAILURE, or raises). The envelope plumbing is
    checked through build_envelope.
"""

from __future__ import annotations

import unittest
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from kernel.contracts.enums import ObservabilityStatus
from kernel.observability.export_monitor import ObservedSpanExporter
from kernel.persistence.base import RunRecord
from kernel.service_envelope import build_envelope
from tests.kernel.observability.test_langfuse_tracer import RUN, TASK, _Harness


class _ReadTimedOut(OSError):
    """The error a timed-out OTLP request ends in."""


class _Failing(SpanExporter):
    """Exporter that fails like a timed-out OTLP request (FAILURE) or by raising."""

    def __init__(self, raises: bool = False) -> None:
        self.raises = raises
        self.attempts = 0

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        self.attempts += 1
        if self.raises:
            raise _ReadTimedOut
        return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        """Nothing to release."""


def _run_segment(tracer: Any, corr: Any) -> ObservabilityStatus:
    """Record a span, a generation and an event, then close the segment (flushes)."""
    tracer.open_segment(RUN, TASK, "start")
    with tracer.span("kernel.route", "chain", corr, input={"q": 1}):
        tracer.event("routing.assessed", corr, payload={"p": 0.9})
    tracer.generation("jev.route", corr, model="m", input="i", output="o", usage=None)
    return tracer.close_segment()


class TestExportFailure(_Harness):
    """A failed export is visible in the status, the reason and the spool."""

    def test_a_failed_export_result_degrades_the_segment_and_spools_the_spans(self) -> None:
        self.exporter = _Failing()  # type: ignore[assignment]
        tracer = self.make()
        status = _run_segment(tracer, self.corr)
        self.assertEqual(status, ObservabilityStatus.DEGRADED)
        self.assertIn("export failed", tracer.degraded_reason or "")
        self.assertIn("FAILURE", tracer.degraded_reason or "")
        spooled = {r["name"] for r in tracer.spool.read()}
        self.assertGreaterEqual(spooled, {"kernel.route", "jev.route", "leafcutter.run"})
        record = next(r for r in tracer.spool.read() if r["name"] == "kernel.route")
        self.assertEqual(record["kind"], "span")
        self.assertIn("export failed", record["reason"])
        self.assertEqual(len(record["data"]["trace_id"]), 32)

    def test_an_exception_from_the_exporter_degrades_and_never_reaches_the_run(self) -> None:
        self.exporter = _Failing(raises=True)  # type: ignore[assignment]
        tracer = self.make()
        status = _run_segment(tracer, self.corr)  # must not raise
        self.assertEqual(status, ObservabilityStatus.DEGRADED)
        self.assertIn("_ReadTimedOut", tracer.degraded_reason or "")
        self.assertTrue(tracer.spool.read())

    def test_a_successful_export_stays_ok_and_spools_nothing(self) -> None:
        tracer = self.make()
        self.assertIsInstance(self.exporter, InMemorySpanExporter)
        status = _run_segment(tracer, self.corr)
        self.assertEqual(status, ObservabilityStatus.OK)
        self.assertIsNone(tracer.degraded_reason)
        self.assertEqual(tracer.spool.read(), [])
        self.assertIn("kernel.route", {s.name for s in self.exporter.get_finished_spans()})

    def test_the_spool_masks_secrets_of_the_lost_spans(self) -> None:
        self.exporter = _Failing()  # type: ignore[assignment]
        tracer = self.make()
        tracer.open_segment(RUN, TASK, "start")
        tracer.generation("jev.route", self.corr, model="m", input=f"key {self.secret}",
                          output="o", usage=None)
        tracer.close_segment()
        self.assertNotIn(self.secret, Path(tracer.spool.path).read_text(encoding="utf-8"))


class TestObservedExporter(unittest.TestCase):
    """The wrapper reports failures and passes results through unchanged."""

    def test_it_reports_only_failures_and_returns_the_delegate_result(self) -> None:
        reports: list[tuple[str, int]] = []
        good = ObservedSpanExporter(InMemorySpanExporter(), lambda r, s: reports.append((r, len(s))))
        self.assertIs(good.export([]), SpanExportResult.SUCCESS)
        self.assertEqual(reports, [])
        bad = ObservedSpanExporter(_Failing(), lambda r, s: reports.append((r, len(s))))
        self.assertIs(bad.export([]), SpanExportResult.FAILURE)
        self.assertEqual(len(reports), 1)
        self.assertIn("FAILURE", reports[0][0])

    def test_a_raising_exporter_is_reported_and_re_raised(self) -> None:
        reports: list[str] = []
        wrapped = ObservedSpanExporter(_Failing(raises=True), lambda r, _s: reports.append(r))
        with self.assertRaises(OSError):
            wrapped.export([])
        self.assertIn("_ReadTimedOut", reports[0])

    def test_a_failing_callback_never_propagates(self) -> None:
        def broken(_reason: str, _spans: Sequence[ReadableSpan]) -> None:
            raise _ReadTimedOut

        self.assertIs(ObservedSpanExporter(_Failing(), broken).export([]),
                      SpanExportResult.FAILURE)


class TestEnvelopeStatus(unittest.TestCase):
    """The envelope says why observability is degraded."""

    @staticmethod
    def _envelope(status: ObservabilityStatus, reason: str | None) -> Any:
        record = RunRecord(run_id="run-1", root_task_id="task-1")
        return build_envelope(record, {}, trace=None, observability=status,
                              observability_reason=reason)

    def test_degraded_adds_a_limitation_with_the_reason(self) -> None:
        envelope = self._envelope(ObservabilityStatus.DEGRADED, "export failed: timed out")
        self.assertEqual(envelope.trace_refs.observability, ObservabilityStatus.DEGRADED)
        self.assertTrue(any("observability_degraded: export failed: timed out" in line
                            for line in envelope.limitations))

    def test_ok_adds_no_limitation(self) -> None:
        envelope = self._envelope(ObservabilityStatus.OK, None)
        self.assertFalse(any("observability" in line for line in envelope.limitations))


if __name__ == "__main__":
    unittest.main()
