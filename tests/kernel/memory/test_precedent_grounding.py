"""
MODULE: tests.kernel.memory.test_precedent_grounding
GOAL: An applicable precedent is evidence, but it is not what grounds the option space: a decision
    whose only evidence is a precedent still runs the `ground:options` research, and the options
    packet then cites the precedent and the researched evidence together.
BUSINESS CONTEXT: Run run-12741427fdf8450d judged a precedent about filing decision records
    applicable to "what to build next"; the decision then held evidence, the grounding rule
    skipped the research, and the host saw only the precedent, so it could propose no
    repository-grounded option.
ARCHITECTURE: The learning-loop rig (real service and graph, scripted Jev, fake host, file memory).
    Run 1 files a precedent; run 2 asks the same goal with a judgement above `applies_threshold`
    and below `reuse_threshold`, so the precedent becomes evidence without a reuse question.
"""

from __future__ import annotations

from kernel.contracts import EvidenceCategory, RunStatus, schema_ids
from tests.kernel.grounding.test_round6_end_to_end import GOAL
from tests.kernel.helpers import narrow
from tests.kernel.memory.test_learning_loop_e2e import LoopCase


class TestPrecedentDoesNotSkipGrounding(LoopCase):
    """The precedent stays evidence; research still runs and both reach the options packet."""

    async def test_a_precedent_only_decision_still_researches_and_cites_both_kinds(self) -> None:
        # covers: DK-100a-2-i
        await self.published()
        self.applies = 0.6  # applicable (>= 0.5), but no reuse question (< 0.8)
        envelope = await self.service().start_run(self.goal(GOAL))
        options_packet = None
        while envelope.status == RunStatus.WAITING_HOST:
            packet = narrow(envelope.pending_interaction)
            if packet.output_schema_id == schema_ids.OPTIONS:
                options_packet = packet
                break
            envelope = await self.service().resume_run(envelope.run_id, self.host_answer(envelope))
        self.assertIsNotNone(options_packet, envelope.status)
        values = await self.checkpoint_values(envelope.run_id)
        self.assertIn("research", self.capabilities_used(values))
        by_id = values["evidence"]
        cited = narrow(options_packet).input_evidence_ids
        categories = {by_id[i].category for i in cited}
        self.assertIn(EvidenceCategory.PRIOR_DECISIONS, categories)
        self.assertTrue(categories - {EvidenceCategory.PRIOR_DECISIONS}, categories)
        self.assertTrue(any(by_id[i].source.id != "memory.decisions" for i in cited))
