"""
MODULE: tests.kernel.memory.test_decision_precedent
GOAL: The decision capability's use of earlier approved decisions, through the real
    DecisionExecutor with a real file memory and a scripted Jev: a matching precedent is judged
    (one call before any basis exists, inside the assess batch otherwise), becomes evidence, and a
    strong match becomes the short reuse-or-decide-anew question; reuse resolves with the current
    human as approver; nothing resolves without a human; and what a human approved is staged.
BUSINESS CONTEXT: Precedent from day one (ADR-059) without authority (ADR-060): the kernel asks Jev
    whether an earlier decision applies, shows it as evidence with its approver, and lets only a
    human reuse it. A decision approved by a host or nobody must leave no record.
ARCHITECTURE: The kernel's resume step is simulated with the capability support helpers; the store
    is a temporary `docs/decisions` written by the real dumper with the real generated index; the
    executor gets the memory through `ExecutionContext.memory`.
"""

from __future__ import annotations

from dataclasses import replace

from kernel.contracts import schema_ids
from kernel.contracts.enums import (
    ApprovalStatus,
    DecisionStatus,
    EvidenceCategory,
    RequestKind,
    ResultStatus,
)
from kernel.contracts.payloads import DecisionReportPayload, HumanQuestionRequestPayload
from kernel.memory.codec import dump_record, load_record_file
from kernel.memory.file_store import FileColonyMemory, staged_files
from kernel.memory.publish import rebuild_index
from kernel.memory.validate import validate_store
from kernel.providers.fakes import noul_answer
from tests.kernel.capabilities.support import child, decision_payload, invocation, resume
from tests.kernel.capabilities.test_decision_graph import DECISION, DecisionTestCase
from tests.kernel.capabilities.test_design_ending import DesignCase
from tests.kernel.helpers import as_json, narrow
from tests.kernel.memory.support import make_record, schema, vocabulary

PRECEDENT_ID = "dec-0123456789abcdef"
QUESTION = "Where should the kernel file approved decisions so later runs find them?"
CONFIRM = ("Decision dec-0123456789abcdef (approved by human:tester on 2026-10-01) chose "
           "One YAML file per decision for a matching question. Reuse it, or decide anew?")


class RefusingBudget:
    """A budget with no Jev calls left."""

    def reserve(self, resource) -> bool:  # noqa: ANN001
        return False

    def available(self, resource) -> int | None:  # noqa: ANN001
        return 0


class PrecedentCase(DecisionTestCase):
    """A store with one approved precedent and a scripted Jev that judges it."""

    applies = 0.95

    def setUp(self) -> None:
        super().setUp()
        self.folder = self.root / "docs" / "decisions"
        self.folder.mkdir(parents=True)
        self.write(make_record())
        self.memory = FileColonyMemory(self.root, self.root / "run")
        self.params["applies"] = self.applies
        for purpose in ("decision.precedent", "decision.assess"):
            self.jev.script(purpose, "precedent.*", lambda q, b: noul_answer(self.params["applies"]))

    def write(self, *records) -> None:  # noqa: ANN002
        for record in records:
            (self.folder / f"{record.id}.yaml").write_text(dump_record(record), encoding="utf-8",
                                                           newline="\n")
        report, written = rebuild_index(self.folder, schema(), vocabulary())
        self.assertTrue(written, report.problems)

    def ctx(self, evidence=None, **overrides):  # noqa: ANN001, ANN201
        return replace(super().ctx(evidence), memory=self.memory, **overrides)

    def goal(self, text: str = QUESTION):  # noqa: ANN201
        ctx = self.ctx()
        inv = invocation(DECISION, schema_ids.GOAL_REQUEST, {"goal": text})
        return inv, ctx, self.run_decision(inv, ctx)

    def answer(self, inv, ctx, waiting, response, actor="human:ada"):  # noqa: ANN001, ANN201
        """Answer the human question; the kernel has merged the waiting result's evidence by now."""
        ctx = replace(ctx, evidence_lookup=self.ctx([*self.evidence, *waiting.evidence])
                      .evidence_lookup)
        out = child(ctx, RequestKind.HUMAN, schema_ids.HUMAN_ANSWER, response)
        return self.run_decision(resume(inv, waiting, [out.model_copy(update={"actor_id": actor})]),
                                 ctx)

    def staged(self, ctx=None):  # noqa: ANN001, ANN201
        """Return every record staged under the run root (any run)."""
        runs = (self.root / "run" / "runs")
        files = [f for d in (runs.iterdir() if runs.is_dir() else [])
                 for f in staged_files(self.root / "run", d.name)]
        return [load_record_file(f) for f in files]

    def matching(self, **extra):  # noqa: ANN003, ANN201
        """Run the first invocation of a decision request whose question matches the precedent."""
        ctx = self.ctx()
        body = {**decision_payload(**extra), "question": QUESTION,
                "evidence_ids": [e.id for e in self.evidence]}
        inv = invocation(DECISION, schema_ids.DECISION_REQUEST, body)
        return inv, ctx, self.run_decision(inv, ctx)


