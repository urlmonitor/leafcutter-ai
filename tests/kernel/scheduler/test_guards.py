"""
MODULE: tests.kernel.scheduler.test_guards
GOAL: Test every guard end to end: work-item cap, dependency depth, duplicate and cycle
    detection, transient-only retries, no-progress (item and run level), scheduler iterations,
    active time, cancellation and the host-operation limit.
BUSINESS CONTEXT: A run must end as a partial or blocked envelope with diagnostics and never
    loop (Rev 3 sections 8.4 and 13.2); rewording a question must not reset the no-progress
    guard.
ARCHITECTURE: Guards are pure functions (unit-tested for the dedup key) but their contract is the
    run's observable outcome, so the tests drive the compiled graph and assert the outcome,
    diagnostics and how many times capabilities actually ran.
"""

from __future__ import annotations

import itertools
import types
import unittest

from kernel.config import load_kernel_config
from kernel.contracts import RequestKind, RequestProposal, RunStatus, schema_ids
from kernel.scheduler import decide_outcome
from kernel.scheduler.guards import normalize_text, request_dedup_key
from kernel.scheduler.nodes_schedule import after_schedule, schedule
from tests.kernel.helpers import make_request_body
from tests.kernel.scheduler.support import (
    Rig,
    completed,
    descriptor,
    failed,
    proposal,
    retrieval_descriptor,
    two_phase,
    waiting,
    with_limits,
)

QUESTION = "Which store does the cache use?"
REWORDED = "Cache store: which does the cache use?"


def _rig(root_factory, child_factory=None, **limits) -> Rig:
    rig = Rig([descriptor("decide.root"), retrieval_descriptor()])
    rig.bind("decide.root", factory=root_factory)
    rig.bind("retrieve.test", factory=child_factory or (
        lambda inv: completed(inv, schema_ids.EVIDENCE_BUNDLE)))
    rig.config = with_limits(load_kernel_config(), **limits)
    return rig


def _limitations(state) -> str:
    return " | ".join(state["outcome"].limitations)


class TestDedupKey(unittest.TestCase):
    """Rewording must not change the duplicate key; a different need must."""

    def _key(self, question: str, category: str = "prior_decisions") -> str:
        return request_dedup_key(proposal(category, question), None)

    def test_rewording_keeps_the_key(self) -> None:
        self.assertEqual(self._key(QUESTION), self._key(REWORDED))
        self.assertEqual(normalize_text("  The Cache, STORE?! "), "cache store")

    def test_a_different_category_or_question_changes_the_key(self) -> None:
        self.assertNotEqual(self._key(QUESTION), self._key(QUESTION, "internal_principles"))
        self.assertNotEqual(self._key(QUESTION), self._key("Which queue is used?"))

    def test_scope_revision_changes_the_key(self) -> None:
        body = make_request_body()
        self.assertNotEqual(request_dedup_key(body, None),
                            request_dedup_key(body, {"commit": "abc", "dirty": False}))


class TestCaps(unittest.IsolatedAsyncioTestCase):
    """Work-item cap and depth."""

    async def test_work_item_cap_rejects_the_proposals_and_blocks_the_parent(self) -> None:
        rig = _rig(lambda inv: waiting(inv, proposal("prior_decisions", QUESTION),
                                       proposal("internal_principles", "Which principles apply?")),
                   max_work_items=2)
        _, _, state = await rig.start()
        self.assertEqual(state["outcome"].status, RunStatus.BLOCKED)
        self.assertIn("work_item_cap", _limitations(state))
        self.assertEqual(len(state["work_items"]), 1)
        self.assertIn("guard.tripped", [e.kind for e in state["events"]])

    async def test_depth_limit_rejects_a_grandchild(self) -> None:
        def child_factory(inv):
            return waiting(inv, proposal("existing_patterns", "Which patterns exist?"))

        rig = _rig(two_phase(lambda inv: waiting(inv, proposal()), completed), child_factory,
                   max_depth=1)
        _, _, state = await rig.start()
        self.assertIn("max_depth", _limitations(state))
        self.assertEqual(state["outcome"].status, RunStatus.BLOCKED)
        self.assertEqual(len(state["work_items"]), 2)


