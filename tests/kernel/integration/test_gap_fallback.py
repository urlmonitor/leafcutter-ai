"""
MODULE: tests.kernel.integration.test_gap_fallback
GOAL: Test the true-capability-gap scenario with an approved host fallback end to end:
    NO_CAPABILITY -> gap -> bounded host fallback -> host answer -> merge, the fallback outcome
    on the stored gap, deduplication across runs and template-authored drafts.
BUSINESS CONTEXT: A request no native capability serves must still finish through an approved
    generic host operation when config allows it, and the unmet need must be recorded once per
    distinct need with its fallback outcome so the backlog learns what to build (Rev 3 sections
    14 and 16, ADR-056).
ARCHITECTURE: Real compiled graph and the real ledgered submission entry point over the scheduler
    Rig (memory stores, scripted executors); the host is a fake responder that answers the packet
    the kernel delivers. The pending fallback gap lives in state until its outcome is known.
"""

from __future__ import annotations

import unittest
from dataclasses import replace

from kernel.contracts import (
    FallbackOutcome,
    GapType,
    RunEvent,
    RunStatus,
    WorkItem,
    WorkItemStatus,
    schema_ids,
)
from kernel.interaction import SubmitStatus
from kernel.persistence.memory import MemoryGapStore
from kernel.scheduler.nodes_gaps import fallback_outcome_of, record_host_only
from tests.kernel.interaction.support import BUNDLE, Started, raw_submission, start
from tests.kernel.scheduler.support import (
    Rig,
    completed,
    descriptor,
    proposal,
    retrieval_descriptor,
    two_phase,
    waiting,
)

QUESTION = "Which store does the cache use?"
OTHER_WORDING = "Cache store: which does the cache use?"
BAD = {"evidence_ids": "not-a-list"}


def host_research(**extra: object):
    """Return the approved generic host research descriptor (bounded_research)."""
    return descriptor("host.research", kinds=("evidence",), mode="host_handoff",
                      accepts=schema_ids.RETRIEVAL_REQUEST, produces=schema_ids.EVIDENCE_BUNDLE,
                      operations=("bounded_research",), **extra)


def fallback_rig(question: str = QUESTION) -> Rig:
    """Return a rig whose root asks for evidence that no registered capability can serve.

    The child names the operation `retrieve`, which only `host.research` could be argued to
    cover, but its own operation is `bounded_research`: routing finds no match (a true gap) and
    the host capability is reachable only as a bounded fallback.
    """
    rig = Rig([descriptor("decide.root"), host_research()])
    rig.bind("decide.root", factory=two_phase(
        lambda inv: waiting(inv, proposal("prior_decisions", question, operation="retrieve")),
        completed))
    rig.bind("host.research")
    return rig


def fallback_items(state: dict) -> list:
    """Return the work items that were rebound to the host research fallback."""
    return [i for i in state["work_items"].values()
            if i.binding and i.binding.capability_id == "host.research"]


class TestFallbackHappyPath(unittest.IsolatedAsyncioTestCase):
    """NO_CAPABILITY -> gap -> fallback -> host answer -> merge."""

    async def test_unsupported_request_is_rebound_to_the_host_and_the_run_completes(self) -> None:
        rig = fallback_rig()
        run = await start(rig)
        self.assertEqual(run.packet["operation"], "bounded_research")
        (item,) = fallback_items(run.state)
        self.assertEqual(item.status, WorkItemStatus.WAITING)
        self.assertEqual(run.state["budgets"].host_operations, 1)
        self.assertEqual(rig.gap_store.observations, [])  # stored once, when the outcome is known
        (pending,) = run.state["gaps"].values()
        self.assertEqual((pending.gap_type, pending.fallback_outcome),
                         (GapType.UNSUPPORTED, FallbackOutcome.NONE))
        result = await run.submit(raw_submission(run.packet, run.run_id))
        self.assertEqual(result.status, SubmitStatus.ACCEPTED)
        self.assertEqual(result.state["outcome"].status, RunStatus.COMPLETED)
        self.assertEqual(result.state["work_items"][item.id].status, WorkItemStatus.COMPLETED)

    async def test_the_gap_is_stored_once_with_its_fallback_outcome_and_a_template_draft(self
                                                                                          ) -> None:
        rig = fallback_rig()
        run = await start(rig)
        result = await run.submit(raw_submission(run.packet, run.run_id))
        (gap,) = rig.gap_store.observations
        self.assertEqual(gap.gap_type, GapType.UNSUPPORTED)
        self.assertEqual(gap.fallback_outcome, FallbackOutcome.HOST_COMPLETED)
        self.assertEqual(gap.example_run_ids, [run.run_id])
        self.assertEqual(gap.normalized_need, "prior_decisions")
        self.assertEqual(gap.output_schema, schema_ids.EVIDENCE_BUNDLE)
        self.assertEqual(gap.missing_native_capability, "native implementation of host.research")
        self.assertEqual(gap.proposal.author, "template")
        draft = rig.gap_store.drafts[gap.proposal.draft_ref]
        self.assertIn("Author: template", draft)
        self.assertIn("NOT a registry entry", draft)
        self.assertIn(gap.gap_key, draft)
        kinds = [e.kind for e in result.state["events"]]
        self.assertEqual(kinds.count("gap.fallback_started"), 1)
        self.assertEqual(kinds.count("gap.recorded"), 1)
        self.assertEqual(result.state["gaps"][gap.id].fallback_outcome,
                         FallbackOutcome.HOST_COMPLETED)

    async def test_the_same_need_in_two_runs_is_one_gap_with_two_occurrences(self) -> None:
        rig = fallback_rig()
        run_ids = []
        for question in (QUESTION, OTHER_WORDING):
            run = await start(rig, goal=f"Decide: {question}")
            await run.submit(raw_submission(run.packet, run.run_id))
            run_ids.append(run.run_id)
        self.assertEqual(len(rig.gap_store.observations), 2)
        (aggregated,) = rig.gap_store.load_gaps()
        self.assertEqual(aggregated.occurrence_count, 2)
        self.assertEqual(aggregated.example_run_ids, run_ids)
        self.assertIn("Occurrences: 2", rig.gap_store.drafts[aggregated.proposal.draft_ref])

    async def test_the_fallback_uses_the_host_operation_budget(self) -> None:
        rig = fallback_rig()
        run = await start(rig)
        host_ops = [e for e in run.state["events"] if e.kind == "gap.fallback_started"]
        self.assertEqual([e.detail for e in host_ops], ["host.research"])
        self.assertEqual(run.state["budgets"].host_operations, 1)


