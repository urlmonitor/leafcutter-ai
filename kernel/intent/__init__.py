"""
MODULE: kernel.intent
GOAL: Public surface of the intake intent package: answer-kind classification, the plain
    clarification questions, root shaping and declines, gap record quality and report wording.
BUSINESS CONTEXT: The root request must pick a supported output contract (Rev 3 section 7.11);
    what a goal needs is decided here, in code and by one bounded Jev question, before routing.
ARCHITECTURE: No scheduler imports, so the scheduler package can import this one. The route node
    applies the results; this package only builds and interprets values.
"""

from __future__ import annotations

from kernel.intent.classify import (
    ANSWER_KINDS,
    CHANGE,
    DECISION,
    EVIDENCE,
    IDEAS,
    INTENT_DEFAULT,
    INTENT_EXPLICIT,
    KIND_SCHEMA,
    OUT_OF_DOMAIN,
    ClarificationAnswer,
    IntentAssessment,
    assess_intent,
    chosen_kind,
    effective_goal,
)

__all__ = ["ANSWER_KINDS", "CHANGE", "DECISION", "EVIDENCE", "IDEAS", "INTENT_DEFAULT",
           "INTENT_EXPLICIT", "KIND_SCHEMA", "OUT_OF_DOMAIN", "ClarificationAnswer",
           "IntentAssessment", "assess_intent", "chosen_kind", "effective_goal"]

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 22:00 [python-coder]: New package instead of more scheduler modules: the scheduler
#   folder is at its file limit and nodes_route.py at the size limit. (#KernelBootstrapV0/INTENT)
# ====================================================================
