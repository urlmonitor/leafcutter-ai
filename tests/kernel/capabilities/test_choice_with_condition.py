"""
MODULE: tests.kernel.capabilities.test_choice_with_condition
GOAL: Through the real DecisionExecutor: a human choice carrying a condition keeps the choice
    authoritative and records the text verbatim as a condition (Jev's constraints labelled
    human-stated, the rationale, the staged record's constraints); a choice of a usable option at
    an escalation (a tie) resolves the decision with the human as approver and a human-ruling
    rationale; the same holds for the ranked question a thin-evidence gap now ends in.
BUSINESS CONTEXT: Live 2026-10-02: a choice at an escalation only set a preference and never
    settled the decision, and "X, but with condition Y" could not be answered as said. Since
    #KernelResearchFirst an unidentified gap with usable options ends in the ranked design-choice
    question (phase awaiting_design_choice), not in awaiting_human, so the human-ruling path of
    approvals._apply_escalation is covered through a tie.
ARCHITECTURE: DesignCase rig (scripted Jev, simulated resume) with a real file memory for staging.
"""

from __future__ import annotations

from dataclasses import replace

from kernel.capabilities.decision.loading import load_working
from kernel.capabilities.decision.ranking import NO_RESEARCH_TARGETS
from kernel.contracts import schema_ids
from kernel.contracts.enums import ApprovalStatus, DecisionStatus, RequestKind, ResultStatus
from kernel.contracts.payloads import DecisionReportPayload, OptionsPayload
from tests.kernel.capabilities.test_design_ending import DesignCase
from tests.kernel.capabilities.support import child, decision_payload, proposed_criteria, resume
from tests.kernel.helpers import as_json, narrow
from tests.kernel.memory.test_decision_precedent import PrecedentCase

CONDITION = "but Jev should be able to decide based on some criteria"
SUFFIX = " Condition stated by the human: {}"


class RankedGapCase(PrecedentCase):
    """Thin evidence, Jev names only a human preference as missing, options are rankable.

    The kernel does not escalate this blindly: the options name nothing to research, so it hands the
    human the ranked question (pending reason `no_research_targets`, phase `awaiting_design_choice`).
    """

    def setUp(self) -> None:
        super().setUp()
        self.params.update(sufficient=0.2, satisfies={},
                           missing="human_preference_or_authorization")

    def ask(self):  # noqa: ANN201
        inv, ctx, waiting = self.first()
        if waiting.requests[0].kind == RequestKind.SYNTHESIS:  # the one synthesis comes first
            findings = child(ctx, RequestKind.SYNTHESIS, schema_ids.FINDINGS, {})
            waiting = self.run_decision(resume(inv, waiting, [findings]), ctx)
        self.assertEqual(waiting.decisions[0].status, DecisionStatus.NEEDS_HUMAN)
        self.assertEqual(waiting.continuation_state["pending_reason"], NO_RESEARCH_TARGETS)
        self.assertEqual(waiting.continuation_state["phase"], "awaiting_design_choice")
        return inv, ctx, waiting


class TieCase(PrecedentCase):
    """Two options pass every required criterion: an `awaiting_human` tie with usable options."""

    def setUp(self) -> None:
        super().setUp()
        self.params.update(satisfies={("c1", "A"): 0.95, ("c1", "B"): 0.95})

    def ask(self):  # noqa: ANN201
        inv, ctx, waiting = self.first()
        self.assertEqual(waiting.decisions[0].status, DecisionStatus.NEEDS_HUMAN)
        self.assertEqual(waiting.continuation_state["phase"], "awaiting_human")
        self.assertEqual(waiting.continuation_state["pending_reason"], "tie")
        return inv, ctx, waiting


