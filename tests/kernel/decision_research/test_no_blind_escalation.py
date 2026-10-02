"""
MODULE: tests.kernel.decision_research.test_no_blind_escalation
GOAL: combine never hands a human the blind `unidentified_gap` escalation while research targets
    are open or while the options can be ranked; and unresolved feasibility becomes a gap.
BUSINESS CONTEXT: Live run run-1dec9568f85745e4 escalated "missing knowledge is not identified"
    with zero research rounds, three synthesis gaps and no ranking (ADR-053 section 8).
ARCHITECTURE: combine is a pure function, driven directly with a Working and an Assessment;
    the loading seam is driven through loading._absorb_options with a payload built by the real
    OptionsPayload serializer.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from kernel.capabilities.decision.assess import NONE_CHOICE, Assessment
from kernel.capabilities.decision.combine import combine
from kernel.capabilities.decision.loading import MAX_GAPS_KEPT, _absorb_options
from kernel.capabilities.decision.design_ending import choice_rationale, design_followup
from kernel.capabilities.decision.ranking import (
    DESIGN_ROUND,
    NO_RESEARCH_TARGETS,
    RESEARCH_CAP,
    research_rounds,
)
from kernel.capabilities.decision.state import DecisionContinuation, Working
from kernel.config import load_kernel_config
from kernel.contracts.decision import Criterion, Option
from kernel.contracts.enums import DecisionStatus
from kernel.contracts.payloads import OptionsPayload
from kernel.providers.base import ChoiceAnswer
from tests.kernel.capabilities.support import evidence_item

CFG = load_kernel_config().decision
OPTS = [Option(id="A", title="Alpha"), Option(id="B", title="Beta")]
CRIT = [Criterion(id="c1", question="Does it reuse existing conventions?")]
BASIS = evidence_item("docs/adr/1.md#L1-L2", "A recorded decision.")


def _work(*, gaps=(), requested=(), options=OPTS, criteria=CRIT) -> Working:  # noqa: ANN001
    cont = DecisionContinuation(gaps=list(gaps), requested=list(requested))
    return Working(question="Q?", cont=cont, options=list(options), criteria=list(criteria),
                   approval_required=False, constraint_ids=[], evidence=[BASIS])


def _assess(work: Working, sufficient: float = 0.72) -> Assessment:
    """Jev names no missing-knowledge kind; flat, uncertain satisfies scores."""
    return Assessment(
        sufficient={c.id: sufficient for c in work.usable_criteria},
        satisfies={(c.id, o.id): 0.5 for c in work.usable_criteria for o in work.usable_options},
        sufficient_confidence={c.id: None for c in work.usable_criteria},
        satisfies_confidence={(c.id, o.id): None for c in work.usable_criteria
                              for o in work.usable_options},
        missing=ChoiceAnswer(choice=NONE_CHOICE, probabilities={NONE_CHOICE: 1.0}),
        design={}, preference=0.0, conflict=0.0, result=MagicMock())


class TestNoBlindEscalation(unittest.TestCase):
    """The unidentified_gap branch of combine."""

    def test_open_targets_and_no_round_yet_runs_the_research_round(self) -> None:
        # covers: UNKNOWN
        # angle: criterion
        work = _work(gaps=["gap one", "gap two", "gap three"])
        v = combine(work, _assess(work), CFG)
        self.assertEqual(v.status, DecisionStatus.NEEDS_EVIDENCE)
        self.assertEqual(v.reason, DESIGN_ROUND)

    def test_rounds_exhausted_hands_the_human_a_ranked_question(self) -> None:
        # covers: UNKNOWN
        # angle: discrimination
        requested = [f"research:r{i}" for i in range(CFG.max_research_rounds)]
        work = _work(gaps=["gap one"], requested=requested)
        v = combine(work, _assess(work), CFG)
        self.assertEqual(v.status, DecisionStatus.NEEDS_HUMAN)
        self.assertNotEqual(v.reason, "unidentified_gap")
        self.assertEqual({r.option_id for r in v.ranking}, {"A", "B"})

    def test_design_round_already_done_ranks_instead_of_blind_gap(self) -> None:
        # covers: UNKNOWN
        # angle: boundary
        work = _work(gaps=["gap one"], requested=[f"research:x:{DESIGN_ROUND}"])
        v = combine(work, _assess(work), CFG)
        self.assertEqual(v.status, DecisionStatus.NEEDS_HUMAN)
        self.assertTrue(v.ranking)

    def test_no_targets_below_the_cap_names_no_research_targets_not_the_cap(self) -> None:
        # covers: UNKNOWN
        # angle: discrimination
        work = _work()  # no gaps, no added options, no uncited files: nothing to research
        self.assertEqual(research_rounds(work), 0)
        v = combine(work, _assess(work), CFG)
        self.assertEqual(v.status, DecisionStatus.NEEDS_HUMAN)
        self.assertEqual(v.reason, NO_RESEARCH_TARGETS)
        self.assertNotEqual(v.reason, RESEARCH_CAP)
        question = design_followup(work, v.reason, v.ranking, CFG).request.question
        self.assertIn("No research round is due", question)
        self.assertNotIn("limit", question)
        work.cont = work.cont.model_copy(update={
            "design_reason": v.reason, "design_ranking": v.ranking, "design_choice_id": "A"})
        rationale = choice_rationale(work)
        self.assertIn("because no_research_targets after 0 research round(s)", rationale)
        self.assertNotIn("research_cap", rationale)

    def test_no_targets_at_the_cap_still_reports_research_cap(self) -> None:
        # covers: UNKNOWN
        # angle: boundary
        requested = [f"research:r{i}" for i in range(CFG.max_research_rounds)]
        work = _work(requested=requested)  # no targets, but the cap really was reached
        v = combine(work, _assess(work), CFG)
        self.assertEqual(v.status, DecisionStatus.NEEDS_HUMAN)
        self.assertEqual(v.reason, RESEARCH_CAP)

    def test_nothing_rankable_keeps_unidentified_gap(self) -> None:
        # covers: UNKNOWN
        # angle: boundary
        work = _work(options=[])
        v = combine(work, _assess(work), CFG)
        self.assertEqual(v.status, DecisionStatus.NEEDS_HUMAN)
        self.assertEqual(v.reason, "unidentified_gap")
        self.assertFalse(v.ranking)


class TestUnresolvedFeasibilityBecomesGaps(unittest.TestCase):
    """loading._absorb_options feeds unresolved_feasibility into cont.gaps."""

    def test_unresolved_feasibility_lands_in_cont_gaps(self) -> None:
        # covers: UNKNOWN
        # angle: seam
        payload = OptionsPayload(unresolved_feasibility=["repo fact one", "repo fact two"]
                                 ).model_dump(mode="json")
        work = _work()
        _absorb_options(work, payload)
        self.assertEqual(work.cont.gaps, ["repo fact one", "repo fact two"])

    def test_gaps_are_bounded_and_deduplicated(self) -> None:
        # covers: UNKNOWN
        # angle: boundary
        items = [f"fact {i}" for i in range(MAX_GAPS_KEPT + 4)] + ["fact 0"]
        work = _work(gaps=["fact 0"])
        _absorb_options(work, OptionsPayload(unresolved_feasibility=items).model_dump(mode="json"))
        self.assertLessEqual(len(work.cont.gaps), MAX_GAPS_KEPT)
        self.assertEqual(len(work.cont.gaps), len(set(work.cont.gaps)))
        self.assertIn("fact 0", work.cont.gaps)
        self.assertIn("fact 1", work.cont.gaps)
