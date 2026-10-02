"""
MODULE: tests.kernel.grounding.test_decision_grounding
GOAL: Behavioural tests of option grounding: a decision with unknown options researches the
    option space first, asks the host for options WITH that evidence, and refuses or flags
    options that cite none of it; the decision keeps one stable id.
BUSINESS CONTEXT: Live runs showed a host inventing options it could not ground (it had no
    repository access and the packet carried no evidence) and a human being asked to approve
    them (Rev 3 sections 10.1 and 10.4, G1 of the grounding findings).
ARCHITECTURE: Drives the real DecisionExecutor and the real host operation conversion with
    ScriptedJev; the kernel resume step is simulated by tests.kernel.capabilities.support.
"""

from __future__ import annotations

import unittest

from kernel.capabilities.decision.requests import GROUNDING_CATEGORIES
from kernel.capabilities.host import host_operation
from kernel.config import load_kernel_config
from kernel.contracts import ApprovalStatus, ProposalStatus, schema_ids
from kernel.contracts.decision import Option
from kernel.contracts.enums import EvidenceCategory, RequestKind, ResultStatus
from kernel.contracts.evidence import EvidenceBundlePayload
from kernel.contracts.payloads import (
    GoalRequestPayload,
    HumanQuestionRequestPayload,
    OptionsPayload,
    OptionsRequestPayload,
    ResearchRequestPayload,
)
from tests.kernel.capabilities.host_support import conversion, option
from tests.kernel.capabilities.support import child, evidence_item, invocation, resume
from tests.kernel.capabilities.test_decision_graph import DECISION, DecisionTestCase
from tests.kernel.helpers import make_context, narrow

GOAL = "Decide which acceptance criterion is most critical to implement next."
EV = "ev-aaaaaaaaaaaaaaaa"


def _config(**decision: object):
    """Default config with decision-section overrides."""
    base = load_kernel_config()
    return base.model_copy(update={"decision": base.decision.model_copy(update=decision)})


class GroundingTestCase(DecisionTestCase):
    """A goal-only decision whose evidence list starts empty."""

    def setUp(self) -> None:
        super().setUp()
        self.evidence = []
        self.ac = evidence_item("docs/acceptance-criteria/AC-1.yaml#L1-L9",
                                "id: AC-1\ncriterion: audit trail\n",
                                EvidenceCategory.TASK_CONTEXT)

    def goal_invocation(self):
        payload = GoalRequestPayload(goal=GOAL).model_dump()
        return invocation(DECISION, schema_ids.GOAL_REQUEST, payload)

    def researched(self, cfg=None):
        """Run to the research request, answer it with one AC evidence item, resume."""
        ctx = make_context(self.root, jev=self.jev, config=cfg, evidence=[self.ac])
        inv = self.goal_invocation()
        asked = self.run_decision(inv, ctx)
        bundle = EvidenceBundlePayload(evidence_ids=[self.ac.id], evidence=[self.ac])
        out = child(ctx, RequestKind.EVIDENCE, schema_ids.EVIDENCE_BUNDLE,
                    bundle.model_dump(mode="json"))
        return inv, ctx, asked, self.run_decision(resume(inv, asked, [out]), ctx)

    def empty_research(self, cfg=None):
        """Run to the research request and answer it with an empty bundle."""
        ctx = make_context(self.root, jev=self.jev, config=cfg)
        inv = self.goal_invocation()
        asked = self.run_decision(inv, ctx)
        empty = child(ctx, RequestKind.EVIDENCE, schema_ids.EVIDENCE_BUNDLE,
                      EvidenceBundlePayload().model_dump(mode="json"))
        return self.run_decision(resume(inv, asked, [empty]), ctx)


