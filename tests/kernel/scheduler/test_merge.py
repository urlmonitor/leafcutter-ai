"""
MODULE: tests.kernel.scheduler.test_merge
GOAL: Test the deterministic merge: reducer semantics, evidence deduplication by content
    address, inline bundle items, child creation and the linking of equivalent requests.
BUSINESS CONTEXT: Parallel workers finish in any order and capabilities reword the same need
    (Rev 3 sections 8.1 step 7 and 8.3); the merged state must not depend on timing or wording,
    and equivalent work must be linked rather than run twice.
ARCHITECTURE: Pure reducers are unit-tested directly; every other behaviour runs through the
    compiled graph with scripted executors and is asserted on the final state.
"""

from __future__ import annotations

import unittest

from kernel.contracts import RunStatus, WorkItem, WorkItemStatus, schema_ids
from kernel.scheduler.state import append_events, merge_map, new_event, sum_counts
from tests.kernel.helpers import make_evidence
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
REWORDED = "Cache store: which does the cache use?"


def _bundle(*evidence) -> dict:
    return {"evidence": [e.model_dump(mode="json") for e in evidence], "findings": [],
            "evidence_ids": [e.id for e in evidence]}


def _rig(first, child_factory=None):
    rig = Rig([descriptor("decide.root"), retrieval_descriptor()])
    root = rig.bind("decide.root", factory=two_phase(first, completed))
    child = rig.bind("retrieve.test", factory=child_factory or (
        lambda inv: completed(inv, schema_ids.EVIDENCE_BUNDLE, _bundle())))
    return rig, root, child


def _item(seq: int, revision: int, status: str = "ready") -> WorkItem:
    return WorkItem(id="work-0000000000000001", root_task_id="task-0000000000000001",
                    request_id="req-0000000000000001", created_seq=seq, status=WorkItemStatus(status),
                    updated_revision=revision)


class TestReducers(unittest.TestCase):
    """The state reducers are deterministic."""

    def test_merge_map_orders_keys_and_newer_revision_wins(self) -> None:
        left = {"b": _item(1, revision=3, status="completed")}
        merged = merge_map(left, {"b": _item(1, revision=2), "a": _item(2, revision=0)})
        self.assertEqual(list(merged), ["a", "b"])
        self.assertEqual(merged["b"].status.value, "completed")
        newer = merge_map(left, {"b": _item(1, revision=4, status="failed")})
        self.assertEqual(newer["b"].status.value, "failed")

    def test_events_are_numbered_after_the_existing_ones(self) -> None:
        from datetime import UTC, datetime

        at = datetime.now(UTC)
        first = append_events([], [new_event("run-0000000000000001", at, "a")])
        both = append_events(first, [new_event("run-0000000000000001", at, "b"),
                                     new_event("run-0000000000000001", at, "c")])
        self.assertEqual([(e.seq, e.kind) for e in both], [(0, "a"), (1, "b"), (2, "c")])

    def test_counters_add_per_key(self) -> None:
        self.assertEqual(sum_counts({"x": 1, "y": 2}, {"y": 3, "z": 1}), {"x": 1, "y": 5, "z": 1})


class TestEvidenceMerge(unittest.IsolatedAsyncioTestCase):
    """Evidence is deduplicated by its content address and inline items are merged."""

    async def test_identical_evidence_from_two_children_is_stored_once(self) -> None:
        shared = make_evidence("docs/shared.md#L1-L2", "Shared excerpt.")
        rig, _, _ = _rig(lambda inv: waiting(
            inv, proposal("prior_decisions", QUESTION),
            proposal("internal_principles", "Which principles apply?")),
            lambda inv: completed(inv, schema_ids.EVIDENCE_BUNDLE, _bundle(shared)))
        _, _, state = await rig.start()
        self.assertEqual(list(state["evidence"]), [shared.id])
        self.assertEqual(state["outcome"].status, RunStatus.COMPLETED)

    async def test_inline_bundle_evidence_enters_run_state_in_sorted_order(self) -> None:
        items = [make_evidence(f"docs/{n}.md#L1-L2", f"Excerpt {n}.") for n in "cab"]
        rig, _, _ = _rig(lambda inv: waiting(inv, proposal()),
                         lambda inv: completed(inv, schema_ids.EVIDENCE_BUNDLE, _bundle(*items)))
        _, _, state = await rig.start()
        self.assertEqual(list(state["evidence"]), sorted(e.id for e in items))

    async def test_results_are_kept_in_sorted_invocation_order(self) -> None:
        rig, _, _ = _rig(lambda inv: waiting(inv, proposal()))
        _, _, state = await rig.start()
        self.assertEqual(list(state["results"]), sorted(state["results"]))


class TestChildrenAndDuplicates(unittest.IsolatedAsyncioTestCase):
    """Children are registered once; equivalent requests are linked, not duplicated."""

    async def test_reworded_duplicate_in_one_result_creates_one_child(self) -> None:
        rig, root, child = _rig(lambda inv: waiting(
            inv, proposal("prior_decisions", QUESTION), proposal("prior_decisions", REWORDED)))
        _, _, state = await rig.start()
        self.assertEqual(len(child.invocations), 1)
        self.assertEqual(len(state["work_items"]), 2)
        self.assertEqual(state["budgets"].work_items_created, 2)

    async def test_different_needs_are_not_merged(self) -> None:
        rig, _, child = _rig(lambda inv: waiting(
            inv, proposal("prior_decisions", QUESTION),
            proposal("internal_principles", QUESTION)))
        _, _, state = await rig.start()
        self.assertEqual(len(child.invocations), 2)
        self.assertEqual(len(state["work_items"]), 3)

    async def test_request_equivalent_to_a_completed_one_is_linked_not_rerun(self) -> None:
        def root_factory(inv):
            if inv.continuation is None:
                return waiting(inv, proposal("prior_decisions", QUESTION), state={"n": 1})
            if inv.continuation.state == {"n": 1}:
                return waiting(inv, proposal("prior_decisions", REWORDED), state={"n": 2})
            return completed(inv)

        rig = Rig([descriptor("decide.root"), retrieval_descriptor()])
        root = rig.bind("decide.root", factory=root_factory)
        child = rig.bind("retrieve.test", factory=lambda inv: completed(
            inv, schema_ids.EVIDENCE_BUNDLE, _bundle(make_evidence())))
        _, _, state = await rig.start()
        self.assertEqual(len(child.invocations), 1, "the reworded request must not run again")
        self.assertEqual(len(root.invocations), 3)
        self.assertEqual(len(state["work_items"]), 2)
        rooted = state["work_items"][state["task"].root_work_item_id]
        self.assertEqual(rooted.dependency_ids, [rooted.child_ids[0]])
        self.assertEqual(state["outcome"].status, RunStatus.COMPLETED)

    async def test_resumed_parent_receives_outcomes_in_child_creation_order(self) -> None:
        rig, root, _ = _rig(lambda inv: waiting(
            inv, proposal("internal_principles", "Which principles apply?"),
            proposal("prior_decisions", QUESTION)))
        _, _, state = await rig.start()
        order = [state["requests"][state["work_items"][o.work_item_id].request_id]
                 .payload["need"]["category"] for o in root.invocations[1].child_outcomes]
        self.assertEqual(order, ["internal_principles", "prior_decisions"])


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:40 [python-coder]: The reworded question keeps the same token set after
#   stopword removal, which is exactly the property the dedup key must preserve (Rev 3 8.4).
#   (#KernelBootstrapV0/P4)
# ====================================================================
