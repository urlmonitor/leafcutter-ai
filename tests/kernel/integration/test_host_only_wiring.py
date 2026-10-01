"""
MODULE: tests.kernel.integration.test_host_only_wiring
GOAL: Prove that one executed host operation yields exactly one `host_only` observation: at
    answer time, when the repair budget is exhausted, and when the run is resumed by a fresh
    graph and runtime (a restart), with no second count from `settle_gap_outcomes`.
BUSINESS CONTEXT: Demand for host-only operations is evidence for a native capability (Rev 3
    section 14, ADR-056); counting an operation twice would inflate that demand.
ARCHITECTURE: Real compiled graph and ledgered submission entry point over the interaction
    rig; the observation count is read from the gap store, the run events and the final state.
"""

from __future__ import annotations

import unittest
from unittest import mock

from kernel.config import HostConfig
from kernel.contracts import FallbackOutcome, GapType, RunStatus
from kernel.scheduler import nodes_gaps
from kernel.interaction import SubmissionRejected, submit_interaction
from kernel.scheduler import build_kernel_graph
from tests.kernel.interaction.support import host_rig, raw_submission, start

BAD = {"evidence_ids": "not-a-list"}


def host_only(store) -> list:
    """Return the host_only observations recorded in the gap store."""
    return [g for g in store.observations if g.gap_type is GapType.HOST_ONLY]


def recorded_events(state: dict) -> list:
    """Return the gap.recorded run events of a final state."""
    return [e for e in state["events"] if e.kind == "gap.recorded"]


class TestHostOnlyRecordedOnce(unittest.IsolatedAsyncioTestCase):
    """The interaction node records the observation; settlement does not repeat it."""

    async def test_one_host_operation_is_one_observation(self) -> None:
        run = await start(host_rig())
        result = await run.submit(raw_submission(run.packet, run.run_id))
        self.assertIs(result.state["outcome"].status, RunStatus.COMPLETED)
        (gap,) = host_only(run.rig.gap_store)
        self.assertIs(gap.fallback_outcome, FallbackOutcome.HOST_COMPLETED)
        self.assertEqual(len(recorded_events(result.state)), 1)
        self.assertEqual(len(result.state["gaps"]), 1)

    async def test_the_answer_records_it_and_settlement_adds_nothing(self) -> None:
        settled: list[dict] = []
        real = nodes_gaps._settle_host_only

        def spy(*args, **kwargs):
            settled.append(real(*args, **kwargs))
            return settled[-1]

        run = await start(host_rig())
        with mock.patch.object(nodes_gaps, "_settle_host_only", spy):
            await run.submit(raw_submission(run.packet, run.run_id))
        self.assertTrue(settled, "schedule must have run its settlement after the answer")
        self.assertEqual([r for r in settled if r], [])
        self.assertEqual(len(host_only(run.rig.gap_store)), 1)

    async def test_a_resume_by_a_fresh_graph_and_runtime_still_counts_once(self) -> None:
        run = await start(host_rig())
        restarted = build_kernel_graph(run.graph.checkpointer)
        result = await submit_interaction(restarted, run.config, run.rig.runtime(),
                                          run.rig.run_store, run.run_id,
                                          raw_submission(run.packet, run.run_id))
        self.assertIs(result.state["outcome"].status, RunStatus.COMPLETED)
        self.assertEqual(len(host_only(run.rig.gap_store)), 1)
        self.assertEqual(len(recorded_events(result.state)), 1)

    async def test_exhausted_repairs_record_one_host_failed_observation(self) -> None:
        rig = host_rig()
        rig.config = rig.config.model_copy(update={
            "host": rig.config.host.model_copy(update={"max_repair_attempts": 1})})
        self.assertIsInstance(rig.config.host, HostConfig)
        run = await start(rig)
        with self.assertRaises(SubmissionRejected):
            await run.submit(raw_submission(run.packet, run.run_id, response=BAD))
        result = await run.submit(raw_submission(run.packet, run.run_id, response=BAD))
        (gap,) = host_only(rig.gap_store)
        self.assertIs(gap.fallback_outcome, FallbackOutcome.HOST_FAILED)
        self.assertEqual(len(recorded_events(result.state)), 1)

    async def test_a_human_question_records_no_host_only_observation(self) -> None:
        from tests.kernel.interaction.support import human_rig, human_submission
        run = await start(human_rig())
        await run.submit(human_submission(run.packet, run.run_id, {"choice_id": "sqlite"}))
        self.assertEqual(host_only(run.rig.gap_store), [])


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 17:40 [python-coder]: The restart case rebuilds the graph and runtime over the
#   same checkpointer instead of spawning a process; the process-level restart of the interaction
#   itself is already covered by test_restart_resume. (#KernelBootstrapV0/INT2)
# ====================================================================
