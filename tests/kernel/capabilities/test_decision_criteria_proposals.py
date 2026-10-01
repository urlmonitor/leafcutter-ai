"""
MODULE: tests.kernel.capabilities.test_decision_criteria_proposals
GOAL: Behavioural tests of the decision capability's options and criteria proposal path: an LLM
    proposes, a human approves or edits (structured answer), and only then does Jev decide.
BUSINESS CONTEXT: LLM-proposed options and criteria are never used without a human approval
    (ADR-053); free text is recorded, never parsed into criteria.
ARCHITECTURE: Split from test_decision_graph (file-size cap); shares DecisionTestCase and the
    helpers by import. ScriptedJev and the resume simulation come from the capabilities support.
"""

from __future__ import annotations

import unittest

from kernel.capabilities.decision.loading import load_working
from kernel.contracts import schema_ids
from kernel.contracts.decision import Option
from kernel.contracts.enums import ApprovalStatus, RequestKind, ResultStatus
from kernel.contracts.evidence import EvidenceBundlePayload
from kernel.contracts.payloads import (
    DecisionReportPayload,
    GoalRequestPayload,
    HumanQuestionRequestPayload,
    OptionsPayload,
    OptionsRequestPayload,
)
from tests.kernel.capabilities.support import (
    child,
    decision_payload as _payload,
    invocation,
    proposed_criteria as _proposed_criteria,
    resume,
)
from tests.kernel.capabilities.test_decision_graph import DECISION, DecisionTestCase


