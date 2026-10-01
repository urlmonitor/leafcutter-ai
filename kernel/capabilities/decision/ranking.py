"""
MODULE: kernel.capabilities.decision.ranking
GOAL: The deterministic pieces of the design-decision ending: the ranking of options by Jev's
    satisfies scores, the no-progress test between two assessments and the reasons to stop
    researching.
BUSINESS CONTEXT: Some criteria are properties of the proposed designs, so no amount of retrieval
    makes them sufficient. The live run `run-5d246775f5e54f11` looped through 18 Jev calls on
    such criteria. The decision then stops researching and ranks the options for a human; the
    ranking is evidence, the preference and authority stay with the human (ADR-053).
ARCHITECTURE: Pure functions of (Working, Assessment, DecisionConfig). Ranking aggregation, best
    first, is lexicographic: (1) required criteria passed at the satisfies threshold, (2) mean
    satisfies over required criteria, (3) mean satisfies over supporting criteria (means rounded
    to 4 decimals), (4) the order the options were declared in. Ties are therefore broken by
    declaration order only, never by a hidden weight.
"""

from __future__ import annotations

from kernel.capabilities.decision.assess import Assessment
from kernel.capabilities.decision.state import Working
from kernel.config import DecisionConfig
from kernel.contracts.decision import Criterion, CriterionKind, OptionRanking
from kernel.contracts.enums import Priority

DESIGN_JUDGEMENT = "design_judgement"
NO_PROGRESS = "no_progress"
RESEARCH_CAP = "research_cap"
DESIGN_REASONS = (DESIGN_JUDGEMENT, NO_PROGRESS, RESEARCH_CAP)
_ROUND = 4


def score_key(criterion_id: str, option_id: str | None = None) -> str:
    """Return the key of a sufficiency (no option) or satisfies score in the score maps."""
    return f"s|{criterion_id}" if option_id is None else f"q|{criterion_id}|{option_id}"


def current_scores(work: Working, a: Assessment) -> dict[str, float]:
    """Return every sufficiency and satisfies probability of the assessment, by score_key."""
    scores = {score_key(c.id): a.sufficient[c.id] for c in work.usable_criteria}
    for c in work.usable_criteria:
        for o in work.usable_options:
            scores[score_key(c.id, o.id)] = a.satisfies[(c.id, o.id)]
    return scores


def _mean(values: list[float]) -> float:
    """Return the mean rounded for a stable comparison."""
    return round(sum(values) / len(values), _ROUND) if values else 0.0


def rank_options(work: Working, a: Assessment, cfg: DecisionConfig) -> list[OptionRanking]:
    """Rank the usable options best first (see the module docstring for the aggregation)."""
    required = [c for c in work.usable_criteria if c.priority is Priority.REQUIRED]
    supporting = [c for c in work.usable_criteria if c.priority is not Priority.REQUIRED]
    rows = []
    for order, option in enumerate(work.usable_options):
        req = [a.satisfies[(c.id, option.id)] for c in required]
        sup = [a.satisfies[(c.id, option.id)] for c in supporting]
        passed = sum(p >= cfg.satisfies_threshold for p in req)
        rows.append((-passed, -_mean(req), -_mean(sup), order, option.id, passed, req, sup))
    rows.sort(key=lambda r: r[:4])
    return [OptionRanking(
        option_id=oid, rank=rank, required_passed=passed, required_total=len(required),
        required_mean=_mean(req), supporting_mean=_mean(sup) if sup else None,
        scores={c.id: a.satisfies[(c.id, oid)] for c in work.usable_criteria})
        for rank, (*_, oid, passed, req, sup) in enumerate(rows, start=1)]


def no_progress(work: Working, scores: dict[str, float], cfg: DecisionConfig) -> bool:
    """True if new evidence arrived since the last assessment yet no score moved materially.

    Comparable assessments only: the same options and criteria (the same score keys). A move of
    more than `progress_epsilon` in any sufficiency or satisfies score counts as progress.
    """
    prior = work.cont.last_scores
    if not prior or set(prior) != set(scores):
        return False
    if set(work.evidence_ids) == set(work.cont.last_scores_evidence):
        return False  # nothing new: the plain no-progress guard handles an identical request
    return max(abs(scores[k] - prior[k]) for k in scores) <= cfg.progress_epsilon


def research_rounds(work: Working) -> int:
    """Return how many research requests (needs-driven, not grounding) the decision has made."""
    return sum(key.startswith("research:") for key in work.cont.requested)


def required_by_kind(work: Working) -> tuple[list[Criterion], list[Criterion]]:
    """Return the usable required criteria as (evidence_answerable, design_judgement)."""
    required = [c for c in work.usable_criteria if c.priority is Priority.REQUIRED]
    design = [c for c in required if c.kind is CriterionKind.DESIGN_JUDGEMENT]
    return [c for c in required if c not in design], design


def design_reason(work: Working, a: Assessment, cfg: DecisionConfig) -> str | None:
    """Return why the decision is a design decision to hand to a human, or None.

    It is one when a required criterion is a design judgement and every evidence-answerable
    required criterion is already sufficient (research has nothing left to settle).
    """
    answerable, design = required_by_kind(work)
    if design and all(a.sufficient[c.id] >= cfg.sufficiency_threshold for c in answerable):
        return DESIGN_JUDGEMENT
    return None


def loop_reason(work: Working, a: Assessment, cfg: DecisionConfig) -> str | None:
    """Return the reason to stop researching because research is not converging, or None."""
    if no_progress(work, current_scores(work, a), cfg):
        return NO_PROGRESS
    if research_rounds(work) >= cfg.max_research_rounds:
        return RESEARCH_CAP
    return None


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Ranking is lexicographic (required passed, required mean, supporting
#   mean, declaration order) rather than one weighted number, so a reader can recompute it from
#   the scores shown to the human. (#KernelV01/A)
# ====================================================================