class TestCycles(unittest.IsolatedAsyncioTestCase):
    """A dependency that would form a cycle is rejected and the parent is blocked."""

    async def test_proposal_equivalent_to_the_root_request_is_a_cycle(self) -> None:
        def again(inv):
            body = RequestProposal(
                kind=RequestKind.CAPABILITY, goal="Decide the cache store",
                payload_schema=schema_ids.GOAL_REQUEST,
                payload={"goal": "Decide the cache store"},
                requested_output_schema=schema_ids.DECISION_REPORT)
            return waiting(inv, body)

        rig = _rig(again)
        _, _, state = await rig.start()
        self.assertEqual(state["outcome"].status, RunStatus.BLOCKED)
        self.assertIn("cycle", _limitations(state))
        self.assertEqual(len(state["work_items"]), 1)

    async def test_dependency_on_the_proposing_item_is_a_cycle(self) -> None:
        def depends_on_self(inv):
            return waiting(inv, proposal(depends_on=[inv.work_item_id]))

        _, _, state = await _rig(depends_on_self).start()
        self.assertEqual(state["outcome"].status, RunStatus.BLOCKED)
        self.assertIn("cycle", _limitations(state))

    async def test_unknown_dependency_is_rejected(self) -> None:
        _, _, state = await _rig(lambda inv: waiting(
            inv, proposal(depends_on=["work-0000000000000099"]))).start()
        self.assertIn("unknown_dependency", _limitations(state))


class TestRetries(unittest.IsolatedAsyncioTestCase):
    """Only transient failures are retried, with the same binding, up to max_retries."""

    async def test_transient_failure_is_retried_then_succeeds(self) -> None:
        calls = itertools.count(1)
        rig = _rig(lambda inv: (failed(inv, "timeout", retryable=True) if next(calls) < 3
                                else completed(inv)), max_retries=2)
        _, _, state = await rig.start()
        self.assertEqual(state["outcome"].status, RunStatus.COMPLETED)
        self.assertEqual(len(rig.executors["decide.root"].invocations), 3)
        self.assertEqual(state["budgets"].retries, {state["task"].root_work_item_id: 2})

    async def test_retries_stop_at_the_configured_limit(self) -> None:
        rig = _rig(lambda inv: failed(inv, "timeout", retryable=True), max_retries=1)
        _, _, state = await rig.start()
        self.assertEqual(state["outcome"].status, RunStatus.FAILED)
        self.assertEqual(len(rig.executors["decide.root"].invocations), 2)

    async def test_a_permanent_failure_is_never_retried(self) -> None:
        rig = _rig(lambda inv: failed(inv, "bad_input"), max_retries=5)
        _, _, state = await rig.start()
        self.assertEqual(len(rig.executors["decide.root"].invocations), 1)
        self.assertEqual(state["outcome"].errors[0].code, "bad_input")


class TestNoProgress(unittest.IsolatedAsyncioTestCase):
    """The same question with unchanged inputs is not progress, however it is worded."""

    async def test_reworded_repeat_is_blocked_after_the_limit(self) -> None:
        questions = itertools.cycle([QUESTION, REWORDED, "Which store is used by the cache?"])

        def always_asks(inv):
            return waiting(inv, proposal("prior_decisions", next(questions)),
                           state={"n": inv.attempt})

        rig = _rig(always_asks, no_progress_limit=2)
        _, _, state = await rig.start()
        root_calls = len(rig.executors["decide.root"].invocations)
        self.assertEqual(root_calls, 3, "attempts 1 and 2 are allowed, the third is blocked")
        self.assertEqual(len(rig.executors["retrieve.test"].invocations), 1)
        self.assertEqual(state["outcome"].status, RunStatus.BLOCKED)
        self.assertIn("no_progress", _limitations(state))

    async def test_new_evidence_resets_the_fingerprint(self) -> None:
        from tests.kernel.helpers import make_evidence

        counter = itertools.count()

        def child(inv):
            ev = make_evidence(f"docs/{next(counter)}.md#L1-L2", f"Fresh excerpt {next(counter)}.")
            bundle = {"evidence": [ev.model_dump(mode="json")], "findings": [],
                      "evidence_ids": [ev.id]}
            return completed(inv, schema_ids.EVIDENCE_BUNDLE, bundle)

        rounds = itertools.count(1)

        def root(inv):
            n = next(rounds)
            if n > 3:
                return completed(inv)
            return waiting(inv, proposal("prior_decisions", f"Question number {n}?"))

        rig = _rig(root, child, no_progress_limit=1)
        _, _, state = await rig.start()
        self.assertEqual(state["outcome"].status, RunStatus.COMPLETED)

    async def test_passes_without_progress_across_items_halt_the_run(self) -> None:
        calls = itertools.count(1)

        def root(inv):
            step = next(calls)
            if step == 1:
                return waiting(inv, proposal("prior_decisions", QUESTION), state={"n": 1})
            return waiting(inv, proposal("internal_principles", "Which principles apply?"),
                           proposal("existing_patterns", "Which patterns exist?"), state={"n": 2})

        def child(inv):
            category = inv.input_payload["need"]["category"]
            if category == "prior_decisions":
                return completed(inv, schema_ids.EVIDENCE_BUNDLE)
            return waiting(inv, proposal("prior_decisions", REWORDED), state={"n": inv.attempt})

        rig = _rig(root, child, no_progress_limit=2)
        _, _, state = await rig.start()
        self.assertEqual(state["outcome"].status, RunStatus.PARTIAL)
        self.assertIn("guard: no_progress", state["outcome"].diagnostics)
        self.assertEqual(state["budgets"].no_progress_streak, 2)
        self.assertEqual(len(rig.executors["retrieve.test"].invocations), 5)


