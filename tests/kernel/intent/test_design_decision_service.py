"""
MODULE: tests.kernel.intent.test_design_decision_service
GOAL: Prove the design-decision ending end to end through the real service and graph: a decision
    whose criteria are design judgements asks the human a ranked question after ONE assessment,
    and the human's choice completes the run with that human as approver.
BUSINESS CONTEXT: The live run run-5d246775f5e54f11 never reached a human or a ranked result
    (18 Jev calls). The observable fix is a WAITING_HUMAN run whose choices are the ranked
    options, then a COMPLETED run, with no research and no host operation in between.
ARCHITECTURE: ScenarioCase (production registry, real bindings, file stores, sqlite checkpointer,
    ScriptedJev); the decision records are read back from the checkpoint through a fresh saver.
"""

from __future__ import annotations

from kernel.contracts import RunStatus
from kernel.contracts.interaction import HumanQuestion
from tests.kernel.helpers import as_type, narrow
from tests.kernel.integration.scenario_support import ScenarioCase, answer_human


class TestDesignDecisionThroughTheService(ScenarioCase):
    """decision (one assessment) -> ranked human question -> the human's choice -> completed."""

    domains = ("primary",)

    def setUp(self) -> None:
        super().setUp()
        self.params.update(
            design={"c1", "c2"}, sufficient=0.6, missing="missing_internal_principle",
            satisfies={("c1", "A"): 0.55, ("c2", "A"): 0.60,
                       ("c1", "B"): 0.67, ("c2", "B"): 0.65})

    async def test_ranked_question_then_the_humans_choice_resolves_the_run(self) -> None:
        # covers: DK-300b-2
        paused = await self.service().start_run(self.task("primary", known_basis=True))
        self.assertEqual(paused.status, RunStatus.WAITING_HUMAN)
        question = as_type(paused.pending_interaction, HumanQuestion)
        self.assertEqual([c.id for c in question.choices], ["B", "A"])  # the kernel ranking
        self.assertIn("Kernel rank 1 of 2", question.choices[0].consequences)
        self.assertTrue(question.free_text_allowed and question.structured_allowed)
        assessed = [b for b in self.jev.batches if b.purpose == "decision.assess"]
        self.assertEqual(len(assessed), 1)  # no assess, research, synthesis loop

        final = await self.service().resume_run(
            paused.run_id, answer_human(paused, {"choice_id": "A"}))  # against the ranking
        self.assertEqual(final.status, RunStatus.COMPLETED)
        values = await self.checkpoint_values(final.run_id)
        used = self.capabilities_used(values)
        self.assertFalse([c for c in used if c.startswith("host.") or c == "research"])
        decisions = list(values["decisions"].values())
        self.assertEqual(len(decisions), 1)
        decision = decisions[0]
        self.assertEqual((decision.status.value, decision.selected_option_id), ("resolved", "A"))
        self.assertEqual((decision.approval_status.value, decision.approved_by), ("approved", "user"))
        text = narrow(decision.rationale).text
        self.assertIn("1. [B]", text)
        self.assertIn("user chose option [A]", text)
        self.assertEqual(len([b for b in self.jev.batches
                              if b.purpose == "decision.assess"]), 1)


if __name__ == "__main__":
    import unittest
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: One end-to-end case of the design-decision ending through
#   KernelService, because the unit cases only prove the graph. (#KernelV01/A)
# ====================================================================
