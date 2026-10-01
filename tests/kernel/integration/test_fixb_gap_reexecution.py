"""
MODULE: tests.kernel.integration.test_fixb_gap_reexecution
GOAL: Prove a gap observation is stored once when a node re-executes after it published the
    observation but before its checkpoint committed.
BUSINESS CONTEXT: Occurrence counts are demand evidence for the capability backlog (Rev 3 section
    14); a crash-and-resume must not double-count one operation.
ARCHITECTURE: A real run through the interaction rig, then the same `record_host_only` call a
    resumed node would make again, against the memory and the file gap store.
"""

from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from kernel.contracts import FallbackOutcome, GapType
from kernel.persistence.gap_store import FileGapStore
from kernel.scheduler.nodes_gaps import record_host_only
from tests.kernel.interaction.support import host_rig, raw_submission, start


class TestReexecutedObservation(unittest.IsolatedAsyncioTestCase):
    """A second execution of the same observation changes nothing."""

    async def _finished_run(self):
        run = await start(host_rig())
        result = await run.submit(raw_submission(run.packet, run.run_id))
        item = next(i for i in result.state["work_items"].values()
                    if i.binding and i.binding.capability_id == "host.research")
        return run, result.state, item

    async def test_a_reexecuted_host_only_record_is_not_counted_twice(self) -> None:
        run, state, item = await self._finished_run()
        store = run.rig.gap_store
        before = [g for g in store.observations if g.gap_type is GapType.HOST_ONLY]
        self.assertEqual(len(before), 1)
        again = record_host_only(state, run.context, item, FallbackOutcome.HOST_COMPLETED)
        host_only = [g for g in store.observations if g.gap_type is GapType.HOST_ONLY]
        self.assertEqual(len(host_only), 1, "the re-executed node stored a second observation")
        self.assertEqual(again[0].id, before[0].id)
        self.assertEqual(sum(g.occurrence_count for g in store.load_gaps()), 1)

    async def test_the_file_store_dedupes_the_same_deterministic_observation(self) -> None:
        run, state, item = await self._finished_run()
        with tempfile.TemporaryDirectory() as tmp:
            store = FileGapStore(Path(tmp))
            ctx = replace(run.context, gap_store=store)
            first = record_host_only(state, ctx, item, FallbackOutcome.HOST_COMPLETED)
            second = record_host_only(state, ctx, item, FallbackOutcome.HOST_COMPLETED)
            self.assertEqual(first[0].id, second[0].id)
            self.assertEqual(sum(g.occurrence_count for g in store.load_gaps()), 1)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 20:00 [python-coder]: Regression for review finding R1-5 (random observation ids
#   defeated the stores' id dedupe). (#KernelBootstrapV0/FIXB)
# ====================================================================
