"""
MODULE: tests.kernel.capabilities.test_choice_with_condition
GOAL: Through the real DecisionExecutor: a human choice carrying a condition keeps the choice
    authoritative and records the text verbatim as a condition (Jev's constraints labelled
    human-stated, the rationale, the staged record's constraints); a choice of a usable option at
    an escalation (unidentified gap) resolves the decision with the human as approver.
BUSINESS CONTEXT: Live 2026-10-02: a choice at an unidentified_gap only set a preference and never
    settled the decision, and "X, but with condition Y" could not be answered as said.
ARCHITECTURE: DesignCase rig (scripted Jev, simulated resume) with a real file memory for staging.
"""

from __future__ import annotations

from dataclasses import replace

from kernel.contracts import schema_ids
from kernel.contracts.enums import ApprovalStatus, DecisionStatus, RequestKind, ResultStatus
from kernel.contracts.payloads import DecisionReportPayload
from tests.kernel.capabilities.test_design_ending import DesignCase
from tests.kernel.capabilities.support import child, resume
from tests.kernel.helpers import as_json, narrow
from tests.kernel.memory.test_decision_precedent import PrecedentCase

CONDITION = "but Jev should be able to decide based on some criteria"


class GapCase(PrecedentCase):
    """An unidentified gap: evidence is thin and Jev names only a human preference as missing."""

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
        self.assertEqual(waiting.continuation_state["pending_reason"], "unidentified_gap")
        return inv, ctx, waiting


class TestChoiceAtAnEscalationResolves(GapCase):
    """A choice of a usable option at an unidentified gap settles the decision."""

    def test_a_choice_at_an_unidentified_gap_completes_with_the_human_as_approver(self) -> None:
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
        self.assertRegex(text.lower(), r"human (ruling|ruled)|ruled by|ruling")
        self.assertNotIn("design_judgement", text)

    def test_a_choice_that_is_not_a_usable_option_does_not_resolve(self) -> None:
        # covers: UNKNOWN
        # angle: failure
        inv, ctx, waiting = self.ask()
        done = self.answer(inv, ctx, waiting, {"choice_id": "nope"})
        self.assertNotEqual(done.decisions[0].status, DecisionStatus.RESOLVED)


class TestConditionIsRecorded(GapCase):
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
        # A free-text-only escalation answer re-assesses; the labelled text reaches Jev.
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