class TestAMatchingPrecedentBeforeAnyBasis(PrecedentCase):
    """Goal only: no assessment is coming, so one Jev call judges the precedent."""

    def test_one_call_judges_it_and_the_human_is_asked_to_reuse_or_decide_anew(self) -> None:
        # covers: DK-300e-3
        _, _, waiting = self.goal()
        self.assertEqual(self.jev.call_count, 1)
        self.assertEqual([b.purpose for b in self.jev.batches], ["decision.precedent"])
        self.assertEqual(self.jev.questions_asked("decision.precedent"),
                         [f"precedent.{PRECEDENT_ID}"])
        self.assertEqual(waiting.status, ResultStatus.WAITING)
        request = waiting.requests[0]
        self.assertEqual(request.kind, RequestKind.HUMAN)
        question = HumanQuestionRequestPayload.model_validate(request.payload)
        self.assertEqual(question.question, CONFIRM)
        self.assertEqual([c.id for c in question.choices], ["reuse", "decide_anew"])
        self.assertFalse(question.free_text_allowed)
        self.assertEqual(waiting.continuation_state["phase"], "awaiting_precedent")
        self.assertEqual(waiting.decisions[0].status, DecisionStatus.NEEDS_HUMAN)

    def test_the_precedent_reaches_the_kernel_as_prior_decisions_evidence_with_its_approver(
            self) -> None:
        _, _, waiting = self.goal()
        (item,) = waiting.evidence
        self.assertEqual(item.category, EvidenceCategory.PRIOR_DECISIONS)
        self.assertEqual(item.source.locator, f"docs/decisions/{PRECEDENT_ID}.yaml")
        self.assertIn("approved by human:tester", item.source.title)
        self.assertIn("human:tester", narrow(item.provenance.query))
        self.assertIsNone(item.provenance.actor)  # a file is never mistaken for a human answer
        self.assertEqual(waiting.decisions[0].precedent_ids, [PRECEDENT_ID])
        question = HumanQuestionRequestPayload.model_validate(waiting.requests[0].payload)
        self.assertEqual(question.evidence_ids, [item.id])

    def test_the_precedent_alone_resolves_nothing(self) -> None:
        # covers: DK-300e-3
        _, _, waiting = self.goal()
        self.assertNotEqual(waiting.status, ResultStatus.COMPLETED)
        self.assertIsNone(waiting.decisions[0].selected_option_id)
        self.assertEqual(self.staged(self.ctx()), [])

    def test_reuse_resolves_with_the_precedents_choice_approved_by_the_current_human(self) -> None:
        # covers: DK-300e-4
        inv, ctx, waiting = self.goal()
        done = self.answer(inv, ctx, waiting, {"choice_id": "reuse"}, actor="human:ada")
        self.assertEqual(done.status, ResultStatus.COMPLETED)
        report = DecisionReportPayload.model_validate(done.output_payload)
        self.assertEqual((report.status, report.selected_option_id, report.recommendation),
                         (DecisionStatus.RESOLVED, "opt.yaml", "One YAML file per decision"))
        decision = done.decisions[0]
        self.assertEqual((decision.approval_status, decision.approved_by),
                         (ApprovalStatus.APPROVED, "human:ada"))  # not human:tester
        self.assertIsNotNone(decision.approved_at)
        self.assertEqual(decision.precedent_ids, [PRECEDENT_ID])
        self.assertIn(PRECEDENT_ID, narrow(decision.rationale).text)
        self.assertIn("human:ada confirmed", narrow(decision.rationale).text)
        self.assertEqual(report.supporting_evidence_ids, [waiting.evidence[0].id])
        self.assertEqual(self.jev.call_count, 1)  # no further Jev call, no research, no host work
        self.assertEqual(done.requests, [])

    def test_reuse_stages_a_new_record_citing_the_precedent(self) -> None:
        # covers: DK-300e-4
        inv, ctx, waiting = self.goal()
        done = self.answer(inv, ctx, waiting, {"choice_id": "reuse"}, actor="human:ada")
        (record,) = self.staged(ctx)
        notes = [x for x in done.limitations if x.startswith("decision record staged:")]
        self.assertEqual(len(notes), 1)  # the result tells the user and how to publish
        self.assertIn(f"decisions publish --run-id {ctx.run_id}", notes[0])
        self.assertIn(notes[0], DecisionReportPayload.model_validate(done.output_payload).limitations)
        self.assertNotEqual(record.id, PRECEDENT_ID)
        self.assertEqual((record.approval.approved_by, record.selected_option_id),
                         ("human:ada", "opt.yaml"))
        self.assertEqual(record.related, [PRECEDENT_ID])
        self.assertEqual(record.supersedes, [])
        self.assertEqual([(n.id, n.action) for n in record.precedents_considered],
                         [(PRECEDENT_ID, "reused")])
        self.assertEqual(record.assessment.basis, "precedent_reuse")
        self.assertEqual(record.provenance.run_id, ctx.run_id)
        self.assertEqual(len(record.provenance.langfuse_trace_id or ""), 32)

    def test_staging_never_touches_the_repository_store(self) -> None:
        # covers: DK-300e-4
        before = sorted(p.name for p in self.folder.iterdir())
        inv, ctx, waiting = self.goal()
        self.answer(inv, ctx, waiting, {"choice_id": "reuse"})
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()), before)

    def test_decide_anew_continues_the_normal_flow_and_keeps_the_precedent_as_evidence(
            self) -> None:
        inv, ctx, waiting = self.goal()
        again = self.answer(inv, ctx, waiting, {"choice_id": "decide_anew"})
        self.assertEqual(again.status, ResultStatus.WAITING)
        # the normal flow: a precedent is not grounding evidence, so the research runs first
        self.assertEqual(again.requests[0].kind, RequestKind.EVIDENCE)
        self.assertEqual(self.jev.call_count, 1)  # the precedent is not judged twice
        self.assertIn(waiting.evidence[0].id, again.continuation_state["evidence_ids"])
        self.assertEqual(self.staged(ctx), [])

    def test_a_precedent_judged_not_to_apply_is_ignored(self) -> None:
        # covers: DK-300e-2-i
        self.params["applies"] = 0.1
        _, ctx, waiting = self.goal("Where should the kernel file approved decisions?")
        self.assertEqual(waiting.requests[0].kind, RequestKind.EVIDENCE)
        self.assertEqual(waiting.evidence, [])
        notes = waiting.continuation_state["precedents"]
        self.assertEqual([(n["id"], n["action"]) for n in notes],
                         [(PRECEDENT_ID, "not_applicable")])
        self.assertEqual(waiting.decisions[0].precedent_ids, [])

    def test_an_applicable_precedent_below_the_reuse_threshold_is_evidence_only(self) -> None:
        # covers: DK-300a-2-i
        self.params["applies"] = 0.6
        _, _, waiting = self.goal()
        self.assertEqual(waiting.requests[0].kind, RequestKind.EVIDENCE)  # still grounds first
        self.assertEqual(len(waiting.evidence), 1)
        self.assertIn(waiting.evidence[0].id, waiting.continuation_state["evidence_ids"])

    def test_a_superseded_precedent_is_never_offered_for_reuse(self) -> None:
        # covers: DK-300e-3-iii
        newer = make_record(id="dec-3333333333333333", supersedes=[PRECEDENT_ID],
                            question="Something about animals and trees?")
        self.write(newer)
        _, _, waiting = self.goal()
        self.assertEqual(waiting.requests[0].kind, RequestKind.EVIDENCE)  # evidence, no reuse offer
        self.assertEqual(len(waiting.evidence), 1)

    def test_no_matching_record_means_no_jev_call_for_precedent(self) -> None:
        self.params["applies"] = 0.99
        _, _, waiting = self.goal("Should the pricing page use a carousel?")
        self.assertEqual(self.jev.questions_asked("decision.precedent"), [])
        self.assertEqual(waiting.requests[0].kind, RequestKind.EVIDENCE)

    def test_memory_off_changes_nothing(self) -> None:
        ctx = replace(self.ctx(), memory=FileColonyMemory(self.root / "nowhere", self.root / "r"))
        inv = invocation(DECISION, schema_ids.GOAL_REQUEST, {"goal": QUESTION})
        waiting = self.run_decision(inv, ctx)
        self.assertEqual(waiting.requests[0].kind, RequestKind.EVIDENCE)
        self.assertEqual(self.jev.call_count, 0)

    def test_an_exhausted_budget_skips_the_precedent_instead_of_blocking(self) -> None:
        ctx = self.ctx(budget=RefusingBudget())
        inv = invocation(DECISION, schema_ids.GOAL_REQUEST, {"goal": QUESTION})
        waiting = self.run_decision(inv, ctx)
        self.assertEqual(waiting.status, ResultStatus.WAITING)
        self.assertEqual(waiting.requests[0].kind, RequestKind.EVIDENCE)
        self.assertTrue(any("precedent was not judged" in x for x in waiting.limitations))

    def test_a_precedent_deleted_before_the_answer_falls_back_to_deciding_anew(self) -> None:
        # covers: DK-300e-4
        inv, ctx, waiting = self.goal()
        (self.folder / f"{PRECEDENT_ID}.yaml").unlink()
        again = self.answer(inv, ctx, waiting, {"choice_id": "reuse"})
        self.assertEqual(again.status, ResultStatus.WAITING)
        self.assertEqual(again.requests[0].kind, RequestKind.EVIDENCE)  # decided anew, normally
        self.assertTrue(any("no longer in the store" in x for x in again.limitations))


