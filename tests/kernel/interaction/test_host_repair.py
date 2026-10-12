"""
MODULE: tests.kernel.interaction.test_host_repair
GOAL: Test the bounded repair of invalid host output: the host is told why, gets
    `host.max_repair_attempts` corrections, and the next invalid output fails the work item
    without corrupting state; a valid correction completes it.
BUSINESS CONTEXT: A cooperative host may produce malformed output (Rev 3 section 11.6); the run
    must neither loop forever on it nor accept it, and invalid content must never reach evidence.
ARCHITECTURE: Real graph and `submit_interaction`; the bound is set through the real config
    model. The repair counter is asserted on the packet the host actually receives.
"""

from __future__ import annotations

import unittest
from typing import Any

from langgraph.types import Command

from kernel.contracts import HostWorkRequest, RunStatus, WorkItemStatus
from kernel.interaction import RejectionCode, SubmissionRejected, SubmitStatus
from tests.kernel.helpers import as_type
from tests.kernel.interaction.support import BUNDLE, Started, host_rig, raw_submission, start

BAD = {"evidence_ids": "not-a-list"}
CITES_MISSING = {**BUNDLE, "evidence_ids": ["ev-0000000000000000"]}


async def started(max_repairs: int) -> Started:
    """Start a one-host-item run whose config allows `max_repairs` corrections."""
    rig = host_rig()
    host = rig.config.host.model_copy(update={"max_repair_attempts": max_repairs})
    rig.config = rig.config.model_copy(update={"host": host})
    return await start(rig)


def host_items(state: dict) -> list:
    """Return the work items bound to the host research capability."""
    return [i for i in state["work_items"].values()
            if i.binding and i.binding.capability_id == "host.research"]


class TestRepairBound(unittest.IsolatedAsyncioTestCase):
    """max_repair_attempts corrections, then the item fails."""

    async def test_invalid_output_is_rejected_and_the_host_is_told_why(self) -> None:
        run = await started(1)
        with self.assertRaises(SubmissionRejected) as caught:
            await run.submit(raw_submission(run.packet, run.run_id, response=BAD))
        self.assertEqual(caught.exception.code, RejectionCode.SCHEMA_INVALID)
        self.assertEqual(caught.exception.details["repairs_remaining"], 0)
        again = caught.exception.details["pending_interaction"]
        self.assertEqual(again["id"], run.packet["id"])
        self.assertEqual([r["code"] for r in again["rejections"]], ["schema_invalid"])
        self.assertIn("evidence_ids", again["rejections"][0]["message"])
        stored = run.rig.run_store.load_interaction(run.run_id, run.packet["id"])
        self.assertEqual(len(as_type(stored, HostWorkRequest).rejections), 1)

    async def test_a_valid_correction_within_the_bound_completes_the_item(self) -> None:
        run = await started(1)
        with self.assertRaises(SubmissionRejected):
            await run.submit(raw_submission(run.packet, run.run_id, response=BAD))
        result = await run.submit(raw_submission(run.packet, run.run_id))
        self.assertEqual(result.status, SubmitStatus.ACCEPTED)
        self.assertEqual(result.state["outcome"].status, RunStatus.COMPLETED)
        self.assertEqual([i.status for i in host_items(result.state)], [WorkItemStatus.COMPLETED])
        self.assertIsNotNone(run.rig.run_store.get_submission(run.run_id, run.packet["id"]))

    async def test_the_submission_after_the_bound_fails_the_item_without_corrupting_state(self) -> None:
        run = await started(1)
        with self.assertRaises(SubmissionRejected):
            await run.submit(raw_submission(run.packet, run.run_id, response=BAD))
        result = await run.submit(raw_submission(run.packet, run.run_id, response=CITES_MISSING))
        self.assertEqual(result.status, SubmitStatus.REPAIR_EXHAUSTED)
        state = result.state
        self.assertEqual([i.status for i in host_items(state)], [WorkItemStatus.FAILED])
        self.assertEqual(state["interaction_queue"], [])
        self.assertIsNone(result.pending)
        self.assertEqual(state["evidence"], {})
        kinds = [e.kind for e in state["events"]]
        self.assertEqual(kinds.count("interaction.rejected"), 2)
        self.assertEqual(kinds.count("interaction.repair_exhausted"), 1)
        self.assertIsNone(run.rig.run_store.get_submission(run.run_id, run.packet["id"]))
        self.assertIn("outcome", state)

    async def test_zero_repairs_fails_on_the_first_invalid_output(self) -> None:
        run = await started(0)
        result = await run.submit(raw_submission(run.packet, run.run_id, response=BAD))
        self.assertEqual(result.status, SubmitStatus.REPAIR_EXHAUSTED)
        self.assertEqual([i.status for i in host_items(result.state)], [WorkItemStatus.FAILED])

    async def test_only_content_errors_consume_repairs(self) -> None:
        run = await started(1)
        for _ in range(3):
            with self.assertRaises(SubmissionRejected) as caught:
                await run.submit(raw_submission(run.packet, run.run_id, revision=99))
            self.assertEqual(caught.exception.code, RejectionCode.STALE_REVISION)
        stored = run.rig.run_store.load_interaction(run.run_id, run.packet["id"])
        self.assertEqual(as_type(stored, HostWorkRequest).rejections, [])

    async def test_a_late_submission_for_the_failed_item_is_reported_as_superseded(self) -> None:
        run = await started(0)
        await run.submit(raw_submission(run.packet, run.run_id, response=BAD))
        with self.assertRaises(SubmissionRejected) as caught:
            await run.submit(raw_submission(run.packet, run.run_id))
        self.assertEqual(caught.exception.code, RejectionCode.CANCELLED_OR_SUPERSEDED)


class TestRejectionDoesNotForkTheGraph(unittest.IsolatedAsyncioTestCase):
    """Resuming the graph directly with a rejected value keeps it on one branch."""

    async def resume(self, run: Started, raw: dict) -> Any:
        """Resume the paused graph exactly as any LangGraph client could."""
        return await run.graph.ainvoke(Command(resume=raw), run.config, context=run.context,
                                       version="v2", durability="sync")

    async def test_a_rejected_then_a_valid_resume_behaves_like_a_single_valid_resume(self) -> None:
        clean = await start(host_rig())
        final_clean = (await self.resume(clean, raw_submission(clean.packet, clean.run_id))).value
        run = await start(host_rig())
        still = await self.resume(run, raw_submission(run.packet, run.run_id, revision=99))
        self.assertEqual(still.interrupts[0].value["id"], run.packet["id"])
        paused = await run.values()
        self.assertEqual([t.name for t in (await run.graph.aget_state(run.config)).tasks],
                         ["await_interaction"])
        self.assertEqual(paused["budgets"], run.state["budgets"])  # no scheduler step ran
        final = (await self.resume(run, raw_submission(run.packet, run.run_id))).value
        self.assertEqual(final["outcome"].status, RunStatus.COMPLETED)
        self.assertEqual(final["budgets"].scheduler_iterations,
                         final_clean["budgets"].scheduler_iterations)
        self.assertNotIn("deadlock", [e.detail for e in final["events"]
                                      if e.kind == "guard.tripped"])


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:59 [python-coder]: max_repair_attempts=N means N corrections after the first
#   invalid output; the (N+1)th invalid output fails the item, so 0 fails at once.
#   (#KernelBootstrapV0/P6)
# ====================================================================
