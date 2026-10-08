"""
MODULE: tests.kernel.decision_research.test_synthesis_on_coverage
GOAL: Behavioural tests of N2: research hands its evidence to the host for synthesis when the
    COVERAGE is thin (a planned need partial, open or unanswered, or no need satisfied), not only
    when Jev's `evaluable` answer is low, and does so within the work-item budget.
BUSINESS CONTEXT: The same goal flipped between "9 findings" (evaluable 0.68) and "no findings"
    (0.78) while no need was satisfied either time; the synthesis that finds the gaps the next
    research round aims at was a coin flip of one probability.
ARCHITECTURE: ResearchExecutor driven through plan, child bundles and resume with ScriptedJev
    (the rig of test_research_graph); each test changes one thing: a need's coverage, an answer
    judgement, `evaluable`, the config switch or the budget.
"""

from __future__ import annotations

from dataclasses import replace

from kernel.config import load_kernel_config
from kernel.contracts import schema_ids
from kernel.contracts.enums import EvidenceCategory, NeedStatus, RequestKind, ResultStatus
from kernel.contracts.payloads import SynthesisRequestPayload
from kernel.scheduler.nodes_execute import ShareBudget
from tests.kernel.capabilities.support import child, evidence_item, resume
from tests.kernel.capabilities.test_research_graph import ResearchCase, _bundle

CATS = EvidenceCategory


class ThinCoverageCase(ResearchCase):
    """Plan two needs; hand back one bundle each with the coverage a test chooses."""

    def setUp(self) -> None:
        super().setUp()
        self.ctx_ = self.ctx()
        self.inv = self.goal()
        self.waiting = self.run_research(self.inv, self.ctx_)
        self.ev_a = evidence_item("docs/a.md#L1-L2", "Use sqlite.")
        self.ev_b = evidence_item("CLAUDE.md#L1-L1", "Roll back.", CATS.INTERNAL_PRINCIPLES)

    def kids(self, a: NeedStatus = NeedStatus.SATISFIED, b: NeedStatus = NeedStatus.SATISFIED,
             items: bool = True):
        """Child bundles for the two planned needs with the given coverage."""
        give_a, give_b = ([self.ev_a], [self.ev_b]) if items else ([], [])
        return [child(self.ctx_, RequestKind.EVIDENCE, schema_ids.EVIDENCE_BUNDLE,
                      _bundle(give_a, {"need.prior_decisions": a})),
                child(self.ctx_, RequestKind.EVIDENCE, schema_ids.EVIDENCE_BUNDLE,
                      _bundle(give_b, {"need.internal_principles": b}))]

    def resumed(self, kids, ctx=None):  # noqa: ANN001, ANN201
        return self.run_research(resume(self.inv, self.waiting, kids), ctx or self.ctx_)

    def assert_asks_for_synthesis(self, result) -> None:  # noqa: ANN001
        self.assertEqual(result.status, ResultStatus.WAITING)
        self.assertEqual(result.requests[0].kind, RequestKind.SYNTHESIS)
        body = SynthesisRequestPayload.model_validate(result.requests[0].payload)
        self.assertTrue(body.evidence_ids)


