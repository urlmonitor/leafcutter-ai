"""
MODULE: tests.kernel.memory.test_decision_anew_correction
GOAL: Deciding anew after a precedent was offered, through the real DecisionExecutor with a real
    file memory: a different final choice stages a record that supersedes the precedent and whose
    publish instruction carries `--correct <old id>`; the same choice supersedes nothing and adds
    no `--correct`.
BUSINESS CONTEXT: DK-600e-3-i. The person who publishes should not have to add the correction
    by hand; the precedent's own record stays untouched until publishing.
ARCHITECTURE: Reuses PrecedentCase from test_decision_precedent (store, scripted Jev, resume
    helpers); split out so that module stays under the file-size limit.
"""

from __future__ import annotations

from dataclasses import replace

from kernel.contracts import ProposalStatus, schema_ids
from kernel.contracts.decision import Criterion, Option
from kernel.contracts.enums import ApprovalStatus, EvidenceCategory, RequestKind, ResultStatus
from kernel.contracts.payloads import OptionsPayload
from tests.kernel.capabilities.support import child, evidence_item, resume
from tests.kernel.memory.test_decision_precedent import PRECEDENT_ID, PrecedentCase


class TestDecidingAnewCarriesTheCorrection(PrecedentCase):
    """A decide-anew run that ends on another option tells the publisher to correct the old one."""

    def _decide_anew_and_choose(self, option_title: str):  # noqa: ANN202
        """Decide anew, then drive the normal flow to a human-approved choice of `option_title`."""
        inv, ctx, waiting = self.goal()
        ctx_evidence = [*self.evidence, *waiting.evidence]
        again = self.answer(inv, ctx, waiting, {"choice_id": "decide_anew"})
        self.assertEqual(again.requests[0].kind, RequestKind.EVIDENCE)
        extra = evidence_item("docs/more.md#L1-L2", "Another fact.",
                              EvidenceCategory.INTERNAL_PRINCIPLES)
        ctx = replace(ctx, evidence_lookup=self.ctx([*ctx_evidence, *again.evidence, extra])
                      .evidence_lookup)
        bundle = child(ctx, RequestKind.EVIDENCE, schema_ids.EVIDENCE_BUNDLE,
                       {"evidence_ids": [extra.id]})
        asked = self.run_decision(resume(inv, again, [bundle]), ctx)
        self.assertEqual(asked.requests[0].kind, RequestKind.OPTIONS)
        proposals = OptionsPayload(
            options=[Option(id="opt.new", title=option_title,
                            proposal_status=ProposalStatus.PROPOSED,
                            approval_status=ApprovalStatus.PROPOSED, proposed_by="host")],
            proposed_criteria=[Criterion(id="p1", question="Is it reviewable?",
                                         proposal_status=ProposalStatus.PROPOSED,
                                         approval_status=ApprovalStatus.PROPOSED,
                                         proposed_by="host")])
        out = child(ctx, RequestKind.OPTIONS, schema_ids.OPTIONS, proposals.model_dump(mode="json"))
        approval = self.run_decision(resume(inv, asked, [out]), ctx)
        self.assertEqual(approval.continuation_state["phase"], "awaiting_approval")
        self.params["satisfies"] = {("p1", "opt.new"): 0.95}
        ok = child(ctx, RequestKind.HUMAN, schema_ids.HUMAN_ANSWER, {"choice_id": "approve"})
        ok = ok.model_copy(update={"actor_id": "human:ada"})
        done = self.run_decision(resume(inv, approval, [ok]), ctx)
        return ctx, done

    def test_deciding_anew_differently_stages_a_superseding_record_with_a_correct_command(
            self) -> None:
        # covers: DK-600e-3-i
        # angle: criterion
        before = (self.folder / f"{PRECEDENT_ID}.yaml").read_bytes()
        ctx, done = self._decide_anew_and_choose("One JSON file per component")
        self.assertEqual(done.status, ResultStatus.COMPLETED, done.limitations)
        (record,) = self.staged(ctx)
        self.assertEqual(record.selected_option_id, "opt.new")
        self.assertEqual(record.supersedes, [PRECEDENT_ID])
        self.assertEqual([(n.id, n.action) for n in record.precedents_considered],
                         [(PRECEDENT_ID, "set_aside")])
        (note,) = [x for x in done.limitations if x.startswith("decision record staged:")]
        self.assertIn(f"decisions publish --run-id {ctx.run_id}", note)
        self.assertIn(f"--correct {PRECEDENT_ID}", note)  # fails today: no --correct is carried
        self.assertEqual((self.folder / f"{PRECEDENT_ID}.yaml").read_bytes(), before)

    def test_deciding_anew_to_the_same_option_supersedes_nothing_and_adds_no_correct(self) -> None:
        # covers: DK-600e-3-i
        # angle: discrimination
        ctx, done = self._decide_anew_and_choose("One YAML file per decision")
        self.assertEqual(done.status, ResultStatus.COMPLETED, done.limitations)
        (record,) = self.staged(ctx)
        self.assertEqual(record.supersedes, [])
        (note,) = [x for x in done.limitations if x.startswith("decision record staged:")]
        self.assertNotIn("--correct", note)