class TestChoiceAtAnEscalationResolves(TieCase):
    """A choice of a usable option at an awaiting_human escalation (a tie) settles the decision."""

    def test_a_choice_at_a_tie_completes_with_the_human_as_approver(self) -> None:
        # covers: UNKNOWN
        # angle: reachability
        inv, ctx, waiting = self.ask()
        done = self.answer(inv, ctx, waiting, {"choice_id": "A"}, actor="human:ada")
        self.assertEqual(done.status, ResultStatus.COMPLETED)
        report = DecisionReportPayload.model_validate(done.output_payload)
        self.assertEqual((report.status, report.selected_option_id),
                         (DecisionStatus.RESOLVED, "A"))
        decision = done.decisions[0]
        self.assertEqual((decision.approval_status, decision.approved_by),
                         (ApprovalStatus.APPROVED, "human:ada"))

    def test_the_rationale_names_a_human_ruling_not_a_kernel_finding(self) -> None:
        # covers: UNKNOWN
        # angle: discrimination
        inv, ctx, waiting = self.ask()
        done = self.answer(inv, ctx, waiting, {"choice_id": "A"}, actor="human:ada")
        text = narrow(done.decisions[0].rationale).text
        self.assertIn("human:ada", text)
        self.assertIn("Human ruling", text)
        self.assertNotIn("Kernel ranking", text)
        self.assertNotIn("design_judgement", text)

    def test_a_choice_that_is_not_a_usable_option_does_not_resolve(self) -> None:
        # covers: UNKNOWN
        # angle: failure
        inv, ctx, waiting = self.ask()
        done = self.answer(inv, ctx, waiting, {"choice_id": "nope"})
        self.assertNotEqual(done.decisions[0].status, DecisionStatus.RESOLVED)

    def test_a_choice_with_a_condition_records_it(self) -> None:
        # covers: UNKNOWN
        # angle: seam
        inv, ctx, waiting = self.ask()
        done = self.answer(inv, ctx, waiting, {"choice_id": "A", "free_text": CONDITION},
                           actor="human:ada")
        self.assertEqual(done.status, ResultStatus.COMPLETED)
        self.assertEqual(done.decisions[0].selected_option_id, "A")
        self.assertIn(CONDITION, narrow(done.decisions[0].rationale).text)
        (record,) = self.staged(ctx)
        self.assertIn(CONDITION, record.task_context.constraints)


class TestRankedQuestionChoice(RankedGapCase):
    """The ranked question a thin-evidence gap ends in: a choice settles it, the rank is shown."""

    def test_a_choice_completes_and_the_rationale_keeps_the_kernel_ranking(self) -> None:
        # covers: UNKNOWN
        # angle: reachability
        inv, ctx, waiting = self.ask()
        done = self.answer(inv, ctx, waiting, {"choice_id": "A"}, actor="human:ada")
        self.assertEqual(done.status, ResultStatus.COMPLETED)
        self.assertEqual(done.decisions[0].selected_option_id, "A")
        self.assertEqual(done.decisions[0].approved_by, "human:ada")
        text = narrow(done.decisions[0].rationale).text
        self.assertIn("human:ada", text)
        self.assertIn("Kernel ranking", text)

    def test_a_choice_that_is_not_a_usable_option_does_not_resolve(self) -> None:
        # covers: UNKNOWN
        # angle: failure
        inv, ctx, waiting = self.ask()
        done = self.answer(inv, ctx, waiting, {"choice_id": "nope"})
        self.assertNotEqual(done.decisions[0].status, DecisionStatus.RESOLVED)