class TestThinCoverageAsksForSynthesis(ThinCoverageCase):
    """Evaluable is high in every test below: only the coverage can ask for the synthesis."""

    def test_a_partial_need_asks_for_a_synthesis(self) -> None:
        self.assertGreater(self.params["evaluable"], 0.9)
        self.assert_asks_for_synthesis(self.resumed(self.kids(b=NeedStatus.PARTIAL)))

    def test_an_open_need_asks_for_a_synthesis(self) -> None:
        self.assert_asks_for_synthesis(self.resumed(self.kids(b=NeedStatus.OPEN)))

    def test_no_satisfied_need_asks_for_a_synthesis(self) -> None:
        self.assert_asks_for_synthesis(self.resumed(
            self.kids(a=NeedStatus.PARTIAL, b=NeedStatus.PARTIAL)))

    def test_a_need_the_evidence_does_not_answer_asks_for_a_synthesis(self) -> None:
        self.params["answer_by_need"] = {"need.prior_decisions": 0.1}  # satisfied by topic only
        asked = self.resumed(self.kids())
        self.assert_asks_for_synthesis(asked)
        self.assertEqual(asked.continuation_state["unanswered"], ["need.prior_decisions"])

    def test_the_same_coverage_gives_the_same_answer_whatever_evaluable_says(self) -> None:
        results = []
        for evaluable in (0.68, 0.78):  # the two values the live run flipped between
            self.params["evaluable"] = evaluable
            results.append(self.resumed(self.kids(b=NeedStatus.PARTIAL)).requests[0].kind)
        self.assertEqual(results, [RequestKind.SYNTHESIS, RequestKind.SYNTHESIS])


class TestSatisfiedCoverageStillNeedsNoSynthesis(ThinCoverageCase):
    """What worked before keeps working: enough evidence that answers is not synthesized."""

    def test_every_need_satisfied_and_evaluable_completes(self) -> None:
        done = self.resumed(self.kids())
        self.assertEqual(done.status, ResultStatus.COMPLETED)
        self.assertEqual(done.requests, [])

    def test_a_low_evaluable_alone_still_asks_for_a_synthesis(self) -> None:
        self.params["evaluable"] = 0.3
        self.assert_asks_for_synthesis(self.resumed(self.kids()))

    def test_without_evidence_there_is_nothing_to_synthesize(self) -> None:
        done = self.resumed(self.kids(NeedStatus.OPEN, NeedStatus.OPEN, items=False))
        self.assertEqual(done.requests, [])
        self.assertNotEqual(done.status, ResultStatus.WAITING)


class TestSwitchesAndBudget(ThinCoverageCase):
    """The config switch and the work-item budget decide whether the synthesis may be asked."""

    def test_allow_synthesis_off_never_asks(self) -> None:
        base = load_kernel_config()
        off = base.model_copy(update={"research": base.research.model_copy(
            update={"allow_synthesis": False})})
        done = self.resumed(self.kids(b=NeedStatus.PARTIAL), replace(self.ctx_, config=off))
        self.assertEqual(done.requests, [])

    def test_a_synthesis_resume_finishes_without_asking_again(self) -> None:
        asked = self.resumed(self.kids(b=NeedStatus.PARTIAL))
        findings = child(self.ctx_, RequestKind.SYNTHESIS, schema_ids.FINDINGS,
                         {"findings": [], "unknowns": ["the second need found nothing"]})
        done = self.run_research(resume(self.inv, asked, [findings]), self.ctx_)
        self.assertEqual(done.requests, [])
        self.assertNotEqual(done.status, ResultStatus.WAITING)

    def test_no_work_item_left_ends_with_a_limitation_instead_of_a_synthesis(self) -> None:
        ctx = replace(self.ctx_, budget=ShareBudget({"jev": 40, "work_item": 0}))
        done = self.resumed(self.kids(b=NeedStatus.PARTIAL), ctx)
        self.assertEqual(done.requests, [])
        self.assertTrue(any("no room for a synthesis" in x for x in self.bundle(done).limitations))

    def test_a_work_item_left_allows_the_synthesis(self) -> None:
        ctx = replace(self.ctx_, budget=ShareBudget({"jev": 40, "work_item": 3}))
        self.assert_asks_for_synthesis(self.resumed(self.kids(b=NeedStatus.PARTIAL), ctx))


if __name__ == "__main__":
    import unittest

    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Round F tests for synthesis on coverage (N2): a partial, open or
#   unanswered need, or no satisfied need, asks the host to synthesize whatever `evaluable`
#   says; satisfied evidence that Jev can evaluate does not; the switch and the work-item budget
#   can stop it. (#KernelV01/F)
# ====================================================================
