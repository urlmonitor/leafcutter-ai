"""
MODULE: kernel.capabilities.decision.budget_gate
GOAL: Keep the Jev budget for the decision's own ending: decide when another research round no
    longer fits beside a reserved final assessment, and fall back to the last complete assessment
    when an assessment cannot be funded.
BUSINESS CONTEXT: Round 6 (run-a522094b886048f3) spent 33 of its 40 Jev calls reranking
    retrieval candidates and ended `blocked: jev call budget exhausted` three-quarters through the
    second assessment, so the ranked human question was never reached. A decision with a usable
    assessment must never end blocked on the budget: it hands the ranked options to a human and
    says plainly that the ranking rests on limited evidence.
ARCHITECTURE: Pure functions over Working, the Verdict and the budget the context reports
    (call_costs.jev_available); nothing is hard-coded, the reserve and the research cost come from
    config. `handover` is consulted after combine for a follow-up that spends calls and ends in
    another assessment; `fallback_followup` is consulted when an assessment is refused for budget.
"""

from __future__ import annotations

from kernel.capabilities.base import ExecutionContext
from kernel.capabilities.call_costs import (
    assessment_reserve,
    jev_available,
    research_round_calls,
    targeted_need_count,
)
from kernel.capabilities.decision.assess import Assessment, unclassified
from kernel.capabilities.decision.combine import Verdict
from kernel.capabilities.decision.design_ending import design_followup
from kernel.capabilities.decision.ranking import (
    BUDGET_RESERVE,
    rank_options,
    rank_satisfies,
    satisfies_from_scores,
)
from kernel.capabilities.decision.requests import Followup
from kernel.capabilities.decision.state import ADDED_OPTION_PREFIX, Working
from kernel.config import KernelConfig
from kernel.contracts.capability import CapabilityResult
from kernel.contracts.enums import DecisionStatus, MissingKnowledge

BUDGET_CODE = "budget_exhausted"
#: Follow-ups that end in another assessment after spending calls (research) or none (the rest).
_REASSESSED = (DecisionStatus.NEEDS_EVIDENCE, DecisionStatus.NEEDS_SYNTHESIS,
               DecisionStatus.NEEDS_OPTIONS)
LIMITATION = ("ranking made on limited evidence because the Jev call budget (limits.max_jev_calls) "
              "was reached: another research round and a final assessment no longer fit")


def reserve_for(work: Working, cfg: KernelConfig) -> int:
    """Return the Jev calls to keep for the decision's final assessment (see call_costs)."""
    return assessment_reserve(len(work.usable_criteria), len(work.usable_options),
                              len(unclassified(work)), cfg)


def followup_calls(work: Working, verdict: Verdict, cfg: KernelConfig) -> int:
    """Return the provider calls the follow-up of this verdict spends before the next assessment.

    Only research spends Jev calls (one retrieval child per need and one judgement); a synthesis
    or an options request is host work. Research needs are exactly the verdict's categories plus
    the targeted needs the decision's options and gaps will produce.
    """
    if verdict.status is not DecisionStatus.NEEDS_EVIDENCE:
        return 0
    added = sum(o.id.startswith(ADDED_OPTION_PREFIX) for o in work.usable_options)
    needs = len(verdict.categories) + targeted_need_count(added, len(work.cont.gaps), cfg)
    return research_round_calls(needs, cfg)


def _rankable(work: Working) -> bool:
    """True if there are options and a required criterion to rank them by."""
    return bool(work.usable_options) and work.has_required_criterion


def handover(ctx: ExecutionContext, work: Working, a: Assessment, verdict: Verdict
             ) -> Verdict | None:
    """Return the ranked human hand-over when the follow-up plus the reserve do not fit, else None.

    Args:
        ctx: Execution context (reports the Jev calls this worker may still spend).
        work: Working state (options, criteria, gaps).
        a: The complete assessment just made (the ranking is built from it).
        verdict: What combine decided.

    Returns:
        Verdict | None: A needs_human verdict with the ranking and reason `budget_reserve`, or
            None when the budget is unknown or funds the follow-up and the reserved assessment.
    """
    if verdict.status not in _REASSESSED or verdict.ranking or not _rankable(work):
        return None
    left = jev_available(ctx.budget)
    if left is None:
        return None
    if left >= followup_calls(work, verdict, ctx.config) + reserve_for(work, ctx.config):
        return None
    work.limitations.append(LIMITATION)
    return Verdict(DecisionStatus.NEEDS_HUMAN, reason=BUDGET_RESERVE,
                   missing=[MissingKnowledge.HUMAN_PREFERENCE_OR_AUTHORIZATION],
                   ranking=rank_options(work, a, ctx.config.decision),
                   assessments=verdict.assessments)


def fallback_followup(ctx: ExecutionContext, work: Working, stopped: CapabilityResult
                      ) -> Followup | None:
    """Return the ranked question built from the last complete assessment, or None.

    Used when a new assessment could not be funded (`budget_exhausted`). The last complete
    assessment must cover every usable option and criterion; otherwise nothing is ranked (a
    half-scored ranking is worse than none) and the stop stands. Usage of calls made before the
    stop is kept so usage rows and the budget still agree.
    """
    if stopped.error is None or stopped.error.code != BUDGET_CODE or not _rankable(work):
        return None
    satisfies = satisfies_from_scores(work, work.cont.last_scores)
    if satisfies is None:
        return None
    cfg = ctx.config.decision
    ranking = rank_satisfies(work, satisfies, cfg)
    work.usage.extend(stopped.usage)
    work.limitations.append(LIMITATION)
    work.cont = work.cont.model_copy(update={"design_ranking": ranking,
                                             "design_reason": BUDGET_RESERVE})
    return design_followup(work, BUDGET_RESERVE, ranking, cfg)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: A decision with a usable assessment never ends blocked on the Jev
#   budget: a research round that would eat into the reserved final assessment is replaced by the
#   ranked human question, and an assessment refused for budget falls back to the last complete
#   one (all-or-nothing: never a half-scored ranking). (#KernelV01/E)
# ====================================================================