class TestPrecedentInTheAssessBatch(PrecedentCase):
    """With options and criteria in hand the questions ride the one assessment call."""

    def test_the_precedent_question_rides_the_assess_batch_without_an_extra_call(self) -> None:
        self.params["satisfies"] = {("c1", "A"): 0.95, ("c2", "A"): 0.9}
        _, ctx, result = self.matching()
        self.assertEqual(self.jev.call_count, 1)
        self.assertEqual([b.purpose for b in self.jev.batches], ["decision.assess"])
        self.assertIn(f"precedent.{PRECEDENT_ID}", self.jev.questions_asked("decision.assess"))
        self.assertIn(PRECEDENT_ID, as_json(self.jev.batches[0].state)["precedents"])
        self.assertEqual(result.status, ResultStatus.COMPLETED)
        self.assertEqual(result.decisions[0].precedent_ids, [PRECEDENT_ID])
        self.assertEqual(len(result.evidence), 1)  # evidence for what follows, never a resolution

    def test_no_reuse_question_when_the_decision_has_options_of_its_own(self) -> None:
        # covers: DK-300c-1-i
        # covers: DK-300e-3-iv
        self.params["satisfies"] = {("c1", "A"): 0.95, ("c2", "A"): 0.9}
        _, _, result = self.matching()
        self.assertEqual(result.status, ResultStatus.COMPLETED)
        self.assertEqual(result.requests, [])
        self.assertEqual(self.staged(self.ctx()), [])  # resolved with no human: no record


