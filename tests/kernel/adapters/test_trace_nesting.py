"""
MODULE: tests.kernel.adapters.test_trace_nesting
GOAL: Test bug D: after a resume, invocations and host packets must nest under the CURRENT
    process segment's trace, not under the segment that started the run.
BUSINESS CONTEXT: One run is one Langfuse trace with a segment root per process (Rev 3 section
    12.2). If work created after a resume still named the start segment as its parent, the trace
    tree would show resumed work under a segment that had already ended.
ARCHITECTURE: A root capability that waits on a host child twice before completing, so there are
    three processes (start, resume, resume) each creating new work. Each process gets a tracer
    with its own segment-id prefix; the checkpointed invocations and packets are inspected.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from kernel.contracts import CapabilityInvocation, schema_ids
from kernel.service import KernelService
from kernel.service_session import open_session
from tests.kernel.adapters.support import SegmentTracer, answer, rig_environment
from tests.kernel.scheduler.support import Rig, completed, descriptor, proposal, waiting

SECOND_QUESTION = "Which queue does the cache use?"


def three_phases(inv: CapabilityInvocation) -> Any:
    """Wait on a host child, wait on a second one, then complete."""
    phase = inv.continuation.state.get("phase", 0) if inv.continuation else 0
    if phase == 0:
        return waiting(inv, proposal(), state={"phase": 1})
    if phase == 1:
        return waiting(inv, proposal(question=SECOND_QUESTION), state={"phase": 2})
    return completed(inv)


def two_handoff_rig() -> Rig:
    """Return a rig whose root pauses at two successive host handoffs."""
    rig = Rig([descriptor("decide.root"),
               descriptor("host.research", kinds=("evidence",), mode="host_handoff",
                          accepts=schema_ids.RETRIEVAL_REQUEST, produces=schema_ids.EVIDENCE_BUNDLE,
                          operations=("bounded_research",))])
    rig.bind("decide.root", factory=three_phases)
    rig.bind("host.research")
    return rig


class TestResumedWorkNestsUnderTheCurrentSegment(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.root, self.rig = Path(tmp.name).resolve(), two_handoff_rig()

    def process(self, prefix: str) -> KernelService:
        """Return a service for a new 'process' whose segments are named `<prefix>-...`."""
        self.env = rig_environment(self.root, self.rig, tracer=SegmentTracer(prefix=prefix))
        return KernelService(self.env)

    async def invocations(self, run_id: str) -> list[CapabilityInvocation]:
        """Return the checkpointed invocations in creation order."""
        record = self.env.run_store.get_run(run_id)
        async with open_session(self.env, "status", run_id, record.root_task_id) as session:
            values = await session.values()
        return sorted(values["invocations"].values(), key=lambda i: i.created_seq)

    async def test_new_invocations_and_packets_follow_the_segment_that_created_them(self) -> None:
        first = await self.process("p1").start_run(self.rig.task_input())
        second = await self.process("p2").resume_run(first.run_id, answer(first))
        third = await self.process("p3").resume_run(second.run_id, answer(second))
        self.assertEqual(third.status.value, "completed")
        self.assertEqual(first.pending_interaction.trace_context.parent_observation_id,
                         "p1-1-start")
        self.assertEqual(second.pending_interaction.trace_context.parent_observation_id,
                         "p2-1-resume")
        self.assertNotEqual(second.pending_interaction.id, first.pending_interaction.id)

    async def test_root_invocations_name_the_segment_of_their_own_process(self) -> None:
        first = await self.process("p1").start_run(self.rig.task_input())
        second = await self.process("p2").resume_run(first.run_id, answer(first))
        await self.process("p3").resume_run(second.run_id, answer(second))
        roots = [i for i in await self.invocations(first.run_id)
                 if i.capability_id == "decide.root"]
        parents = [i.trace.parent_observation_id for i in roots]
        self.assertEqual(parents, ["p1-1-start", "p2-1-resume", "p3-1-resume"])
        self.assertEqual({i.trace.trace_id for i in roots}, {first.trace_refs.trace_id})


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 13:40 [python-coder]: Segment prefixes differ per simulated process, so a parent id
#   that still named the start segment after a resume would fail the assertion by name.
#   (#KernelBootstrapV0/P7)
# ====================================================================
