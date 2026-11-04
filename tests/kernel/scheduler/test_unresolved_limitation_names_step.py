"""
MODULE: tests.kernel.scheduler.test_unresolved_limitation_names_step
GOAL: Prove that when a guard trips on a work item that has no goal, the limitation written for
    it names the capability or step that was cut and never reads "unnamed request".
BUSINESS CONTEXT: Ticket KernelDecisionGoalRoutingAndRetrievalTimeout, AC-5. The limitation
    `unresolved_at_max_active_seconds: unnamed request` told the user nothing about which step
    was cut (runs run-cd87dd99047e4540 and run-1652957b15594844).
ARCHITECTURE: The caller is exercised end to end: a finished run is reopened so a retrieval child
    with no goal is unfinished, `schedule` trips the run-level Jev cap (the technique of
    test_guards_hardening), and the limitation `stop_unresolved` wrote is read from the merged
    state and from the decided outcome. The signature of `unresolved_text` is not fixed here.
"""

from __future__ import annotations

import types
import unittest
from typing import Any

from kernel.contracts import WorkItemStatus, schema_ids
from kernel.scheduler import decide_outcome
from kernel.scheduler.nodes_schedule import schedule
from kernel.scheduler.state import Budgets
from tests.kernel.scheduler.support import (
    Rig,
    completed,
    descriptor,
    proposal,
    retrieval_descriptor,
    two_phase,
    waiting,
)

CAPABILITY = "retrieve.repository"


async def _trip(goal: str | None) -> tuple[Any, Any, str]:
    """Run a root with one retrieval child (goal as given), reopen the child, trip a guard.

    Returns:
        tuple: (merged state after the trip, the reopened child, the child's limitation text).
    """
    rig = Rig([descriptor("decide.root"), retrieval_descriptor(CAPABILITY)])
    child_request = proposal("task_context", "Which facts apply to zebras?").model_copy(
        update={"goal": goal, "question": "Which facts apply to zebras?"})
    rig.bind("decide.root", factory=two_phase(lambda inv: waiting(inv, child_request), completed))
    rig.bind(CAPABILITY, factory=lambda inv: completed(inv, schema_ids.EVIDENCE_BUNDLE))
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
    update: Any = await schedule(state, types.SimpleNamespace(context=rig.runtime()))
    merged: Any = {**state, **update,
                   "work_items": {**state["work_items"], **update["work_items"]}}
    return merged, done["requests"][child.request_id], " | ".join(
        merged["work_items"][child.id].limitations)


class TestGuardTripOnAGoallessItemNamesTheStep(unittest.IsolatedAsyncioTestCase):
    """AC-5: no goal on the item, yet the limitation says which capability was cut."""

    async def test_ac5_the_limitation_names_the_capability_not_an_unnamed_request(self) -> None:
        # covers: UNKNOWN
        # angle: criterion
        """AC-5: `unresolved_at_<guard>` for a goalless item carries `retrieve.repository`."""
        merged, request, item_text = await _trip(None)
        self.assertIsNone(request.goal, "fixture must have no goal")
        self.assertIn("unresolved_at_max_jev_calls", item_text)
        self.assertNotIn("unnamed request", item_text)
        self.assertIn(CAPABILITY, item_text)
        outcome_text = " | ".join(decide_outcome(merged).limitations)
        self.assertNotIn("unnamed request", outcome_text)
        self.assertIn(CAPABILITY, outcome_text)

    async def test_ac5_an_item_with_a_goal_still_shows_its_goal(self) -> None:
        # covers: UNKNOWN
        # angle: discrimination
        """AC-5 control: the goal is still the subject when there is one.

        Catches the wrong version that always writes the capability id and drops the goal.
        """
        _, request, item_text = await _trip("Which facts apply to zebras?")
        self.assertEqual(request.goal, "Which facts apply to zebras?")
        self.assertIn("unresolved_at_max_jev_calls: Which facts apply to zebras?", item_text)


if __name__ == "__main__":
    unittest.main()