class TestOnlyHumanApprovalStagesARecord(PrecedentCase, DesignCase):
    """A record exists only because a human approved a resolved decision."""

    def setUp(self) -> None:
        super().setUp()
        self.params.update(design={"c1"})
        self.inv, self.ctx_, self.waiting = self.start()

    def ctx(self, evidence=None):  # noqa: ANN001, ANN201
        return replace(DesignCase.ctx(self, evidence), memory=self.memory)

    def choose(self, actor: str):  # noqa: ANN201
        return self.answer(self.inv, self.ctx_, self.waiting, {"choice_id": "C"}, actor=actor)

    def test_a_humans_design_choice_stages_a_publishable_record(self) -> None:
        # covers: DK-300b-3
        # covers: DK-300c-1
        done = self.choose("human:ada")
        self.assertEqual(done.status, ResultStatus.COMPLETED)
        self.assertTrue(any(x.startswith("decision record staged:") for x in done.limitations))
        (record,) = self.staged(self.ctx_)
        self.assertEqual((record.id, record.selected_option_id, record.approval.approved_by),
                         (done.decisions[0].id, "C", "human:ada"))
        self.assertEqual(record.assessment.basis, "kernel_ranking")
        self.assertEqual(record.assessment.selected_rank, 2)
        self.assertEqual([r.option_id for r in record.assessment.ranking], ["B", "C", "A"])
        self.assertEqual(record.assessment.design_reason, "design_judgement")
        self.assertEqual(record.approval.approved_at[:4], "2026")
        self.assertEqual(record.provenance.template_version, "decision.assess@1")
        # the staged file is publishable as it stands (schema, vocabularies, links)
        target = self.root / "published"
        target.mkdir()
        (target / f"{PRECEDENT_ID}.yaml").write_text(dump_record(make_record()), encoding="utf-8",
                                                     newline="\n")
        (target / f"{record.id}.yaml").write_text(dump_record(record), encoding="utf-8",
                                                  newline="\n")
        rebuild_index(target, schema(), vocabulary())
        report = validate_store(target, schema=schema(), vocab=vocabulary())
        self.assertTrue(report.ok, [p.as_dict() for p in report.problems])

    def test_a_bare_actor_id_is_filed_as_a_human_actor(self) -> None:
        # covers: DK-300c-1
        self.choose("tester")
        (record,) = self.staged(self.ctx_)
        self.assertEqual(record.approval.approved_by, "human:tester")

    def test_a_decision_a_host_approved_leaves_no_record(self) -> None:
        # covers: DK-300c-1-i
        done = self.choose("host:fake")
        self.assertEqual(done.status, ResultStatus.COMPLETED)
        self.assertFalse(any(x.startswith("decision record staged:") for x in done.limitations))
        self.assertEqual(self.staged(self.ctx_), [])

    def test_an_unanswered_decision_leaves_no_record(self) -> None:
        self.assertEqual(self.staged(self.ctx_), [])


