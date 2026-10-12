"""
MODULE: tests.kernel.observability.test_recording_tracer
GOAL: Test RecordingTracer and NoOpTracer: recorded names, correlation ids, nesting (including
    concurrent tasks), events, generations, segment lifecycle and deterministic trace ids.
BUSINESS CONTEXT: Later phases assert observability behaviour through these doubles, so the
    doubles themselves must record exactly what a real tracer would receive.
ARCHITECTURE: asyncio.run drives the concurrency test; no network, no SDK.
"""

from __future__ import annotations

import asyncio
import unittest

from kernel.contracts.base import CorrelationIds
from kernel.contracts.capability import Usage
from kernel.contracts.enums import ObservabilityStatus
from kernel.observability import (
    NoOpTracer,
    RecordingTracer,
    Tracer,
    deterministic_trace_id,
    run_correlation,
)


class TestRecording(unittest.TestCase):
    """RecordingTracer behaviour."""

    def setUp(self) -> None:
        self.tracer = RecordingTracer()
        self.corr = CorrelationIds(run_id="run-0000000000000001", work_item_id="work-1")

    def test_both_implementations_satisfy_the_port(self) -> None:
        self.assertIsInstance(self.tracer, Tracer)
        self.assertIsInstance(NoOpTracer(), Tracer)

    def test_span_records_name_kind_input_and_correlation(self) -> None:
        with self.tracer.span("kernel.route", "chain", self.corr, input={"n": 1}) as span:
            span.update(output={"ok": True}, metadata={"k": "v"}, level="WARNING")
        call = self.tracer.named("kernel.route", "span")[0]
        self.assertEqual(call.corr.work_item_id, "work-1")
        self.assertEqual((call.data["span_kind"], call.data["input"]), ("chain", {"n": 1}))
        self.assertEqual(call.data["output"], {"ok": True})
        self.assertEqual(call.data["metadata"], {"k": "v"})
        self.assertEqual(call.data["level"], "WARNING")
        self.assertTrue(call.closed)

    def test_nesting_parents_children_and_restores_after_exit(self) -> None:
        with self.tracer.span("outer", "chain", self.corr):
            with self.tracer.span("inner", "tool", self.corr):
                self.tracer.event("inside", self.corr)
            self.tracer.event("after_inner", self.corr)
        self.tracer.event("after_outer", self.corr)
        outer, inner = self.tracer.named("outer")[0], self.tracer.named("inner")[0]
        self.assertIsNone(outer.parent)
        self.assertEqual(inner.parent, outer.index)
        self.assertEqual(self.tracer.named("inside")[0].parent, inner.index)
        self.assertEqual(self.tracer.named("after_inner")[0].parent, outer.index)
        self.assertIsNone(self.tracer.named("after_outer")[0].parent)
        self.assertEqual([c.name for c in self.tracer.children_of(outer)],
                         ["inner", "after_inner"])

    def test_span_closes_and_context_resets_when_body_raises(self) -> None:
        with self.assertRaises(RuntimeError), self.tracer.span("boom", "chain", self.corr):
            raise RuntimeError
        self.assertTrue(self.tracer.named("boom")[0].closed)
        self.tracer.event("later", self.corr)
        self.assertIsNone(self.tracer.named("later")[0].parent)

    def test_concurrent_tasks_do_not_cross_parent(self) -> None:
        async def worker(name: str) -> None:
            with self.tracer.span(name, "agent", self.corr):
                await asyncio.sleep(0)
                self.tracer.event(f"{name}.event", self.corr)

        async def main() -> None:
            await asyncio.gather(worker("a"), worker("b"))

        asyncio.run(main())
        for name in ("a", "b"):
            span = self.tracer.named(name)[0]
            self.assertEqual(self.tracer.named(f"{name}.event")[0].parent, span.index)

    def test_generation_records_model_usage_and_payloads(self) -> None:
        usage = Usage(provider="jev", model_id="jev-1", input_tokens=10, calls=1)
        self.tracer.generation("jev.route", self.corr, model="jev-1", input={"q": 1},
                               output={"a": 2}, usage=usage, metadata={"template_id": "t1"})
        call = self.tracer.named("jev.route", "generation")[0]
        self.assertEqual((call.data["model"], call.data["usage"]), ("jev-1", usage))
        self.assertIsNone(call.data["usage"].cost_usd)
        self.assertEqual(call.data["metadata"], {"template_id": "t1"})

    def test_event_level_and_payload(self) -> None:
        self.tracer.event("guard.tripped", self.corr, level="WARNING", payload={"guard": "depth"})
        call = self.tracer.named("guard.tripped", "event")[0]
        self.assertEqual((call.data["level"], call.data["payload"]),
                         ("WARNING", {"guard": "depth"}))

    def test_segment_lifecycle_and_status(self) -> None:
        state = self.tracer.open_segment("run-0000000000000001", "task-1", "resume")
        self.assertEqual(state.trace_id, deterministic_trace_id("run-0000000000000001"))
        self.assertEqual(self.tracer.segments, [("run-0000000000000001", "task-1", "resume")])
        self.assertEqual(self.tracer.named("leafcutter.run.resume", "segment")[0].corr.run_id,
                         "run-0000000000000001")
        self.assertEqual(self.tracer.close_segment(), ObservabilityStatus.OK)
        self.assertEqual(self.tracer.closed_segments, 1)
        degraded = RecordingTracer(ObservabilityStatus.DEGRADED)
        self.assertEqual(degraded.close_segment(), ObservabilityStatus.DEGRADED)


class TestIdentityAndNoOp(unittest.TestCase):
    """Trace identity helpers and the no-op tracer."""

    def test_trace_id_is_32_hex_and_stable_per_run(self) -> None:
        first = deterministic_trace_id("run-a")
        self.assertRegex(first, r"^[0-9a-f]{32}$")
        self.assertEqual(first, deterministic_trace_id("run-a"))
        self.assertNotEqual(first, deterministic_trace_id("run-b"))

    def test_correlation_metadata_omits_nulls(self) -> None:
        corr = run_correlation("run-1", "task-1").with_updates(work_item_id="work-9")
        self.assertEqual(corr.as_metadata(),
                         {"run_id": "run-1", "root_task_id": "task-1", "work_item_id": "work-9"})

    def test_noop_tracer_does_nothing_but_keeps_identity(self) -> None:
        tracer = NoOpTracer()
        corr = CorrelationIds()
        with tracer.span("x", "chain", corr) as span:
            span.update(output=1)
        tracer.event("e", corr)
        tracer.generation("g", corr, model="m", input=None, output=None, usage=None)
        self.assertEqual(tracer.langchain_callbacks(corr), [])
        self.assertEqual(tracer.open_segment("run-a", "t", "start").trace_id,
                         deterministic_trace_id("run-a"))
        self.assertEqual(tracer.close_segment(), ObservabilityStatus.OK)


if __name__ == "__main__":
    unittest.main()

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:00 [python-coder]: The concurrency test guards the ContextVar-based nesting
#   choice (Send workers run as concurrent tasks). (#KernelBootstrapV0/P1)
# ====================================================================