class TestConditionIsRecorded(RankedGapCase):
    """The text of a pair is a verbatim condition: constraints, rationale and staged record."""

    PAIR = {"choice_id": "A", "free_text": CONDITION}

    def test_the_choice_stays_authoritative_and_the_condition_reaches_the_rationale(self) -> None:
        # covers: UNKNOWN
        # angle: criterion
        inv, ctx, waiting = self.ask()
        done = self.answer(inv, ctx, waiting, self.PAIR, actor="human:ada")
        self.assertEqual(done.status, ResultStatus.COMPLETED)
        self.assertEqual(done.decisions[0].selected_option_id, "A")
        self.assertIn(CONDITION, narrow(done.decisions[0].rationale).text)

    def test_the_rationale_ends_with_the_condition_stated_by_the_human(self) -> None:
        # covers: UNKNOWN
        # angle: criterion
        inv, ctx, waiting = self.ask()
        done = self.answer(inv, ctx, waiting, self.PAIR, actor="human:ada")
        text = narrow(done.decisions[0].rationale).text
        self.assertTrue(text.endswith(f"Condition stated by the human: {CONDITION}"), text)

    def test_the_staged_record_carries_the_condition_in_its_constraints(self) -> None:
        # covers: UNKNOWN
        # angle: seam
        inv, ctx, waiting = self.ask()
        self.answer(inv, ctx, waiting, self.PAIR, actor="human:ada")
        (record,) = self.staged(ctx)
        self.assertIn(CONDITION, record.task_context.constraints)

    def test_jev_sees_the_condition_as_a_labelled_human_stated_constraint(self) -> None:
        # covers: UNKNOWN
        # angle: seam
        # A free-text-only answer to the ranked question re-assesses; the labelled text reaches Jev.
        inv, ctx, waiting = self.ask()
        self.answer(inv, ctx, waiting, {"free_text": CONDITION})
        constraints = as_json(self.jev.batches[-1].state)["constraints"]
        labelled = [c for c in constraints if CONDITION in c]
        self.assertTrue(labelled, constraints)
        self.assertTrue(all("human" in c.lower() for c in labelled), labelled)


class TestDesignChoiceWithACondition(PrecedentCase, DesignCase):
    """The ranked design question answered with a choice and a condition."""

    def setUp(self) -> None:
        super().setUp()
        self.params.update(design={"c1"})
        self.inv, self.ctx_, self.waiting = self.start()

    def ctx(self, evidence=None):  # noqa: ANN001, ANN201
        return replace(DesignCase.ctx(self, evidence), memory=self.memory)

    def test_a_design_choice_with_a_condition_resolves_and_records_it(self) -> None:
        # covers: UNKNOWN
        # angle: seam
        done = self.answer(self.inv, self.ctx_, self.waiting,
                           {"choice_id": "C", "free_text": CONDITION}, actor="human:ada")
        self.assertEqual(done.status, ResultStatus.COMPLETED)
        self.assertEqual(done.decisions[0].selected_option_id, "C")
        self.assertIn(CONDITION, narrow(done.decisions[0].rationale).text)
        (record,) = self.staged(self.ctx_)
        self.assertIn(CONDITION, record.task_context.constraints)



def kept_after(case: PrecedentCase, inv, ctx, waiting, response):  # noqa: ANN001, ANN201
    """Apply a human answer to the waiting decision and return the working continuation."""
    out = child(ctx, RequestKind.HUMAN, schema_ids.HUMAN_ANSWER, response)
    return load_working(resume(inv, waiting, [out]), ctx).cont


