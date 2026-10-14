"""
MODULE: tests.kernel.intent.test_evidence_floor
GOAL: Prove an evidence goal always plans research needs (task context and existing patterns at
    least) even when entity context is unavailable and Jev judges no category needed, and that a
    plan with zero needs can never end `completed`.
BUSINESS CONTEXT: Live runs 2026-10-09 answered a lookup question with an empty evidence bundle
    and status `completed` after two Jev calls: nothing was searched and nothing said so.
ARCHITECTURE: Real service over IntentCase (production registry, no entity index built, so
    recognition is `unavailable`); research-level checks call bundle_result and ResearchExecutor.
"""

from __future__ import annotations

import asyncio
import unittest
from pathlib import Path
from unittest import mock

from kernel.capabilities.research import ResearchExecutor
from kernel.capabilities.research.results import bundle_result
from kernel.capabilities.research.state import Collected, Plan, ResearchContinuation
from kernel.contracts import RunStatus, schema_ids
from kernel.contracts.enums import ResultStatus
from kernel.contracts.payloads import GoalRequestPayload
from tests.kernel.capabilities.support import invocation, no_git
from tests.kernel.helpers import bundle_of, make_context
from tests.kernel.intent.support import SURE, IntentCase

LOOKUP = "Find where this repository records why a piece of data is needed."


class TestEvidenceGoalPlansNeeds(IntentCase):
    """An evidence goal with unavailable entity context and no Jev-selected category."""

    async def test_goal_plans_baseline_needs_and_runs_retrieval(self) -> None:
        self.intents = [("evidence", *SURE)]
        self.needs = {}  # Jev judges no category needed
        envelope = await self.service().start_run(self.goal_task(LOOKUP))
        values = await self.checkpoint_values(envelope.run_id)
        recognized = [e for e in values["events"] if e.kind == "context.recognized"]
        self.assertIn("unavailable", recognized[0].detail)
        bundle = out_payload_of(envelope)
        self.assertEqual(sorted(bundle["coverage"]),
                         ["need.existing_patterns", "need.task_context"])
        self.assertIn("retrieve.repository", self.capabilities_used(values))
        self.assertNotIn("no evidence needs were identified for the question",
                         bundle["limitations"])
        self.assertIn(envelope.status, (RunStatus.COMPLETED, RunStatus.WAITING_HOST))

    async def test_selected_categories_are_not_padded_with_the_baseline(self) -> None:
        self.intents = [("evidence", *SURE)]
        self.needs = {"prior_decisions": 0.95}
        envelope = await self.service().start_run(self.goal_task(LOOKUP))
        self.assertEqual(sorted(out_payload_of(envelope)["coverage"]), ["need.prior_decisions"])


def out_payload_of(envelope) -> dict:
    """Return the evidence bundle payload of a run envelope."""
    assert envelope.output is not None, envelope.limitations
    assert envelope.output.schema_id == schema_ids.EVIDENCE_BUNDLE
    return dict(envelope.output.payload)


class TestEmptyPlanIsNeverCompleted(unittest.TestCase):
    """A bundle with no needs ends partial and says that no research ran."""

    def setUp(self) -> None:
        no_git(self)

    def test_bundle_result_without_needs_is_partial_with_a_no_research_limitation(self) -> None:
        inv = invocation("research", schema_ids.GOAL_REQUEST,
                         GoalRequestPayload(goal=LOOKUP).model_dump())
        plan = Plan(LOOKUP, "all_required", [], [])
        result = bundle_result(inv, plan, ResearchContinuation(phase="planned"), Collected(), [])
        self.assertEqual(result.status, ResultStatus.PARTIAL)
        bundle = bundle_of(result)
        text = " ".join(bundle.limitations)
        self.assertIn("no research ran", text)
        self.assertIn("no evidence needs were identified for the question", text)
        self.assertEqual(result.limitations, bundle.limitations)

    def test_executor_with_an_empty_plan_returns_partial_not_completed(self) -> None:
        async def nothing(ctx, invocation_, plan):
            return [], []
        ctx = make_context(Path(__file__).resolve().parents[3])
        inv = invocation("research", schema_ids.GOAL_REQUEST,
                         GoalRequestPayload(goal=LOOKUP).model_dump())
        with mock.patch("kernel.capabilities.research.executor.plan_needs", nothing):
            result = asyncio.run(ResearchExecutor().ainvoke(inv, ctx))
        self.assertEqual(result.status, ResultStatus.PARTIAL)
        self.assertTrue(any("no research ran" in x for x in bundle_of(result).limitations))


if __name__ == "__main__":
    unittest.main()