class TestRecordsOfOtherApprovalPaths(PrecedentCase):
    """The resolved-gate path stages only when a human approved the decision."""

    def test_a_required_human_approval_stages_a_record_for_that_human(self) -> None:
        # covers: DK-300c-1
        self.params["satisfies"] = {("c1", "A"): 0.95}
        self.params["applies"] = 0.05
        inv, ctx, waiting = self.matching(approval_required=True)
        self.assertEqual(self.staged(ctx), [])
        done = self.answer(inv, ctx, waiting, {"choice_id": "approve"}, actor="human:ada")
        self.assertEqual(done.status, ResultStatus.COMPLETED)
        (record,) = self.staged(ctx)
        self.assertEqual((record.approval.approved_by, record.assessment.basis),
                         ("human:ada", "resolved_gate"))
        self.assertEqual(record.selected_option_id, "A")
        self.assertEqual([n.action for n in record.precedents_considered], ["not_applicable"])


if __name__ == "__main__":
    import unittest

    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: A precedent-only decision now requests the grounding research first
#   (the old assertions encoded the defect: options without repository evidence).
#   (#KernelPrecedentSkipsGrounding)
# - 2026-10-01 [python-coder]: Every authority rule has a test: a precedent resolves nothing alone,
#   reuse is approved by the CURRENT human, a host approver or an unanswered decision leaves no
#   record, and staging never touches the repository's store. (#KernelDecisionStore)
# ====================================================================
