"""
MODULE: tests.kernel.scheduler.test_trace_events
GOAL: Verify the finalize and record_gaps nodes emit the design-mapped tracer events
    `run.finalized` and `gap.recorded` with correlation ids and no payload text.
BUSINESS CONTEXT: Langfuse traces are the audit trail (design part 5): a run must show how it
    ended, and capability gaps must stay countable in traces (colony-memory prerequisites).
ARCHITECTURE: Drives the real compiled graph with scripted executors and a RecordingTracer.
"""

from __future__ import annotations

import unittest

from tests.kernel.scheduler.support import Rig, descriptor


def _events(rig: Rig, name: str):
    return [c for c in rig.tracer.calls if c.kind == "event" and c.name == name]


class TestRunFinalizedEvent(unittest.IsolatedAsyncioTestCase):
    """finalize reports the terminal status to the tracer inside its own span."""

    async def test_finalize_emits_run_finalized_under_the_finalize_span(self) -> None:
        rig = Rig([descriptor("decide.root")])
        rig.bind("decide.root")
        _, _, state = await rig.start()
        (event,) = _events(rig, "run.finalized")
        self.assertEqual(event.data["payload"]["status"], state["outcome"].status.value)
        self.assertEqual(event.corr.run_id, state["run_id"])
        parent = rig.tracer.calls[event.parent]
        self.assertEqual(parent.name, "kernel.finalize")
        self.assertEqual(parent.data["span_kind"], "node")

    async def test_blocked_run_reports_its_status(self) -> None:
        rig = Rig([descriptor("decide.other", kinds=("options",))])
        rig.bind("decide.other")
        _, _, state = await rig.start()
        (event,) = _events(rig, "run.finalized")
        self.assertEqual(event.data["payload"]["status"], "blocked")
        self.assertEqual(state["outcome"].status.value, "blocked")


class TestGapRecordedEvent(unittest.IsolatedAsyncioTestCase):
    """record_gaps emits one tracer event per recorded gap, correlated to the work item."""

    async def test_gap_event_matches_the_stored_observation(self) -> None:
        rig = Rig([descriptor("decide.other", kinds=("options",))])
        rig.bind("decide.other")
        _, _, state = await rig.start()
        (event,) = _events(rig, "gap.recorded")
        (stored,) = rig.gap_store.observations
        payload = event.data["payload"]
        self.assertEqual(payload["gap_key"], stored.gap_key)
        self.assertEqual(payload["gap_type"], stored.gap_type.value)
        self.assertEqual(payload["gap_id"], stored.id)
        self.assertTrue(event.corr.work_item_id)
        self.assertIn(event.corr.work_item_id, state["work_items"])
        self.assertNotIn("goal", payload)


if __name__ == "__main__":
    unittest.main()