class TestGroundingFlow(GroundingTestCase):
    """Unknown options: research first, then options with the evidence attached."""

    def test_unknown_options_first_ask_for_research_not_for_options(self) -> None:
        # covers: DK-100a-2
        ctx = make_context(self.root, jev=self.jev)
        asked = self.run_decision(self.goal_invocation(), ctx)
        self.assertEqual(asked.status, ResultStatus.WAITING)
        self.assertEqual([r.kind for r in asked.requests], [RequestKind.EVIDENCE])
        body = ResearchRequestPayload.model_validate(asked.requests[0].payload)
        self.assertEqual({n.category for n in body.evidence_needs}, set(GROUNDING_CATEGORIES))
        self.assertEqual(self.jev.call_count, 0)

    def test_the_options_request_carries_the_researched_evidence(self) -> None:
        # covers: DK-100a-2
        _, _, _, after = self.researched()
        self.assertEqual(after.status, ResultStatus.WAITING)
        request = after.requests[0]
        self.assertEqual(request.kind, RequestKind.OPTIONS)
        body = OptionsRequestPayload.model_validate(request.payload)
        self.assertEqual(body.evidence_ids, [self.ac.id])
        self.assertTrue(body.require_grounding)

    def test_research_is_asked_only_once(self) -> None:
        inv, ctx, _, after = self.researched()
        again = self.run_decision(resume(inv, after, []), ctx)
        self.assertNotEqual([r.kind for r in again.requests], [RequestKind.EVIDENCE])

    def test_no_evidence_found_blocks_when_grounding_is_required(self) -> None:
        done = self.empty_research()
        self.assertEqual(done.status, ResultStatus.BLOCKED)
        self.assertEqual(done.error.code, "options_ungrounded")

    def test_no_evidence_is_only_a_limitation_when_grounding_is_not_required(self) -> None:
        done = self.empty_research(_config(require_option_grounding=False))
        self.assertEqual(done.requests[0].kind, RequestKind.OPTIONS)
        self.assertTrue(any("ground" in text for text in done.limitations))

    def test_supplied_evidence_skips_the_grounding_research(self) -> None:
        self.evidence = [self.ac]
        _, _, result = self.first(options=False)
        self.assertEqual(result.requests[0].kind, RequestKind.OPTIONS)


class TestGroundedConversion(unittest.TestCase):
    """host.generate_options keeps only options that cite the supplied evidence."""

    def _convert(self, options: list[dict], **request: object):
        body = {"problem": "Which AC?", "max_options": 5, "propose_criteria": False,
                "evidence_ids": [EV], "require_grounding": False, **request}
        ctx = conversion("host.generate_options", body, {"options": options})
        result = narrow(host_operation("host.generate_options")).convert(ctx)
        return result, OptionsPayload.model_validate(result.output_payload)

    def test_a_cited_option_keeps_its_reference(self) -> None:
        _, payload = self._convert([option("a", source_refs=[EV])])
        self.assertEqual(payload.options[0].source_refs, [EV])

    def test_unknown_references_are_dropped_and_flagged(self) -> None:
        result, payload = self._convert([option("a", source_refs=["ev-bbbbbbbbbbbbbbbb"])])
        self.assertEqual(payload.options[0].source_refs, [])
        self.assertTrue(any("not grounded" in t for t in result.limitations))

    def test_an_ungrounded_option_is_flagged_when_grounding_is_optional(self) -> None:
        result, payload = self._convert([option("a")])
        self.assertEqual([o.id for o in payload.options], ["a"])
        self.assertTrue(any("not grounded" in t and "a" in t for t in result.limitations))

    def test_an_ungrounded_option_is_refused_when_grounding_is_required(self) -> None:
        result, payload = self._convert(
            [option("a"), option("b", source_refs=[EV])], require_grounding=True)
        self.assertEqual([o.id for o in payload.options], ["b"])
        self.assertTrue(any("refused" in t for t in result.limitations))

    def test_the_packet_says_to_cite_evidence_and_grants_no_repository_access(self) -> None:
        op = host_operation("host.generate_options")
        request = OptionsRequestPayload(problem="p", evidence_ids=[EV], require_grounding=True)
        text = " ".join(narrow(op).requirements(request))
        self.assertIn("source_refs", text)
        self.assertIn("no repository access", text)


class TestDecisionIdentity(GroundingTestCase):
    """One decision record, and its id reaches the approval question."""

    def test_every_waiting_result_names_the_same_decision(self) -> None:
        _, _, asked, after = self.researched()
        ids = {asked.decisions[0].id, after.decisions[0].id}
        self.assertEqual(len(ids), 1)

    def test_the_approval_question_carries_the_decision_id(self) -> None:
        inv, ctx, _, after = self.researched()
        proposed = OptionsPayload(
            options=[Option(id="a", title="Audit trail", proposal_status=ProposalStatus("proposed"),
                            approval_status=ApprovalStatus("proposed"), source_refs=[self.ac.id])],
            proposed_criteria=[]).model_dump(mode="json")
        opts = child(ctx, RequestKind.OPTIONS, schema_ids.OPTIONS, proposed)
        approval = self.run_decision(resume(inv, after, [opts]), ctx)
        question = approval.requests[0]
        self.assertEqual(question.kind, RequestKind.HUMAN)
        body = HumanQuestionRequestPayload.model_validate(question.payload)
        self.assertEqual(body.decision_id, approval.decisions[0].id)
        self.assertIn(self.ac.id, body.question)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 23:00 [python-coder]: Tests for G1 written first and seen failing.
#   (#KernelBootstrapV0/GROUND)
# ====================================================================
