"""
MODULE: tests.kernel.interaction.test_trace_events
GOAL: Test the observation-map events of the interaction path with a RecordingTracer:
    `interaction.opened` when a packet is created, `submission.accepted` once after the resume,
    and `submission.rejected` with the stable code, each carrying the interaction id.
BUSINESS CONTEXT: The trace is how an operator sees a run wait, resume and refuse input (design
    part 5); events must be small, carry ids and codes only, and must not repeat because the
    paused node re-executes on resume.
ARCHITECTURE: Real graph and `submit_interaction` over the scheduler Rig, whose tracer is the
    RecordingTracer; nothing is asserted about span nesting here.
"""

from __future__ import annotations

import unittest

from kernel.interaction import SubmissionRejected
from tests.kernel.interaction.support import (
    host_rig,
    human_rig,
    human_submission,
    raw_submission,
    start,
)


class TestInteractionTraceEvents(unittest.IsolatedAsyncioTestCase):
    """Opened, accepted and rejected events appear exactly once, with ids and codes."""

    async def test_opened_is_traced_once_with_the_interaction_id_and_nothing_else_yet(self) -> None:
        run = await start(host_rig())
        opened = run.rig.tracer.named("interaction.opened", "event")
        self.assertEqual([c.corr.interaction_id for c in opened], [run.packet["id"]])
        self.assertEqual(opened[0].data["payload"]["kind"], "host")
        self.assertEqual(run.rig.tracer.named("submission.accepted"), [])
        self.assertEqual(run.rig.tracer.named("submission.rejected"), [])

    async def test_a_rejection_is_traced_once_with_its_code_and_a_later_accept_once(self) -> None:
        run = await start(human_rig())
        with self.assertRaises(SubmissionRejected):
            await run.submit(human_submission(run.packet, run.run_id, {"choice_id": "nope"},
                                              revision=run.packet["state_revision"]))
        with self.assertRaises(SubmissionRejected):
            await run.submit(human_submission(run.packet, run.run_id, {"choice_id": "sqlite"},
                                              revision=99))
        rejected = run.rig.tracer.named("submission.rejected", "event")
        self.assertEqual([c.data["payload"]["code"] for c in rejected],
                         ["semantic_invalid", "stale_revision"])
        self.assertEqual({c.corr.interaction_id for c in rejected}, {run.packet["id"]})
        await run.submit(human_submission(run.packet, run.run_id, {"choice_id": "sqlite"}))
        accepted = run.rig.tracer.named("submission.accepted", "event")
        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0].data["payload"]["actor_kind"], "human")

    async def test_invalid_host_output_is_traced_once_per_submission_not_per_replay(self) -> None:
        run = await start(host_rig())
        bad = raw_submission(run.packet, run.run_id, response={"evidence_ids": "nope"})
        with self.assertRaises(SubmissionRejected):
            await run.submit(bad)
        await run.submit(raw_submission(run.packet, run.run_id))
        self.assertEqual(len(run.rig.tracer.named("submission.rejected", "event")), 1)
        accepted = run.rig.tracer.named("submission.accepted", "event")
        self.assertEqual([c.data["payload"]["rejections_before"] for c in accepted], [1])


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:59 [python-coder]: The repeat check submits one invalid host output before the
#   valid one: the node replays that first resume value when it re-executes, so a rejection traced
#   inside the node would be recorded twice. (#KernelBootstrapV0/P6)
# ====================================================================
