"""
MODULE: tests.kernel.scheduler.test_guards_hardening
GOAL: Test the P9 guard hardening: Unicode-stable duplicate keys, a reworded repeated question
    ending in blocked or partial instead of looping, cycle-safe ancestor walks, run-level Jev and
    host caps, per-call timeout, active time that never includes human wait, and trips that
    name the unresolved work.
BUSINESS CONTEXT: A run must always end as a partial or blocked envelope with diagnostics and the
    work it did not finish (Rev 3 sections 8.4, 13.2 and 16, "Repeated question with no new
    information"); no wording trick may reset a guard.
ARCHITECTURE: Pure guard functions are unit-tested directly; every end-to-end claim drives the
    compiled graph and asserts the outcome, the item statuses and the capability call counts.
"""

from __future__ import annotations

import asyncio
import itertools
import types
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

from kernel.config import load_kernel_config
from kernel.contracts import RunEvent, RunStatus, WorkItem, WorkItemStatus, schema_ids
from kernel.scheduler import decide_outcome
from kernel.scheduler.guards import (
    ancestor_ids,
    check_run_guards,
    host_operations_available,
    normalize_text,
    reaches,
    request_dedup_key,
    unresolved_item_ids,
    unresolved_text,
    waiting_seconds,
)
from kernel.scheduler.nodes_schedule import schedule
from kernel.scheduler.state import Budgets
from tests.kernel.helpers import narrow
from tests.kernel.interaction.support import host_rig, raw_submission, start
from tests.kernel.scheduler.support import (
    Rig,
    completed,
    descriptor,
    proposal,
    retrieval_descriptor,
    two_phase,
    waiting,
    with_limits,
)

QUESTION = "Which store does the cache use?"
T0 = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


def _rig(root_factory, child_factory=None, **limits) -> Rig:
    rig = Rig([descriptor("decide.root"), retrieval_descriptor()])
    rig.bind("decide.root", factory=root_factory)
    rig.bind("retrieve.test", factory=child_factory or (
        lambda inv: completed(inv, schema_ids.EVIDENCE_BUNDLE)))
    rig.config = with_limits(load_kernel_config(), **limits)
    return rig


def _limitations(state) -> str:
    return " | ".join(state["outcome"].limitations)


def _item(item_id: str, status: WorkItemStatus, seq: int = 0, **extra) -> WorkItem:
    return WorkItem(id=item_id, root_task_id="task-0000000000000001",
                    request_id=f"req-{item_id[-16:]}", status=status, created_seq=seq, **extra)


def _event(kind: str, seconds: int, interaction_id: str | None) -> RunEvent:
    refs = {"interaction_id": interaction_id} if interaction_id else {}
    return RunEvent(seq=0, run_id="run-1", kind=kind, at=T0 + timedelta(seconds=seconds),
                    refs=refs)


class TestStableDuplicateKeys(unittest.TestCase):
    """Wording tricks that do not change the need must not change the duplicate key."""

    def key(self, question: str) -> str:
        return request_dedup_key(proposal("prior_decisions", question), None)

    def test_width_case_and_compatibility_variants_keep_the_key(self) -> None:
        variants = ["Which store does the cache use?", "WHICH STORE DOES THE CACHE USE?",
                    "Ｗｈｉｃｈ　ｓｔｏｒｅ　does the cache use？",
                    "which  store, does... the cache use"]
        self.assertEqual({self.key(v) for v in variants}, {self.key(QUESTION)})

    def test_unicode_case_folding_is_applied(self) -> None:
        self.assertEqual(normalize_text("Straße"), normalize_text("STRASSE"))

    def test_a_different_need_still_changes_the_key(self) -> None:
        self.assertNotEqual(self.key(QUESTION), self.key("Which queue does the cache use?"))


class TestCycleSafety(unittest.TestCase):
    """Walks over origin and dependency links terminate even on corrupt cyclic data."""

    def test_ancestor_walk_stops_on_a_parent_loop(self) -> None:
        items = {i: _item(f"work-000000000000000{i}", WorkItemStatus.READY) for i in "12"}
        a, b = items["1"].id, items["2"].id
        by_id = {a: items["1"], b: items["2"]}
        self.assertEqual(ancestor_ids(by_id, {a: b, b: a}, a), [a, b])

    def test_reaches_follows_children_and_dependencies_and_stops_on_loops(self) -> None:
        a = _item("work-0000000000000001", WorkItemStatus.WAITING,
                  child_ids=["work-0000000000000002"])
        b = _item("work-0000000000000002", WorkItemStatus.WAITING,
                  dependency_ids=["work-0000000000000003"])
        c = _item("work-0000000000000003", WorkItemStatus.WAITING,
                  child_ids=["work-0000000000000002"])  # b <-> c loop
        items = {i.id: i for i in (a, b, c)}
        self.assertTrue(reaches(items, a.id, c.id))
        self.assertFalse(reaches(items, c.id, a.id))


