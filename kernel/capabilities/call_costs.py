"""
MODULE: kernel.capabilities.call_costs
GOAL: Pure arithmetic on Jev provider calls: how many calls a batch, a retrieval rerank, a research
    round or a decision assessment costs, and how many the running capability may still spend.
BUSINESS CONTEXT: A live run (round 6, run-a522094b886048f3) spent its whole Jev budget on
    retrieval reranks and ended `blocked` three-quarters through the assessment that would have
    produced the ranked human question. Reserving that assessment, and refusing research that
    would eat into the reserve, needs one shared, configurable cost model that the decision
    (go or no-go), research (trim the plan) and the Jev call guard (refuse atomically) all use.
ARCHITECTURE: No IO and no capability imports; everything is derived from KernelConfig
    (`jev.max_questions_per_call`, `retrieval.rerank_max_per_need`, `decision.*`), nothing is
    hard-coded. A budget that cannot report what is left (`UnlimitedBudget`, test doubles) yields
    `None`, which every caller reads as "no limit known, do not gate".
"""

from __future__ import annotations

import math

from kernel.config import KernelConfig

#: Questions of one decision assessment that do not depend on the options or criteria:
#: `missing`, `preference` and `conflict`.
FIXED_ASSESSMENT_QUESTIONS = 3
#: Questions a research judgement always carries beside one `answers.<need>` per satisfied need:
#: `conflict` and `evaluable`.
JUDGEMENT_BASE_QUESTIONS = 2


def _available(budget: object, resource: str) -> int | None:
    """Return what the budget still allows of a resource, or None when it cannot say."""
    probe = getattr(budget, "available", None)
    if not callable(probe):
        return None
    left = probe(resource)
    return None if left is None else max(0, int(left))


def jev_available(budget: object) -> int | None:
    """Return the Jev calls the budget still allows, or None when it cannot say.

    Args:
        budget: The context's budget (a ShareBudget reports its share; others may report nothing).

    Returns:
        int | None: Calls left, or None for an unbounded or non-reporting budget.
    """
    return _available(budget, "jev")


def work_items_available(budget: object) -> int | None:
    """Return the work items the budget still allows, or None when it cannot say."""
    return _available(budget, "work_item")


def provider_calls(questions: int, cfg: KernelConfig) -> int:
    """Return how many provider calls `questions` questions take (chunked per call, at least 0)."""
    if questions <= 0:
        return 0
    return math.ceil(questions / cfg.jev.max_questions_per_call)


def rerank_calls(cfg: KernelConfig) -> int:
    """Return the provider calls one retrieval rerank spends at most (one batch per need)."""
    return provider_calls(cfg.retrieval.rerank_max_per_need, cfg)


def judgement_calls(needs: int, cfg: KernelConfig) -> int:
    """Return the provider calls of one research judgement over `needs` satisfied needs."""
    return provider_calls(JUDGEMENT_BASE_QUESTIONS + needs, cfg)


def research_round_calls(needs: int, cfg: KernelConfig, *, planning: bool = False) -> int:
    """Return the most provider calls one research round of `needs` needs spends.

    Each need is one retrieval child (one rerank batch), the round ends with one judgement over
    all of them, and Jev-chosen planning adds one call over the categories not yet needed.
    """
    planned = provider_calls(len(_categories(cfg)), cfg) if planning else 0
    return planned + needs * rerank_calls(cfg) + judgement_calls(needs, cfg)


def _categories(cfg: KernelConfig) -> list[str]:
    """Return the evidence categories Jev may be asked to select among."""
    return [c.value for c in cfg.research.category_descriptions]


def batch_allowance(left: int | None, reserve: int, needs: int, cfg: KernelConfig) -> int | None:
    """Return the rerank batches each of `needs` retrieval children may judge, or None (no limit).

    The first batch of every need and the round's judgement are planned for (`afford_needs`); the
    calls left beyond them and beyond the requester's `reserve` buy further batches, shared evenly
    between the needs, so deeper reranking can never spend the decision's final assessment.
    """
    if left is None or needs <= 0:
        return None
    base = needs * rerank_calls(cfg) + judgement_calls(needs, cfg)
    spare = max(0, left - reserve - base)
    return 1 + spare // (needs * rerank_calls(cfg))


def targeted_need_count(human_added: int, gaps: int, cfg: KernelConfig) -> int:
    """Return how many targeted needs a research round builds (claims and gaps, capped)."""
    return min(cfg.research.max_targeted_needs, human_added + gaps)


def assessment_questions(criteria: int, options: int, unclassified: int) -> int:
    """Return the number of questions of one decision assessment batch."""
    return criteria * (1 + options) + unclassified + FIXED_ASSESSMENT_QUESTIONS


def assessment_calls(criteria: int, options: int, unclassified: int, cfg: KernelConfig) -> int:
    """Return the provider calls one decision assessment of this size takes."""
    return provider_calls(assessment_questions(criteria, options, unclassified), cfg)


def assessment_reserve(criteria: int, options: int, unclassified: int, cfg: KernelConfig) -> int:
    """Return the Jev calls kept back so the decision can always run its final assessment.

    It covers `decision.reserve_assessments` assessments sized for the options now known plus
    `decision.reserve_extra_options` (a human may add an option when shown the ranking), and
    `decision.reserve_margin_calls` for routing a child request and other small overhead.
    """
    each = assessment_calls(criteria, options + cfg.decision.reserve_extra_options,
                            unclassified, cfg)
    return cfg.decision.reserve_assessments * each + cfg.decision.reserve_margin_calls


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: batch_allowance turns the Jev calls left beyond the plan and the
#   requester's reserve into extra rerank batches per need, so a need may judge deeper without
#   touching the reserve; work_items_available reads the work-item share the same way.
#   (#KernelV01/F)
# - 2026-10-01 [python-coder]: One cost model shared by the decision gate, research planning and
#   the Jev call guard, derived entirely from config; decision-driven research plans exactly its
#   mandated needs (no Jev planning call), so a round's cost is known before it starts.
#   (#KernelV01/E)
# ====================================================================
