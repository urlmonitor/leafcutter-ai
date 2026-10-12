"""
MODULE: tests.kernel.grounding.test_answer_aware_coverage
GOAL: Behavioural tests of answer-aware coverage: a need stays `satisfied` only when Jev judges
    that the kept evidence answers the need's question (one literal noul per need, in the
    existing research.assess batch); topic match alone gives `partial` with a limitation.
BUSINESS CONTEXT: A live run asked "how are decisions stored today?" and `prior_decisions` was
    reported satisfied by aspirational colony-memory documents: the topic matched, the question
    was not answered, and the bundle invited a false answer (Rev 3 sections 9.4 and 10.2).
ARCHITECTURE: ResearchExecutor driven through plan, child bundles and resume with ScriptedJev;
    the answer probability per need comes from the mutable `params` of the research rig.
"""

from __future__ import annotations

from typing import Any

from kernel.config import KernelConfig, load_kernel_config
from kernel.contracts import schema_ids
from kernel.contracts.enums import EvidenceCategory, NeedStatus, RequestKind, ResultStatus
from kernel.contracts.evidence import Evidence
from tests.kernel.capabilities.support import child, evidence_item, resume
from tests.kernel.capabilities.test_research_graph import ResearchCase, _bundle
from tests.kernel.helpers import as_json

CATS = EvidenceCategory
TODAY = "how are decisions stored today"


def _judged(item: Evidence, relevance: float) -> Evidence:
    """Return the evidence with a judged relevance (what native retrieval records)."""
    return item.model_copy(update={
        "provenance": item.provenance.model_copy(update={"relevance": relevance})})


def _config(**research: Any) -> KernelConfig:
    """Return the default config with research overrides (no synthesis unless asked for).

    These tests are about the coverage a bundle reports; a partial need asks for a host synthesis
    since round F (tests/kernel/decision_research), which they do not want to answer.
    """
    base = load_kernel_config()
    research.setdefault("allow_synthesis", False)
    return base.model_copy(update={"research": base.research.model_copy(update=research)})


class AnswerCase(ResearchCase):
    """Plan two needs, hand back one bundle each and read what Jev was asked."""

    ev_a = _judged(evidence_item("docs/colony.md#L1-L5", "Decisions may one day live in Neo4j."),
                   0.9)
    ev_b = _judged(evidence_item("CLAUDE.md#L1-L1", "Roll back.", CATS.INTERNAL_PRINCIPLES), 0.9)

    def finish(self, config: KernelConfig | None = None, a: Evidence | None = None,
               b: Evidence | None = None, **params: Any):
        """Resume research with both needs reported satisfied; return (result, bundle)."""
        self.params.update(params)
        ctx = self.ctx(config)
        inv = self.goal(f"Explain {TODAY} in this project")
        waiting = self.run_research(inv, ctx)
        kids = [child(ctx, RequestKind.EVIDENCE, schema_ids.EVIDENCE_BUNDLE,
                      _bundle([a or self.ev_a], {"need.prior_decisions": NeedStatus.SATISFIED})),
                child(ctx, RequestKind.EVIDENCE, schema_ids.EVIDENCE_BUNDLE,
                      _bundle([b or self.ev_b], {"need.internal_principles":
                                                 NeedStatus.SATISFIED}))]
        done = self.run_research(resume(inv, waiting, kids), ctx)
        return done, self.bundle(done)


class TestAnswerJudgement(AnswerCase):
    """A topical hit that does not answer leaves the need partial."""

    def test_a_need_the_evidence_does_not_answer_is_partial_with_a_limitation(self) -> None:
        done, bundle = self.finish(_config(), answer_by_need={"need.prior_decisions": 0.15})
        self.assertEqual(bundle.coverage["need.prior_decisions"], NeedStatus.PARTIAL)
        self.assertEqual(bundle.coverage["need.internal_principles"], NeedStatus.SATISFIED)
        text = " ".join(bundle.limitations)
        self.assertIn("need.prior_decisions", text)
        self.assertIn("matched the topic but did not answer", text)
        self.assertEqual(done.status, ResultStatus.PARTIAL)  # a required need is not satisfied
        self.assertIn(self.ev_a.id, bundle.evidence_ids)  # kept as context, not dropped

    def test_a_need_the_evidence_answers_stays_satisfied(self) -> None:
        done, bundle = self.finish()
        self.assertEqual(set(bundle.coverage.values()), {NeedStatus.SATISFIED})
        self.assertEqual(done.status, ResultStatus.COMPLETED)
        self.assertNotIn("did not answer", " ".join(bundle.limitations))

    def test_the_answer_threshold_comes_from_config(self) -> None:
        for threshold, expected in ((0.6, NeedStatus.SATISFIED), (0.7, NeedStatus.PARTIAL)):
            with self.subTest(threshold=threshold):
                _, bundle = self.finish(_config(answer_threshold=threshold),
                                        answer_by_need={"need.prior_decisions": 0.65})
                self.assertEqual(bundle.coverage["need.prior_decisions"], expected)

    def test_the_switch_turns_the_judgement_off(self) -> None:
        _, bundle = self.finish(_config(answer_aware_coverage=False),
                                answer_by_need={"need.prior_decisions": 0.0})
        self.assertEqual(bundle.coverage["need.prior_decisions"], NeedStatus.SATISFIED)
        self.assertFalse([q for q in self.jev.questions_asked() if q.startswith("answers.")])