class TestRunLevelCaps(unittest.TestCase):
    """Jev-call and host-operation caps trip as run guards when accounting passes the limit."""

    def setUp(self) -> None:
        self.limits = load_kernel_config().limits.model_copy(update={
            "max_jev_calls": 3, "max_host_operations": 2})

    def trip(self, **budget):
        return check_run_guards(Budgets(**budget), self.limits, max_iterations=99,
                                queue_empty=False, cancelled=False)

    def test_at_the_limit_nothing_trips_and_beyond_it_the_cap_does(self) -> None:
        self.assertIsNone(self.trip(jev_calls=3, host_operations=2))
        self.assertEqual(self.trip(jev_calls=4).guard, "max_jev_calls")
        self.assertEqual(self.trip(host_operations=3).guard, "max_host_operations")

    def test_host_operations_available_never_goes_negative(self) -> None:
        self.assertEqual(host_operations_available(Budgets(host_operations=1), self.limits), 1)
        self.assertEqual(host_operations_available(Budgets(host_operations=9), self.limits), 0)

    def test_cancellation_outranks_every_other_guard(self) -> None:
        trip = check_run_guards(Budgets(jev_calls=9), self.limits, max_iterations=99,
                                queue_empty=True, cancelled=True)
        self.assertEqual(narrow(trip).guard, "cancelled")


class TestWaitingTime(unittest.TestCase):
    """Human and host wait is measured from events, apart from the active-time budget."""

    def test_open_to_answer_intervals_are_summed_per_interaction(self) -> None:
        events = [_event("interaction.opened", 0, "int-a"), _event("run.started", 1, None),
                  _event("interaction.opened", 5, "int-b"),
                  _event("interaction.answered", 30, "int-a"),
                  _event("interaction.repair_exhausted", 65, "int-b")]
        self.assertEqual(waiting_seconds(events), 30 + 60)

    def test_a_still_open_interaction_is_not_counted(self) -> None:
        self.assertEqual(waiting_seconds([_event("interaction.opened", 0, "int-a")]), 0.0)


class TestUnresolvedWork(unittest.TestCase):
    """The helper that names what a tripped guard left unfinished."""

    def test_only_open_non_root_items_are_listed_in_presentation_order(self) -> None:
        items = {i.id: i for i in (
            _item("work-0000000000000001", WorkItemStatus.WAITING, 0),
            _item("work-0000000000000003", WorkItemStatus.READY, 2),
            _item("work-0000000000000002", WorkItemStatus.DISPATCHED, 1),
            _item("work-0000000000000004", WorkItemStatus.COMPLETED, 3))}
        self.assertEqual(unresolved_item_ids(items, "work-0000000000000001"),
                         ["work-0000000000000002", "work-0000000000000003"])

    def test_the_limitation_names_the_guard_and_a_bounded_goal(self) -> None:
        text = unresolved_text("max_active_seconds", "line one\nline two " + "x" * 300)
        self.assertTrue(text.startswith("unresolved_at_max_active_seconds: line one line two"))
        self.assertLess(len(text), 200)
        self.assertIn("unnamed request", unresolved_text("deadlock", None))


class TestRepeatedQuestionEndsBounded(unittest.IsolatedAsyncioTestCase):
    """A repeated question with no new information ends partial or blocked, never looping."""

    async def test_unicode_reworded_repeats_are_linked_and_end_blocked_with_diagnostics(self
                                                                                         ) -> None:
        wordings = itertools.cycle(["Which store does the cache use?",
                                    "ＷＨＩＣＨ store does the cache use？",
                                    "which STORE, does the cache use"])
        rig = _rig(lambda inv: waiting(inv, proposal("prior_decisions", next(wordings))),
                   no_progress_limit=2)
        _, _, state = await rig.start()
        self.assertEqual(state["outcome"].status, RunStatus.BLOCKED)
        self.assertIn("no_progress", _limitations(state))
        self.assertEqual(len(state["work_items"]), 2)  # reworded repeats were linked, not new
        self.assertLessEqual(len(rig.executors["decide.root"].invocations), 3)
        self.assertEqual(len(rig.executors["retrieve.test"].invocations), 1)


