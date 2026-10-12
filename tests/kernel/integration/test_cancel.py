"""
MODULE: tests.kernel.integration.test_cancel
GOAL: Test cancellation end to end through the real service, graph, sqlite checkpointer and file
    stores: cancel while a native capability runs, while the run waits for the host and while it
    waits for a human; first actor wins; a cancelled run cannot resume; a stale writer cannot
    lose the cancel; `run.cancelled` reaches events.jsonl without colliding with graph events.
BUSINESS CONTEXT: A user must be able to stop a run at any moment and trust that nothing runs on
    afterwards, that the open work is closed (children included) and that the record shows who
    cancelled and when (Rev 3 sections 8.4, 13.1 and 16, "Cancelled run").
ARCHITECTURE: Two KernelService instances over one run root model two processes. The running
    process is held inside a gated executor while the second one cancels. The design's risk 5
    (`aupdate_state` on a paused thread) is pinned by asserting the closed thread's checkpoint.
"""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from typing import Any

from langgraph.types import Command

from kernel.contracts import Actor, ActorKind, RunStatus, WorkItemStatus, schema_ids
from kernel.contracts.base import utc_now
from kernel.interaction import RejectionCode, SubmissionRejected
from kernel.persistence import FileRunStore, RunRecord
from kernel.persistence.memory import MemoryRunStore
from kernel.service import KernelService
from kernel.service_cancel import (
    SERVICE_SEQ_BASE,
    append_service_event,
    commit_cancel,
    compare_and_write,
)
from kernel.service_session import open_session
from tests.kernel.adapters.support import answer, rig_environment
from tests.kernel.helpers import narrow
from tests.kernel.interaction.support import host_rig, human_rig, human_submission
from tests.kernel.scheduler.support import (
    Rig,
    completed,
    descriptor,
    proposal,
    retrieval_descriptor,
    waiting,
)

HUMAN = Actor(id="human:tester", kind=ActorKind.HUMAN)
OTHER = Actor(id="human:other", kind=ActorKind.HUMAN)


class Gate:
    """Executor that holds the run inside the capability until the test releases it."""

    def __init__(self) -> None:
        """Create the two events."""
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.invocations: list = []

    async def ainvoke(self, invocation: Any, ctx: Any) -> Any:
        """Signal the start, wait for the release, then ask for one evidence child."""
        self.invocations.append(invocation)
        self.started.set()
        await self.release.wait()
        return waiting(invocation, proposal())