class TestOptionsAndCriteriaProposals(DecisionTestCase):
    """Missing options or criteria: LLM proposes, a human approves, only then Jev decides."""

    def test_no_options_requests_options_and_proposed_criteria_without_jev(self) -> None:
        ctx = self.ctx()
        inv = invocation(DECISION, schema_ids.GOAL_REQUEST,
                         GoalRequestPayload(goal="Where should state live?").model_dump())
        grounding = self.run_decision(inv, ctx)  # unknown options are grounded in evidence first
        self.assertEqual(grounding.requests[0].kind, RequestKind.EVIDENCE)
        bundle = EvidenceBundlePayload(evidence_ids=[self.evidence[0].id],
                                       evidence=self.evidence)
        found = child(ctx, RequestKind.EVIDENCE, schema_ids.EVIDENCE_BUNDLE,
                      bundle.model_dump(mode="json"))
        result = self.run_decision(resume(inv, grounding, [found]), ctx)
        request = result.requests[0]
        self.assertEqual(request.kind, RequestKind.OPTIONS)
        payload = OptionsRequestPayload.model_validate(request.payload)
        self.assertTrue(payload.propose_criteria)
        self.assertGreater(payload.max_options, 0)
        self.assertEqual(self.jev.call_count, 0)

    def test_options_known_criteria_missing_requests_llm_criteria_first(self) -> None:
        _, _, result = self.first(_payload(criteria=False))
        self.assertEqual(result.status, ResultStatus.WAITING)
        self.assertEqual([r.kind for r in result.requests], [RequestKind.OPTIONS])
        payload = OptionsRequestPayload.model_validate(result.requests[0].payload)
        self.assertTrue(payload.propose_criteria)
        self.assertEqual(payload.max_options, 0)
        self.assertEqual(payload.existing_option_ids, ["A", "B"])
        self.assertEqual(self.jev.call_count, 0)

    def _proposal_round(self):
        """Run request -> options child with proposed criteria; return state for the next step."""
        inv, ctx, waiting = self.first(_payload(criteria=False))
        proposals = OptionsPayload(proposed_criteria=_proposed_criteria())
        out = child(ctx, RequestKind.OPTIONS, schema_ids.OPTIONS,
                    proposals.model_dump(mode="json"))
        return inv, ctx, self.run_decision(resume(inv, waiting, [out]), ctx)

    def test_proposed_criteria_go_to_human_approval_before_jev(self) -> None:
        _, _, asked = self._proposal_round()
        request = asked.requests[0]
        self.assertEqual(request.kind, RequestKind.HUMAN)
        question = HumanQuestionRequestPayload.model_validate(request.payload)
        self.assertEqual(question.subject_ids, ["p1", "p2"])
        self.assertTrue(question.free_text_allowed)
        self.assertEqual({c.id for c in question.choices}, {"approve"})
        self.assertEqual(self.jev.call_count, 0)

    def test_jev_decides_against_approved_criteria_only(self) -> None:
        inv, ctx, asked = self._proposal_round()
        self.params["satisfies"] = {("p1", "A"): 0.95, ("p2", "A"): 0.95}
        approve = child(ctx, RequestKind.HUMAN, schema_ids.HUMAN_ANSWER,
                        {"choice_id": "approve"})
        done = self.run_decision(resume(inv, asked, [approve]), ctx)
        self.assertEqual(done.status, ResultStatus.COMPLETED)
        self.assertEqual(set(self.jev.batches[0].state["criteria"]), {"p1", "p2"})
        report = DecisionReportPayload.model_validate(done.output_payload)
        self.assertEqual(report.approval_status, ApprovalStatus.APPROVED)

    def test_unrecognised_answer_keeps_proposals_unapproved(self) -> None:
        inv, ctx, asked = self._proposal_round()
        junk = child(ctx, RequestKind.HUMAN, schema_ids.HUMAN_ANSWER, {"choice_id": "maybe"})
        result = self.run_decision(resume(inv, asked, [junk]), ctx)
        self.assertEqual(result.status, ResultStatus.PARTIAL)
        self.assertEqual(self.jev.call_count, 0)

    def test_edited_criteria_replace_the_proposals(self) -> None:
        inv, ctx, asked = self._proposal_round()
        edited = {"edited_criteria": [{"question": "Must survive a crash"},
                                      {"question": "Must run offline", "priority": "supporting"}]}
        edit = child(ctx, RequestKind.HUMAN, schema_ids.HUMAN_ANSWER, edited)
        self.params["satisfies"] = {("crit.edit.1", "A"): 0.95, ("crit.edit.2", "A"): 0.95}
        done = self.run_decision(resume(inv, asked, [edit]), ctx)
        self.assertEqual(done.status, ResultStatus.COMPLETED)
        state = self.jev.batches[0].state["criteria"]
        self.assertEqual(sorted(state.values()), ["Must run offline", "Must survive a crash"])
        self.assertNotIn("p1", state)

    def test_subset_approval_declines_the_unlisted_proposal(self) -> None:
        inv, ctx, asked = self._proposal_round()
        subset = child(ctx, RequestKind.HUMAN, schema_ids.HUMAN_ANSWER,
                       {"approved_criterion_ids": ["p1"]})
        self.params["satisfies"] = {("p1", "A"): 0.95}
        done = self.run_decision(resume(inv, asked, [subset]), ctx)
        self.assertEqual(done.status, ResultStatus.COMPLETED)
        self.assertEqual(set(self.jev.batches[0].state["criteria"]), {"p1"})

    def test_free_text_is_recorded_but_never_becomes_criteria(self) -> None:
        inv, ctx, asked = self._proposal_round()
        text = child(ctx, RequestKind.HUMAN, schema_ids.HUMAN_ANSWER,
                     {"free_text": "- Must survive a crash\n- Must run offline"})
        result = self.run_decision(resume(inv, asked, [text]), ctx)
        self.assertEqual(result.status, ResultStatus.PARTIAL)
        self.assertEqual(self.jev.call_count, 0)
        self.assertTrue(any("free-text answer recorded" in x for x in result.limitations))

    def test_edited_criteria_are_approved_by_the_answering_actor(self) -> None:
        inv, ctx, asked = self._proposal_round()
        edit = child(ctx, RequestKind.HUMAN, schema_ids.HUMAN_ANSWER,
                     {"edited_criteria": [{"question": "Must survive a crash"}]})
        edit = edit.model_copy(update={"actor_id": "alice"})
        work = load_working(resume(inv, asked, [edit]), ctx)
        mine = [c for c in work.criteria if c.id == "crit.edit.1"]
        self.assertEqual([(c.approved_by, c.proposed_by, c.proposal_status.value,
                           c.approval_status.value) for c in mine],
                         [("alice", "alice", "supplied", "approved")])
        declined = {c.id: c.approval_status.value for c in work.criteria if c.id in ("p1", "p2")}
        self.assertEqual(declined, {"p1": "rejected", "p2": "rejected"})

    def test_an_answer_to_an_earlier_question_is_not_applied_to_this_phase(self) -> None:
        inv, ctx, asked = self._proposal_round()
        stale = child(ctx, RequestKind.HUMAN, schema_ids.HUMAN_ANSWER, {"choice_id": "approve"})
        stale = stale.model_copy(update={"current_wait": False})
        result = self.run_decision(resume(inv, asked, [stale]), ctx)
        self.assertEqual(result.status, ResultStatus.PARTIAL)
        self.assertEqual(self.jev.call_count, 0)

    def test_generated_options_are_proposals_until_approved(self) -> None:
        ctx = self.ctx()
        inv = invocation(DECISION, schema_ids.GOAL_REQUEST,
                         GoalRequestPayload(goal="Where should state live?").model_dump())
        waiting = self.run_decision(inv, ctx)
        generated = OptionsPayload(
            options=[Option(id="G1", title="Generated", proposal_status="proposed",
                            approval_status="proposed", proposed_by="host")],
            proposed_criteria=_proposed_criteria())
        out = child(ctx, RequestKind.OPTIONS, schema_ids.OPTIONS,
                    generated.model_dump(mode="json"))
        asked = self.run_decision(resume(inv, waiting, [out]), ctx)
        question = HumanQuestionRequestPayload.model_validate(asked.requests[0].payload)
        self.assertEqual(question.subject_ids, ["p1", "p2", "G1"])
        self.assertEqual(self.jev.call_count, 0)

    def test_empty_options_reply_blocks_instead_of_looping(self) -> None:
        inv, ctx, waiting = self.first(_payload(options=False, criteria=False))
        empty = child(ctx, RequestKind.OPTIONS, schema_ids.OPTIONS, {})
        result = self.run_decision(resume(inv, waiting, [empty]), ctx)
        self.assertEqual(result.status, ResultStatus.BLOCKED)
        self.assertEqual(result.error.code, "options_unavailable")

    def test_failed_options_child_blocks(self) -> None:
        inv, ctx, waiting = self.first(_payload(criteria=False))
        failed = child(ctx, RequestKind.OPTIONS, schema_ids.OPTIONS, None, ResultStatus.FAILED)
        result = self.run_decision(resume(inv, waiting, [failed]), ctx)
        self.assertEqual(result.status, ResultStatus.BLOCKED)
        self.assertEqual(result.error.code, "child_unavailable")


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 23:00 [python-coder]: A goal-only decision first researches the option space; the
#   options request (with proposed criteria) follows once evidence exists.
#   (#KernelBootstrapV0/GROUND)
# - 2026-09-30 23:59 [python-coder]: Moved out of test_decision_graph to keep that file under
#   the 400-line cap. (#KernelBootstrapV0/P6)
# ====================================================================