class _Reserving:
    """Executor that tries to reserve two Jev calls and records what it was granted."""

    def __init__(self) -> None:
        self.granted: list[list[bool]] = []
        self.invocations: list = []

    async def ainvoke(self, invocation, ctx):
        self.invocations.append(invocation)
        self.granted.append([ctx.budget.reserve("jev"), ctx.budget.reserve("jev")])
        return completed(invocation, schema_ids.EVIDENCE_BUNDLE)


class TestWorkerBudgets(unittest.IsolatedAsyncioTestCase):
    """Parallel workers split the remaining Jev budget and can never overspend it."""

    async def test_workers_share_the_remaining_jev_budget(self) -> None:
        rig = _rig(two_phase(lambda inv: waiting(
            inv, proposal("prior_decisions", QUESTION),
            proposal("internal_principles", "Which principles apply?")), completed),
            max_jev_calls=3)
        reserving = rig.bind("retrieve.test", _Reserving())
        _, _, state = await rig.start()
        self.assertEqual(reserving.granted, [[True, False], [True, False]])
        self.assertEqual(state["budgets"].jev_calls, 2)
        self.assertEqual(state["outcome"].status, RunStatus.COMPLETED)


class TestRunLimits(unittest.IsolatedAsyncioTestCase):
    """Scheduler iterations, active time and cancellation stop the run with diagnostics."""

    async def test_scheduler_iteration_limit_stops_the_run(self) -> None:
        rig = _rig(lambda inv: failed(inv, "timeout", retryable=True), max_retries=50,
                   no_progress_limit=50)
        rig.max_iterations = 3
        _, _, state = await rig.start()
        self.assertIn("guard: max_scheduler_iterations", state["outcome"].diagnostics)
        self.assertEqual(state["outcome"].status, RunStatus.BLOCKED)
        self.assertLessEqual(len(rig.executors["decide.root"].invocations), 3)

    async def test_active_time_limit_stops_the_run(self) -> None:
        rig = _rig(lambda inv: failed(inv, "timeout", retryable=True), max_retries=50,
                   no_progress_limit=50, max_active_seconds=1000)
        ticks = itertools.count(step=400)
        rig.monotonic = lambda: float(next(ticks))
        _, _, state = await rig.start()
        self.assertIn("guard: max_active_seconds", state["outcome"].diagnostics)
        self.assertGreaterEqual(state["budgets"].active_seconds, 1000)

    async def test_deadlock_halts_with_a_diagnostic_instead_of_spinning(self) -> None:
        rig = _rig(completed)
        _, _, done = await rig.start()
        root_id = done["task"].root_work_item_id
        stuck = done["work_items"][root_id].model_copy(update={
            "status": "waiting", "continuation": {
                "capability_id": "decide.root", "capability_version": "1.0.0", "state": {},
                "resume_reason": "children_done"}, "child_ids": ["work-0000000000000099"]})
        state = {**done, "work_items": {root_id: stuck}, "interaction_queue": [], "outcome": None}
        update = await schedule(state, types.SimpleNamespace(context=rig.runtime()))
        self.assertEqual(update["halt_reason"], "deadlock")
        self.assertEqual(after_schedule({**state, **update}), "finalize")
        outcome = decide_outcome({**state, **update})
        self.assertEqual(outcome.status, RunStatus.BLOCKED)
        self.assertIn("guard: deadlock", outcome.diagnostics)

    async def test_cancellation_ends_the_run_as_cancelled(self) -> None:
        rig = _rig(two_phase(lambda inv: waiting(inv, proposal()), completed))
        rig.cancel = lambda: len(rig.executors["decide.root"].invocations) >= 1
        _, _, state = await rig.start()
        self.assertEqual(state["outcome"].status, RunStatus.CANCELLED)
        self.assertEqual(len(rig.executors["retrieve.test"].invocations), 0)

    async def test_host_operation_limit_makes_host_capabilities_ineligible(self) -> None:
        rig = Rig([descriptor("host.decide", mode="host_handoff")])
        rig.bind("host.decide")
        rig.config = with_limits(rig.config, max_host_operations=0)
        _, _, state = await rig.start()
        self.assertEqual(state["outcome"].status, RunStatus.BLOCKED)
        self.assertIn("budget_exhausted", _limitations(state))
        self.assertEqual(state.get("interaction_queue"), [])
        self.assertEqual(rig.gap_store.observations, [])


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:40 [python-coder]: Run-level guards are exercised with a retryable-failure
#   storm because it is the only loop that makes no progress on any per-item signal.
#   (#KernelBootstrapV0/P4)
# ====================================================================