class CancelCase(unittest.IsolatedAsyncioTestCase):
    """A run root shared by several service instances (one per simulated process)."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.rig: Rig = host_rig()

    def service(self, rig: Rig | None = None) -> KernelService:
        """Return a service over a fresh environment on the shared run root."""
        self.env = rig_environment(self.root, rig or self.rig)
        return KernelService(self.env)

    def events(self, run_id: str) -> list:
        """Return the events.jsonl entries of a run."""
        return FileRunStore(self.root).read_events(run_id)

    def assert_event_log_is_collision_free(self, run_id: str) -> None:
        """Graph events keep their own contiguous numbers; service events sit above them."""
        seqs = [e.seq for e in self.events(run_id)]
        self.assertEqual(len(seqs), len(set(seqs)))
        graph = [s for s in seqs if s < SERVICE_SEQ_BASE]
        self.assertEqual(graph, list(range(len(graph))))
        cancelled = [e for e in self.events(run_id) if e.kind == "run.cancelled"]
        self.assertEqual(len(cancelled), 1)
        self.assertGreaterEqual(cancelled[0].seq, SERVICE_SEQ_BASE)

    async def closed_thread(self, run_id: str) -> tuple[Any, Any, Any, Any]:
        """Open a status session and return (snapshot, graph, config, runtime) of the thread."""
        env = rig_environment(self.root, self.rig)
        async with open_session(env, "status", run_id) as session:
            snapshot = await session.graph.aget_state(session.config)
            return snapshot, session.graph, session.config, session.runtime


class TestCancelWhileWaiting(CancelCase):
    """A paused run is closed: no pending interaction, open work cancelled, resume refused."""

    async def test_cancel_while_waiting_host_closes_the_thread_and_refuses_resume(self) -> None:
        paused = await self.service().start_run(self.rig.task_input())
        cancelled = await self.service().cancel_run(paused.run_id, HUMAN)
        self.assertEqual(cancelled.status, RunStatus.CANCELLED)
        self.assertIsNone(cancelled.pending_interaction)
        record = self.env.run_store.get_run(paused.run_id)
        self.assertEqual((record.status, narrow(record.cancel).by), (RunStatus.CANCELLED, HUMAN.id))
        self.assert_event_log_is_collision_free(paused.run_id)
        snapshot, graph, config, runtime = await self.closed_thread(paused.run_id)
        self.assertEqual(snapshot.next, ())
        self.assertFalse(any(t.interrupts for t in snapshot.tasks))  # risk 5: interrupt dropped
        values = snapshot.values
        self.assertEqual(values["status"], RunStatus.CANCELLED)
        self.assertEqual(values["interaction_queue"], [])
        self.assertTrue(all(i.status in (WorkItemStatus.CANCELLED, WorkItemStatus.COMPLETED)
                            for i in values["work_items"].values()))
        self.assertEqual(sum(i.status is WorkItemStatus.CANCELLED
                             for i in values["work_items"].values()), 2)  # root and its child
        self.assertEqual(values["outcome"].status, RunStatus.CANCELLED)
        with self.assertRaises(SubmissionRejected) as caught:
            await self.service().resume_run(paused.run_id, answer(paused))
        self.assertEqual(caught.exception.code, RejectionCode.CANCELLED_OR_SUPERSEDED)
        self.assertEqual(caught.exception.envelope.status, RunStatus.CANCELLED)

    async def test_a_closed_thread_ignores_a_direct_resume_instead_of_running_nodes(self) -> None:
        paused = await self.service().start_run(self.rig.task_input())
        await self.service().cancel_run(paused.run_id, HUMAN)
        before = len(self.rig.executors["decide.root"].invocations)
        env = rig_environment(self.root, self.rig)
        async with open_session(env, "resume", paused.run_id) as session:
            out = await session.graph.ainvoke(
                Command(resume=answer(paused).model_dump(mode="json")), session.config,
                context=session.runtime, version="v2", durability="sync")
        self.assertEqual(out.value["status"], RunStatus.CANCELLED)
        self.assertEqual(len(self.rig.executors["decide.root"].invocations), before)

    async def test_cancel_while_waiting_human_cancels_the_question(self) -> None:
        # covers: DK-600b-2-iii
        self.rig = human_rig()
        paused = await self.service().start_run(self.rig.task_input())
        self.assertEqual(paused.status, RunStatus.WAITING_HUMAN)
        question = paused.pending_interaction
        cancelled = await self.service().cancel_run(paused.run_id, HUMAN)
        self.assertEqual((cancelled.status, cancelled.pending_interaction),
                         (RunStatus.CANCELLED, None))
        self.assert_event_log_is_collision_free(paused.run_id)
        raw = human_submission(narrow(question).model_dump(mode="json"), paused.run_id,
                               {"choice_id": "sqlite"})
        with self.assertRaises(SubmissionRejected) as caught:
            await self.service().resume_run(paused.run_id, raw)
        self.assertEqual(caught.exception.code, RejectionCode.CANCELLED_OR_SUPERSEDED)
        snapshot, *_ = await self.closed_thread(paused.run_id)
        self.assertEqual(snapshot.next, ())
        self.assertEqual(snapshot.values["interaction_queue"], [])

    async def test_first_actor_wins_and_a_repeat_changes_nothing(self) -> None:
        paused = await self.service().start_run(self.rig.task_input())
        await self.service().cancel_run(paused.run_id, HUMAN)
        first = self.env.run_store.get_run(paused.run_id)
        again = await self.service().cancel_run(paused.run_id, OTHER)
        self.assertEqual(again.status, RunStatus.CANCELLED)
        self.assertEqual(self.env.run_store.get_run(paused.run_id), first)
        self.assertEqual(narrow(first.cancel).by, HUMAN.id)
        self.assert_event_log_is_collision_free(paused.run_id)  # exactly one run.cancelled


class TestCancelWhileRunning(CancelCase):
    """A graph running in another process stops at its next superstep."""

    async def test_cancel_while_a_capability_runs_stops_the_run_and_cancels_the_children(self
                                                                                          ) -> None:
        rig = Rig([descriptor("decide.root"), retrieval_descriptor()])
        gate = rig.bind("decide.root", Gate())
        rig.bind("retrieve.test", factory=lambda inv: completed(inv, schema_ids.EVIDENCE_BUNDLE))
        running = asyncio.create_task(self.service(rig).start_run(
            rig.task_input(), run_id="run-cancel-running-1"))
        await asyncio.wait_for(gate.started.wait(), 60)
        cancelled = await self.service(rig).cancel_run("run-cancel-running-1", HUMAN)
        self.assertEqual(cancelled.status, RunStatus.CANCELLED)
        gate.release.set()
        final = await asyncio.wait_for(running, 60)
        self.assertEqual(final.status, RunStatus.CANCELLED)
        record = FileRunStore(self.root).get_run("run-cancel-running-1")
        self.assertEqual((record.status, narrow(record.cancel).by), (RunStatus.CANCELLED, HUMAN.id))
        self.assertEqual(rig.executors["retrieve.test"].invocations, [])  # nothing ran on
        kinds = [e.kind for e in self.events("run-cancel-running-1")]
        self.assertIn("guard.tripped", kinds)
        self.assertIn("run.cancelled", kinds)
        self.assertEqual(kinds[-1], "run.cancelled")  # service events sort after graph events
        self.assert_event_log_is_collision_free("run-cancel-running-1")
        env = rig_environment(self.root, rig)
        async with open_session(env, "status", "run-cancel-running-1") as session:
            values = await session.values()
        statuses = {i.status for i in values["work_items"].values()}
        self.assertEqual(statuses, {WorkItemStatus.CANCELLED})
        self.assertEqual(len(values["work_items"]), 2)  # root and the child it proposed


class _RacingStore(FileRunStore):
    """A store whose first compare-and-update loses to another writer."""

    def __init__(self, root: Path) -> None:
        """Count the compare calls."""
        super().__init__(root)
        self.compares = 0

    def compare_and_update(self, record: RunRecord, expected_revision: int) -> bool:
        """Let a competing writer bump the revision first, once."""
        self.compares += 1
        if self.compares == 1:
            current = self.get_run(record.run_id)
            self.update_run(current.model_copy(update={
                "state_revision": current.state_revision + 1}))
        return super().compare_and_update(record, expected_revision)


class TestCompareAndUpdate(unittest.TestCase):
    """The cancel commit uses compare-and-update: stale writers retry or lose, never win."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()

    def test_a_lost_compare_is_retried_against_a_fresh_read(self) -> None:
        store = _RacingStore(self.root)
        store.create_run(RunRecord(run_id="run-1", root_task_id="task-1"))
        record, won = commit_cancel(store, "run-1", HUMAN.id, utc_now())
        self.assertTrue(won)
        self.assertEqual(store.compares, 2)
        self.assertEqual(narrow(store.get_run("run-1").cancel).by, HUMAN.id)
        self.assertEqual(record.state_revision, 2)  # the competing bump plus the cancel

    def test_a_stale_writer_cannot_overwrite_a_committed_cancel(self) -> None:
        store = FileRunStore(self.root)
        store.create_run(RunRecord(run_id="run-1", root_task_id="task-1"))
        stale = store.get_run("run-1")
        commit_cancel(store, "run-1", HUMAN.id, utc_now())
        racing = stale.model_copy(update={"status": RunStatus.WAITING_HOST})
        self.assertFalse(compare_and_write(store, racing, stale.state_revision))
        kept = store.get_run("run-1")
        self.assertEqual((kept.status, narrow(kept.cancel).by), (RunStatus.CANCELLED, HUMAN.id))

    def test_the_second_actor_loses_and_a_finished_run_cannot_be_cancelled(self) -> None:
        store = FileRunStore(self.root)
        store.create_run(RunRecord(run_id="run-1", root_task_id="task-1"))
        store.create_run(RunRecord(run_id="run-2", root_task_id="task-1",
                                   status=RunStatus.COMPLETED))
        first, won_first = commit_cancel(store, "run-1", HUMAN.id, utc_now())
        second, won_second = commit_cancel(store, "run-1", OTHER.id, utc_now())
        self.assertEqual((won_first, won_second), (True, False))
        self.assertEqual(second.cancel, first.cancel)
        _, won_done = commit_cancel(store, "run-2", HUMAN.id, utc_now())
        self.assertFalse(won_done)
        self.assertIsNone(store.get_run("run-2").cancel)

    def test_a_store_without_compare_and_update_falls_back_to_a_plain_update(self) -> None:
        store = MemoryRunStore()
        store.create_run(RunRecord(run_id="run-1", root_task_id="task-1"))
        _, won = commit_cancel(store, "run-1", HUMAN.id, utc_now())
        self.assertTrue(won)
        self.assertTrue(store.is_cancelled("run-1"))

    def test_service_events_use_the_reserved_range_in_order(self) -> None:
        store = FileRunStore(self.root)
        store.create_run(RunRecord(run_id="run-1", root_task_id="task-1"))
        first = append_service_event(store, "run-1", "run.cancelled", utc_now())
        second = append_service_event(store, "run-1", "run.note", utc_now())
        self.assertEqual((first.seq, second.seq), (SERVICE_SEQ_BASE, SERVICE_SEQ_BASE + 1))
        self.assertEqual([e.kind for e in store.read_events("run-1")],
                         ["run.cancelled", "run.note"])


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 15:00 [python-coder]: The running-process case holds the graph inside a gated
#   executor and cancels from a second service on the same run root: that is the real race
#   (cancel lands between supersteps of another process), not a stubbed probe.
#   (#KernelBootstrapV0/P9)
# ====================================================================