class TestFallbackFailure(unittest.IsolatedAsyncioTestCase):
    """A failed host fallback leaves the gap a build opportunity with outcome host_failed."""

    async def test_exhausted_repairs_record_host_failed_and_block_the_parent(self) -> None:
        rig = fallback_rig()
        host = rig.config.host.model_copy(update={"max_repair_attempts": 0})
        rig.config = rig.config.model_copy(update={"host": host})
        run = await start(rig)
        result = await run.submit(raw_submission(run.packet, run.run_id, response=BAD))
        self.assertEqual(result.status, SubmitStatus.REPAIR_EXHAUSTED)
        self.assertEqual(result.state["outcome"].status, RunStatus.BLOCKED)
        (gap,) = rig.gap_store.observations
        self.assertEqual((gap.gap_type, gap.fallback_outcome),
                         (GapType.UNSUPPORTED, FallbackOutcome.HOST_FAILED))
        self.assertIsNotNone(gap.proposal)


class TestHostOnly(unittest.IsolatedAsyncioTestCase):
    """A routed host operation with no native counterpart records a host_only observation."""

    async def host_run(self, rig: Rig) -> tuple[Started, dict]:
        run = await start(rig)
        result = await run.submit(raw_submission(run.packet, run.run_id, response=dict(BUNDLE)))
        return run, result.state

    async def test_a_selected_host_operation_without_a_native_twin_is_host_only(self) -> None:
        rig = Rig([descriptor("decide.root"), host_research()])
        rig.bind("decide.root", factory=two_phase(
            lambda inv: waiting(inv, proposal(operation="bounded_research")), completed))
        rig.bind("host.research")
        _, state = await self.host_run(rig)
        (gap,) = rig.gap_store.observations
        self.assertEqual((gap.gap_type, gap.fallback_outcome),
                         (GapType.HOST_ONLY, FallbackOutcome.HOST_COMPLETED))
        self.assertIsNotNone(gap.proposal)  # host_only is a build opportunity
        self.assertEqual(state["outcome"].status, RunStatus.COMPLETED)

    async def test_a_host_operation_with_a_native_twin_is_recorded_without_a_draft(self) -> None:
        rig = Rig([descriptor("decide.root"), host_research(), retrieval_descriptor()])
        rig.bind("decide.root", factory=two_phase(
            lambda inv: waiting(inv, proposal(operation="bounded_research")), completed))
        rig.bind("host.research")
        await self.host_run(rig)
        (gap,) = rig.gap_store.observations
        self.assertEqual(gap.gap_type, GapType.HOST_ONLY)
        self.assertIn("native alternatives", gap.why_insufficient)
        self.assertIn("retrieve.test", gap.why_insufficient)
        self.assertIsNone(gap.proposal)  # nothing to build: a native capability exists
        self.assertEqual(rig.gap_store.drafts, {})


