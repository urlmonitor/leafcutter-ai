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

import re
from collections.abc import Mapping

from kernel.capabilities.decision.assess import Assessment
from kernel.capabilities.decision.option_context import cited_refs
from kernel.capabilities.decision.state import ADDED_OPTION_PREFIX, Working
from kernel.config import DecisionConfig
from kernel.contracts.decision import Criterion, CriterionKind, OptionRanking
from kernel.contracts.enums import Priority

DESIGN_JUDGEMENT = "design_judgement"
NO_PROGRESS = "no_progress"
RESEARCH_CAP = "research_cap"
#: The Jev budget cannot fund another research round plus the reserved final assessment.
BUDGET_RESERVE = "budget_reserve"
DESIGN_REASONS = (DESIGN_JUDGEMENT, NO_PROGRESS, RESEARCH_CAP, BUDGET_RESERVE)
#: Reason (and request key suffix) of the one targeted research round a design decision runs
#: before it ranks its options.
DESIGN_ROUND = "design_round"
_ROUND = 4
#: A cited reference that names a repository file (a path with an extension).
_PATH_REF = re.compile(r"(?:[\w.\-]+/)*[\w.\-]+\.(?:py|md|json|ya?ml|toml|sql|ts|js|txt|cfg|ini|sh)"
                       r"(?:#\S+|::[\w.]+)?")


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


def satisfies_from_scores(work: Working, scores: Mapping[str, float]
                          ) -> dict[tuple[str, str], float] | None:
    """Return the satisfies score of every usable (criterion, option) pair, or None.

    `scores` is a complete assessment's `current_scores` map (the continuation's `last_scores`).
    None when any current pair has no score: the options or criteria changed since, and a ranking
    over some of the options would be half scored.
    """
    found: dict[tuple[str, str], float] = {}
    for c in work.usable_criteria:
        for o in work.usable_options:
            score = scores.get(score_key(c.id, o.id))
            if score is None:
                return None
            found[(c.id, o.id)] = score
    return found if found else None


def rank_options(work: Working, a: Assessment, cfg: DecisionConfig) -> list[OptionRanking]:
    """Rank the usable options best first (see the module docstring for the aggregation)."""
    return rank_satisfies(work, a.satisfies, cfg)


def rank_satisfies(work: Working, satisfies: Mapping[tuple[str, str], float],
                   cfg: DecisionConfig) -> list[OptionRanking]:
    """Rank the usable options best first from a complete (criterion, option) score map."""
    required = [c for c in work.usable_criteria if c.priority is Priority.REQUIRED]
    supporting = [c for c in work.usable_criteria if c.priority is not Priority.REQUIRED]
    rows = []
    for order, option in enumerate(work.usable_options):
        req = [satisfies[(c.id, option.id)] for c in required]
        sup = [satisfies[(c.id, option.id)] for c in supporting]
        passed = sum(p >= cfg.satisfies_threshold for p in req)
        rows.append((-passed, -_mean(req), -_mean(sup), order, option.id, passed, req, sup))
    rows.sort(key=lambda r: r[:4])
    return [OptionRanking(
        option_id=oid, rank=rank, required_passed=passed, required_total=len(required),
        required_mean=_mean(req), supporting_mean=_mean(sup) if sup else None,
        scores={c.id: satisfies[(c.id, oid)] for c in work.usable_criteria})
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

    It is one when a required criterion is a design judgement, every evidence-answerable required
    criterion is already sufficient (research has nothing left to settle) and no option passes
    every required criterion. An option that does pass (Jev is sure of each criterion, for example
    because an ADR states the answer) leaves the decision to the resolved-gate: the ending exists
    to stop loops on flat scores, not to take a clear answer away (the live ADR-settled goal was
    ranked for a human although its option scored 0.98 and 0.96).
    """
    answerable, design = required_by_kind(work)
    if not design or not all(a.sufficient[c.id] >= cfg.sufficiency_threshold for c in answerable):
        return None
    required = [c for c in work.usable_criteria if c.priority is Priority.REQUIRED]
    if any(all(a.satisfies[(c.id, o.id)] >= cfg.satisfies_threshold for c in required)
           for o in work.usable_options):
        return None
    return DESIGN_JUDGEMENT


def design_round_done(work: Working) -> bool:
    """True if the decision already asked for its one targeted research round before ranking."""
    return any(k.startswith("research:") and k.endswith(f":{DESIGN_ROUND}")
               for k in work.cont.requested)


def has_targets(work: Working) -> bool:
    """True if there is something specific to look for: what the options claim and cite.

    That is a gap a synthesis named, the claims of an option a human added, or a file an option
    cites that is not among the evidence yet. A round that would only repeat the goal's own
    query finds nothing new and is not worth the calls.
    """
    if work.cont.gaps or any(o.id.startswith(ADDED_OPTION_PREFIX) for o in work.usable_options):
        return True
    fetched = {e.source.locator.split("#")[0].split("::")[0] for e in work.evidence}
    refs = (r for o in work.usable_options for r in cited_refs(o) if _PATH_REF.fullmatch(r))
    return any(r.split("#")[0].split("::")[0] not in fetched for r in refs)


def design_round_due(work: Working, cfg: DecisionConfig) -> bool:
    """True if a design decision should run its targeted research round before ranking.

    Once, while the research-round cap has room and the options give something to aim at.
    """
    return (not design_round_done(work) and research_rounds(work) < cfg.max_research_rounds
            and has_targets(work))


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
# - 2026-10-01 [python-coder]: A design decision runs ONE targeted research round (option claims,
#   synthesis gaps, cited files not yet evidence) before it ranks: round 7 reached the ranked
#   question in 7 calls on 3 evidence items, and the user's own option showed "no evidence cited"
#   because the round that fetches `kernel/contracts/decision.py` never ran. design_round_due
#   keeps the research-round cap; the budget gate still decides whether the round fits beside
#   the reserve. (#KernelV01/F)
# - 2026-10-01 [python-coder]: A design-judgement ending does not fire while an option passes
#   every required criterion: the live ADR-settled goal (scores 0.98 and 0.96) was ranked for a
#   human once Jev classified its criteria as properties of the options. (#KernelV01/E)
# - 2026-10-01 [python-coder]: The ranking can be built from a stored score map (the last complete
#   assessment) as well as a fresh Assessment, and refuses (None) when an option or criterion has
#   no score, so a budget stop never produces a half-scored ranking; BUDGET_RESERVE is the new
#   reason to stop researching. (#KernelV01/E)
# - 2026-10-01 [python-coder]: Ranking is lexicographic (required passed, required mean, supporting
#   mean, declaration order) rather than one weighted number, so a reader can recompute it from
#   the scores shown to the human. (#KernelV01/A)
# ====================================================================
