"""
MODULE: kernel.capabilities.research.baseline
GOAL: Name the baseline evidence needs a research goal falls back on when Jev selects none.
BUSINESS CONTEXT: A lookup question answered with an empty bundle searched nothing and said so
    only in a limitation; a goal must always send retrieval at least to the task's own context
    and the repository's existing patterns.
ARCHITECTURE: Pure function over the question and the configured category descriptions.
"""

from __future__ import annotations

from kernel.contracts.enums import EvidenceCategory, Priority
from kernel.contracts.evidence import EvidenceNeed

BASELINE_CATEGORIES = (EvidenceCategory.TASK_CONTEXT, EvidenceCategory.EXISTING_PATTERNS)


def baseline_needs(question: str, described: dict[EvidenceCategory, str]) -> list[EvidenceNeed]:
    """Return the supporting task-context and existing-pattern needs for the question.

    Args:
        question: The research question (the goal).
        described: Configured description per evidence category.

    Returns:
        One supporting need per baseline category, in `BASELINE_CATEGORIES` order.
    """
    return [EvidenceNeed(id=f"need.{c.value}", category=c, priority=Priority.SUPPORTING,
                         question=f"{described[c]} Question: {question}")
            for c in BASELINE_CATEGORIES]


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-09 [python-coder]: Baseline needs are supporting, not required: evidence plans never
#   reach the required threshold, and a required baseline would turn every thin lookup partial.
#   (#TICKET-20261009-KernelEvidenceLookupNoNeeds)
# ====================================================================