class TestApprovalWithACondition(PrecedentCase):
    """The approve answer at awaiting_approval carries free text: it is a condition of the approval."""

    def asked(self):  # noqa: ANN201
        inv, ctx, waiting = self.first(decision_payload(criteria=False))
        proposals = OptionsPayload(proposed_criteria=proposed_criteria())
        out = child(ctx, RequestKind.OPTIONS, schema_ids.OPTIONS,
                    proposals.model_dump(mode="json"))
        asked = self.run_decision(resume(inv, waiting, [out]), ctx)
        self.assertEqual(asked.continuation_state["phase"], "awaiting_approval")
        self.params["satisfies"] = {("p1", "A"): 0.95, ("p2", "A"): 0.95}
        return inv, ctx, asked

    def test_ac1_approve_with_free_text_keeps_the_text_as_a_condition(self) -> None:
        # covers: UNKNOWN
        # angle: criterion
        inv, ctx, asked = self.asked()
        cont = kept_after(self, inv, ctx, asked, {"choice_id": "approve", "free_text": CONDITION})
        self.assertEqual(cont.conditions, [CONDITION])
        self.assertEqual(cont.human_inputs, [])

    def test_ac1_the_approval_condition_reaches_the_rationale_and_the_staged_record(self) -> None:
        # covers: UNKNOWN
        # angle: seam
        inv, ctx, asked = self.asked()
        done = self.answer(inv, ctx, asked, {"choice_id": "approve", "free_text": CONDITION},
                           actor="human:ada")
        self.assertEqual(done.status, ResultStatus.COMPLETED)
        text = narrow(done.decisions[0].rationale).text
        self.assertTrue(text.endswith(SUFFIX.format(CONDITION)), text)
        (record,) = self.staged(ctx)
        self.assertIn(CONDITION, record.task_context.constraints)

    def test_an_approval_without_text_keeps_no_condition(self) -> None:
        # covers: UNKNOWN
        # angle: boundary
        inv, ctx, asked = self.asked()
        cont = kept_after(self, inv, ctx, asked, {"choice_id": "approve", "free_text": "  "})
        self.assertEqual(cont.conditions, [])

    def test_two_conditions_give_two_suffixes_in_order(self) -> None:
        # covers: UNKNOWN
        # angle: boundary
        # A first condition is already on the continuation (as an earlier answer would leave it).
        inv, ctx, asked = self.asked()
        state = {**asked.continuation_state, "conditions": ["first condition"]}
        asked = asked.model_copy(update={"continuation_state": state})
        done = self.answer(inv, ctx, asked, {"choice_id": "approve", "free_text": CONDITION})
        text = narrow(done.decisions[0].rationale).text
        self.assertTrue(
            text.endswith(SUFFIX.format("first condition") + SUFFIX.format(CONDITION)), text)

    def test_no_condition_leaves_the_gate_rationale_unchanged(self) -> None:
        # covers: UNKNOWN
        # angle: discrimination
        inv, ctx, asked = self.asked()
        done = self.answer(inv, ctx, asked, {"choice_id": "approve"})
        text = narrow(done.decisions[0].rationale).text
        self.assertEqual(text, "Option [A] Use sqlite satisfies the required criteria "
                               f"['p1', 'p2'] according to evidence {[e.id for e in self.evidence]}.")

    def test_the_report_rationale_carries_the_suffix_too(self) -> None:
        # covers: UNKNOWN
        # angle: seam
        inv, ctx, asked = self.asked()
        done = self.answer(inv, ctx, asked, {"choice_id": "approve", "free_text": CONDITION})
        report = DecisionReportPayload.model_validate(done.output_payload)
        text = narrow(report.rationale).text
        self.assertTrue(text.endswith(SUFFIX.format(CONDITION)), text)

    def test_an_unrecognised_approval_choice_is_recorded_and_keeps_no_text(self) -> None:
        # covers: UNKNOWN
        # angle: failure
        inv, ctx, asked = self.asked()
        response = {"choice_id": "maybe", "free_text": CONDITION}
        cont = kept_after(self, inv, ctx, asked, response)
        self.assertEqual((cont.conditions, cont.human_inputs), ([], []))
        done = self.answer(inv, ctx, asked, response)
        self.assertNotEqual(done.status, ResultStatus.COMPLETED)
        self.assertIn("unrecognised approval answer 'maybe'", done.limitations)


class TestUnusableChoiceKeepsNothingAtATie(TieCase):
    """A choice that is not a usable option keeps neither its text nor a ruling at awaiting_human."""

    def test_the_text_is_kept_nowhere_and_the_limitation_is_recorded(self) -> None:
        # covers: UNKNOWN
        # angle: discrimination
        inv, ctx, waiting = self.ask()
        response = {"choice_id": "nope", "free_text": CONDITION}
        cont = kept_after(self, inv, ctx, waiting, response)
        self.assertEqual((cont.conditions, cont.human_inputs), ([], []))
        done = self.answer(inv, ctx, waiting, response)
        self.assertNotEqual(done.decisions[0].status, DecisionStatus.RESOLVED)
        self.assertIn("answer 'nope' is not a usable option", done.limitations)