class TestTripsNameUnresolvedWork(unittest.IsolatedAsyncioTestCase):
    """Every guard trip ends open work visibly and yields a partial or blocked envelope."""

    def two_children(self, **limits) -> Rig:
        return _rig(two_phase(lambda inv: waiting(
            inv, proposal("prior_decisions", QUESTION),
            proposal("internal_principles", "Which principles apply?")), completed),
            max_concurrent_native=1, **limits)

    async def test_iteration_limit_blocks_the_unfinished_child_and_reports_partial(self) -> None:
        rig = self.two_children()
        rig.max_iterations = 2
        _, _, state = await rig.start()
        outcome = state["outcome"]
        self.assertEqual(outcome.status, RunStatus.PARTIAL)  # one child delivered
        self.assertIn("guard: max_scheduler_iterations", outcome.diagnostics)
        open_children = [i for i in state["work_items"].values()
                         if i.id != state["task"].root_work_item_id
                         and i.status is WorkItemStatus.BLOCKED]
        self.assertEqual(len(open_children), 1)
        self.assertIn("unresolved_at_max_scheduler_iterations", _limitations(state))
        self.assertEqual(state["interaction_queue"], [])

    async def test_cancellation_cancels_children_instead_of_blocking_them(self) -> None:
        rig = self.two_children()
        rig.cancel = lambda: len(rig.executors["retrieve.test"].invocations) >= 1
        _, _, state = await rig.start()
        self.assertEqual(state["outcome"].status, RunStatus.CANCELLED)
        statuses = [i.status for i in state["work_items"].values()]
        self.assertIn(WorkItemStatus.CANCELLED, statuses)
        self.assertNotIn(WorkItemStatus.BLOCKED, statuses)
        self.assertNotIn(WorkItemStatus.READY, statuses)

    async def test_a_run_level_cap_trip_ends_the_run_with_the_unresolved_child(self) -> None:
        rig = _rig(two_phase(lambda inv: waiting(inv, proposal()), completed))
        _, _, done = await rig.start()
        root_id = done["task"].root_work_item_id
        child = next(i for i in done["work_items"].values() if i.id != root_id)
        reopened = child.model_copy(update={"status": WorkItemStatus.READY, "result_ref": None})
        stuck_root = done["work_items"][root_id].model_copy(update={
            "status": WorkItemStatus.WAITING, "continuation": {
                "capability_id": "decide.root", "capability_version": "1.0.0", "state": {},
                "resume_reason": "children_done"}})
        state: Any = {**done, "work_items": {root_id: stuck_root, child.id: reopened},
                 "budgets": Budgets(jev_calls=99), "interaction_queue": [], "outcome": None,
                 "halt_reason": None}
        runtime: Any = types.SimpleNamespace(context=rig.runtime())
        update: Any = await schedule(state, runtime)
        self.assertEqual(update["halt_reason"], "max_jev_calls")
        merged: Any = {**state, **update, "work_items": {**state["work_items"],
                                                    **update["work_items"]}}
        self.assertEqual(merged["work_items"][child.id].status, WorkItemStatus.BLOCKED)
        outcome = decide_outcome(merged)
        self.assertIn(outcome.status, (RunStatus.PARTIAL, RunStatus.BLOCKED))
        self.assertIn("guard: max_jev_calls", outcome.diagnostics)
        self.assertIn("unresolved_at_max_jev_calls", " | ".join(outcome.limitations))


class _Slow:
    """Executor slower than the per-call timeout."""

    def __init__(self) -> None:
        self.invocations: list = []

    async def ainvoke(self, invocation, ctx):
        self.invocations.append(invocation)
        await asyncio.sleep(5)


class TestPerCallTimeoutAndActiveTime(unittest.IsolatedAsyncioTestCase):
    """A hung capability is cut off per call; human wait is never active time."""

    async def test_a_call_over_the_timeout_fails_as_timeout_and_retries_are_bounded(self) -> None:
        rig = _rig(completed, capability_timeout_seconds=0.05, max_retries=1)
        slow = rig.bind("decide.root", _Slow())
        _, _, state = await rig.start()
        self.assertEqual(len(slow.invocations), 2)  # first attempt plus one retry
        self.assertEqual(state["outcome"].status, RunStatus.FAILED)
        self.assertEqual(state["outcome"].errors[0].code, "timeout")

    async def test_host_wait_is_measured_from_events_and_adds_no_active_time(self) -> None:
        rig = host_rig()
        rig.monotonic = lambda: 0.0  # nodes take no time; any charged wait would show up
        ticks = itertools.count()
        rig.runtime_wrap = lambda runtime: replace(runtime, clock=lambda: T0 + timedelta(
            minutes=next(ticks)))
        run = await start(rig)
        self.assertEqual(run.state["budgets"].active_seconds, 0.0)
        result = await run.submit(raw_submission(run.packet, run.run_id))
        self.assertEqual(result.state["outcome"].status, RunStatus.COMPLETED)
        self.assertEqual(result.state["budgets"].active_seconds, 0.0)
        self.assertGreaterEqual(waiting_seconds(result.state["events"]), 60.0)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 15:00 [python-coder]: The run-level cap trip is driven by calling `schedule` on a
#   reopened state (as the deadlock test does): the per-route checks make an overspend
#   unreachable through the graph, so the safety net can only be exercised directly.
#   (#KernelBootstrapV0/P9)
# ====================================================================