class TestAnswerQuestions(AnswerCase):
    """One literal noul per satisfied need, quoted as state, in the existing batch."""

    def test_one_noul_per_satisfied_need_rides_the_existing_assess_batch(self) -> None:
        self.finish()
        assess = [b for b in self.jev.batches if b.purpose == "research.assess"]
        self.assertEqual(len(assess), 1)  # no extra Jev call
        ids = [q.id for q in assess[0].questions]
        self.assertEqual(sorted(i for i in ids if i.startswith("answers.")),
                         ["answers.need.internal_principles", "answers.need.prior_decisions"])
        self.assertIn("evaluable", ids)
        self.assertEqual(self.jev.call_count, 2)  # plan_needs + assess, exactly as before

    def test_the_question_and_the_evidence_are_quoted_state_not_instructions(self) -> None:
        self.finish()
        batch = next(b for b in self.jev.batches if b.purpose == "research.assess")
        checks = as_json(batch.state)["answer_checks"]
        entry = checks["need.prior_decisions"]
        self.assertIn(TODAY, entry["question"])
        self.assertEqual(entry["evidence_ids"], [self.ev_a.id])
        asked = next(q for q in batch.questions if q.id == "answers.need.prior_decisions")
        self.assertNotIn(TODAY, asked.instructions)  # the need's text is data, not instruction
        self.assertIn("answer_checks.need.prior_decisions", asked.instructions)
        self.assertIn("today", asked.instructions)  # present state, not proposals or plans

    def test_only_evidence_that_passed_relevance_is_offered(self) -> None:
        weak = _judged(evidence_item("docs/weak.md#L1-L1", "Barely related."), 0.55)
        strong = _judged(evidence_item("docs/strong.md#L1-L1", "Stored in sqlite."), 0.9)
        self.finish(a=strong)
        self.finish(a=weak)  # nothing passes: the need is partial already, so it is not asked
        first, second = [b for b in self.jev.batches if b.purpose == "research.assess"]
        self.assertEqual(as_json(first.state)["answer_checks"]["need.prior_decisions"]["evidence_ids"],
                         [strong.id])
        self.assertNotIn("need.prior_decisions", as_json(second.state)["answer_checks"])

    def test_a_need_that_is_not_satisfied_is_not_asked(self) -> None:
        self.params["need"] = {"prior_decisions": 0.9, "internal_principles": 0.9}
        ctx = self.ctx()
        inv = self.goal()
        waiting = self.run_research(inv, ctx)
        kids = [child(ctx, RequestKind.EVIDENCE, schema_ids.EVIDENCE_BUNDLE,
                      _bundle([self.ev_a], {"need.prior_decisions": NeedStatus.PARTIAL})),
                child(ctx, RequestKind.EVIDENCE, schema_ids.EVIDENCE_BUNDLE,
                      _bundle([], {"need.internal_principles": NeedStatus.OPEN}))]
        self.run_research(resume(inv, waiting, kids), ctx)
        self.assertEqual([q for q in self.jev.questions_asked("research.assess")
                          if q.startswith("answers.")], [])

    def test_no_evidence_means_no_assess_call_at_all(self) -> None:
        ctx = self.ctx()
        inv = self.goal()
        waiting = self.run_research(inv, ctx)
        kids = [child(ctx, RequestKind.EVIDENCE, schema_ids.EVIDENCE_BUNDLE,
                      _bundle([], {"need.prior_decisions": NeedStatus.OPEN})),
                child(ctx, RequestKind.EVIDENCE, schema_ids.EVIDENCE_BUNDLE,
                      _bundle([], {"need.internal_principles": NeedStatus.OPEN}))]
        self.run_research(resume(inv, waiting, kids), ctx)
        self.assertEqual(self.jev.questions_asked("research.assess"), [])


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Tests for V0.1 wave 2 (targeted queries, answer-aware coverage).
#   (#KernelV01/D)
# ====================================================================