class TestUnusableChoiceKeepsNothingAtTheRankedQuestion(RankedGapCase):
    """The same at awaiting_design_choice, where the text used to be kept as a condition."""

    def test_the_text_is_kept_nowhere_and_the_limitation_is_recorded(self) -> None:
        # covers: UNKNOWN
        # angle: discrimination
        inv, ctx, waiting = self.ask()
        response = {"choice_id": "nope", "free_text": CONDITION}
        cont = kept_after(self, inv, ctx, waiting, response)
        self.assertEqual((cont.conditions, cont.human_inputs), ([], []))
        done = self.answer(inv, ctx, waiting, response)
        self.assertNotEqual(done.decisions[0].status, DecisionStatus.RESOLVED)
        self.assertIn("answer 'nope' is not a usable option", done.limitations)


class TestATieRulingDoesNotClaimAKernelRanking(TieCase):
    """No ranking was shown at a tie, so the report must say a human ruled, not that it ranked."""

    def test_the_limitation_names_the_human_ruling_and_not_a_kernel_ranking(self) -> None:
        # covers: UNKNOWN
        # angle: discrimination
        inv, ctx, waiting = self.ask()
        done = self.answer(inv, ctx, waiting, {"choice_id": "A"}, actor="human:ada")
        limitations = DecisionReportPayload.model_validate(done.output_payload).limitations
        self.assertIn("human ruling: human:ada chose [A] at a tie escalation", limitations)
        self.assertFalse([x for x in limitations if "ranked by the kernel" in x], limitations)

    def test_the_staged_basis_stays_kernel_ranking_with_an_empty_ranking(self) -> None:
        # covers: UNKNOWN
        # angle: boundary
        # Current, documented behaviour: assessment.basis is a pinned vocabulary (the schema is a
        # hash-pinned trusted asset), so a human ruling is still staged as kernel_ranking. A basis
        # value for it needs a reviewed re-pin: the basis-vocabulary follow-up ticket.
        inv, ctx, waiting = self.ask()
        self.answer(inv, ctx, waiting, {"choice_id": "A"}, actor="human:ada")
        (record,) = self.staged(ctx)
        self.assertEqual(record.assessment.basis, "kernel_ranking")
        self.assertEqual(list(record.assessment.ranking), [])


class TestPrecedentReuseWithACondition(PrecedentCase):
    """A condition stated earlier still ends the rationale when a precedent is then reused."""

    def test_the_reuse_rationale_ends_with_the_condition(self) -> None:
        # covers: UNKNOWN
        # angle: seam
        inv, ctx, waiting = self.goal()
        self.assertEqual(waiting.continuation_state["phase"], "awaiting_precedent")
        state = {**waiting.continuation_state, "conditions": [CONDITION]}
        waiting = waiting.model_copy(update={"continuation_state": state})
        done = self.answer(inv, ctx, waiting, {"choice_id": "reuse"}, actor="human:ada")
        self.assertEqual(done.status, ResultStatus.COMPLETED)
        text = narrow(done.decisions[0].rationale).text
        self.assertTrue(text.endswith(SUFFIX.format(CONDITION)), text)

    def test_no_condition_leaves_the_reuse_rationale_without_a_suffix(self) -> None:
        # covers: UNKNOWN
        # angle: boundary
        inv, ctx, waiting = self.goal()
        done = self.answer(inv, ctx, waiting, {"choice_id": "reuse"}, actor="human:ada")
        self.assertNotIn("Condition stated", narrow(done.decisions[0].rationale).text)