class TestRecordHostOnly(unittest.IsolatedAsyncioTestCase):
    """The public `record_host_only` the interaction node calls for every executed host op."""

    async def finished(self) -> tuple[Rig, Started, dict, object]:
        rig = Rig([descriptor("decide.root"), host_research()])
        rig.bind("decide.root", factory=two_phase(
            lambda inv: waiting(inv, proposal(operation="bounded_research")), completed))
        rig.bind("host.research")
        run = await start(rig)
        state = (await run.submit(raw_submission(run.packet, run.run_id))).state
        (item,) = fallback_items(state)
        return rig, run, state, item

    async def test_it_records_with_the_same_gap_key_and_aggregates_with_the_graph_record(self
                                                                                          ) -> None:
        rig, run, state, item = await self.finished()
        (from_graph,) = rig.gap_store.observations
        before = {**state, "events": [e for e in state["events"] if e.kind != "gap.recorded"]}
        second_attempt = item.model_copy(update={"attempts": item.attempts + 1})
        gap, events = record_host_only(before, run.context, second_attempt,
                                       FallbackOutcome.HOST_COMPLETED)
        self.assertEqual(gap.gap_key, from_graph.gap_key)
        self.assertEqual([e.kind for e in events], ["gap.recorded"])
        self.assertEqual(events[0].refs, {"work_item_id": item.id, "gap_id": gap.id})
        (aggregated,) = rig.gap_store.load_gaps()
        self.assertEqual(aggregated.occurrence_count, 2)  # counted with the graph's own record
        self.assertEqual(aggregated.gap_type, GapType.HOST_ONLY)

    async def test_the_outcome_is_carried_and_a_draft_is_written_when_nothing_native_exists(self
                                                                                             ) -> None:
        rig, run, state, item = await self.finished()
        gap, _ = record_host_only(state, run.context, item, FallbackOutcome.HOST_FAILED)
        self.assertEqual(gap.fallback_outcome, FallbackOutcome.HOST_FAILED)
        self.assertEqual(gap.missing_native_capability, "native implementation of host.research")
        self.assertIn(gap.proposal.draft_ref, rig.gap_store.drafts)

    async def test_a_store_failure_is_reported_in_events_and_never_raised(self) -> None:
        rig, run, state, item = await self.finished()

        class Broken(MemoryGapStore):
            def record(self, gap):
                raise OSError("disk full")

        context = replace(run.context, gap_store=Broken())
        gap, events = record_host_only(state, context, item, FallbackOutcome.HOST_COMPLETED)
        self.assertEqual([e.kind for e in events], ["gap.recorded", "gap.record_failed"])
        self.assertEqual(gap.gap_type, GapType.HOST_ONLY)  # the gap object is still returned

    async def test_fallback_human_and_unbound_items_are_skipped(self) -> None:
        rig, run, state, item = await self.finished()
        started = RunEvent(seq=0, run_id=run.run_id, kind="gap.fallback_started",
                           at=run.context.clock(), refs={"work_item_id": item.id})
        fallback_state = {**state, "events": [*state["events"], started]}
        self.assertIsNone(record_host_only(fallback_state, run.context, item,
                                           FallbackOutcome.HOST_COMPLETED))
        human = item.model_copy(update={"binding": item.binding.model_copy(update={
            "capability_id": "kernel.human"})})
        self.assertIsNone(record_host_only(state, run.context, human,
                                           FallbackOutcome.HOST_COMPLETED))
        native = item.model_copy(update={"binding": None})
        self.assertIsNone(record_host_only(state, run.context, native,
                                           FallbackOutcome.HOST_COMPLETED))


class TestOutcomeMapping(unittest.TestCase):
    """The pure mapping from an item's state to the fallback outcome."""

    def test_done_failed_and_open_items_map_to_their_outcomes(self) -> None:
        cases = [(WorkItemStatus.COMPLETED, False, FallbackOutcome.HOST_COMPLETED),
                 (WorkItemStatus.PARTIAL, False, FallbackOutcome.HOST_COMPLETED),
                 (WorkItemStatus.FAILED, False, FallbackOutcome.HOST_FAILED),
                 (WorkItemStatus.CANCELLED, False, FallbackOutcome.HOST_FAILED),
                 (WorkItemStatus.WAITING, False, None),
                 (WorkItemStatus.WAITING, True, FallbackOutcome.NONE)]
        for status, halting, expected in cases:
            with self.subTest(status=status, halting=halting):
                self.assertEqual(fallback_outcome_of(bare_item(status), halting), expected)


def bare_item(status: WorkItemStatus) -> WorkItem:
    """Return a bare WorkItem with the given status."""
    return WorkItem(id="work-0000000000000001", root_task_id="task-0000000000000001",
                    request_id="req-0000000000000001", status=status)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 20:00 [python-coder]: The aggregation test records a second attempt of the item:
#   observation ids are now deterministic per attempt, so re-recording the same attempt is a
#   re-execution and counts once. (#KernelBootstrapV0/FIXB)
# - 2026-10-01 14:30 [python-coder]: The fallback child names operation `retrieve` so routing
#   finds no match while `host.research` stays reachable as a fallback by kind and output
#   schema; this is the smallest registry that reproduces a true gap with an approved host
#   operation. (#KernelBootstrapV0/P9)
# ====================================================================
