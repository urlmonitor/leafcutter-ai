"""
MODULE: tests.kernel.grounding.test_grounded_run
GOAL: End-to-end proof, through the real service, that a decision with unknown options is
    grounded: the host is handed retrieved evidence with excerpts, an option that cites none of it
    is refused, the approval question names its grounding and carries the decision id, and one
    decision is one record.
BUSINESS CONTEXT: Live runs showed a human asked to approve options the host invented because it
    could not see the repository (G1); the same flow must now give the host evidence and give the
    human a decision they can trace.
ARCHITECTURE: ScenarioCase (production registry, real KernelService and stores, scripted Jev, a
    fake host); every assertion reads the envelope, the packet's input artifact or the checkpoint.
"""

from __future__ import annotations

import json
from pathlib import Path

from kernel.contracts import ActorKind, HumanQuestion, RunStatus, schema_ids
from tests.kernel.helpers import as_type
from tests.kernel.integration.scenario_support import (
    FakeHostResponder,
    ScenarioCase,
    answer_human,
    options_response,
)
from tests.kernel.interaction.support import raw_submission


class TestGroundedRun(ScenarioCase):
    """The host gets evidence; the human gets a traceable, grounded proposal."""

    domains = ("primary",)

    async def paused(self):
        return await self.service().start_run(self.task("primary", request=False))

    async def test_the_host_packet_carries_retrieved_evidence_with_excerpts(self) -> None:
        paused = await self.paused()
        self.assertEqual(paused.status, RunStatus.WAITING_HOST)
        packet = paused.pending_interaction
        self.assertTrue(packet.input_evidence_ids)
        self.assertNotIn("read_repo", packet.allowed_operations)  # no repository access
        text = " ".join(packet.output_requirements)
        self.assertIn("no repository access", text)
        self.assertIn("source_refs", text)
        (ref,) = packet.input_artifact_refs
        body = json.loads(Path(ref).read_text(encoding="utf-8"))
        self.assertEqual([e["id"] for e in body["evidence"]], packet.input_evidence_ids)
        self.assertIn("subgraph", " ".join(e["excerpt"] for e in body["evidence"]))
        self.assertTrue(body["request"]["require_grounding"])

    async def test_an_option_citing_no_evidence_is_refused(self) -> None:
        paused = await self.paused()
        packet = paused.pending_interaction.model_dump(mode="json")
        raw = raw_submission(packet, paused.run_id, kind=ActorKind.HOST,
                             response=options_response("primary"), actor_id="host:fake")
        done = await self.service().resume_run(paused.run_id, raw)
        question = done.pending_interaction  # only the (ungrounded-agnostic) criteria remain
        self.assertNotIn("Proposed options", as_type(question, HumanQuestion).question)
        self.assertFalse({"A", "B"} & set(as_type(question, HumanQuestion).subject_ids))
        self.assertEqual(self.jev.questions_asked("decision.assess"), [])

    async def test_the_approval_question_names_the_grounding_and_the_decision(self) -> None:
        responder = FakeHostResponder({schema_ids.OPTIONS: options_response("primary")})
        paused = await self.paused()
        approval = await self.service().resume_run(paused.run_id, responder.answer(paused))
        self.assertEqual(approval.status, RunStatus.WAITING_HUMAN)
        question = approval.pending_interaction
        cited = paused.pending_interaction.input_evidence_ids
        self.assertIn(f"grounded in {', '.join(cited)}", as_type(question, HumanQuestion).question)
        self.assertEqual(as_type(question, HumanQuestion).decision_id, approval.decision_ids[0])
        self.assertEqual(as_type(question, HumanQuestion).relevant_evidence_ids, cited)  # the cited evidence
        self.assertEqual(len(approval.decision_ids), 1)

    async def test_one_decision_is_one_record_through_to_the_end(self) -> None:
        self.params["satisfies"] = {("c1", "A"): 0.95, ("c2", "A"): 0.9}
        responder = FakeHostResponder({schema_ids.OPTIONS: options_response("primary")})
        paused = await self.paused()
        approval = await self.service().resume_run(paused.run_id, responder.answer(paused))
        final = await self.service().resume_run(
            paused.run_id, answer_human(approval, {"choice_id": "approve"}))
        self.assertEqual(final.status, RunStatus.COMPLETED)
        self.assertEqual(len(final.decision_ids), 1)
        self.assertEqual(final.decision_ids, approval.decision_ids)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 23:00 [python-coder]: End-to-end G1 proof through the real service.
#   (#KernelBootstrapV0/GROUND)
# ====================================================================
