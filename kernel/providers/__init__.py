"""
MODULE: kernel.providers
GOAL: Provider ports (Jev) and their test doubles.
BUSINESS CONTEXT: Graphs and the scheduler ask Jev only through JevPort so the provider adapter
    (P3) and the scripted double are interchangeable.
ARCHITECTURE: Re-exports from base and fakes; the langchain-typesafe adapter lives in jev.py (P3)
    and is deliberately not imported here.
"""

from kernel.providers.base import (
    Answer,
    ChoiceAnswer,
    JevBatch,
    JevError,
    JevInvalidResponse,
    JevPayloadTooLarge,
    JevPort,
    JevResult,
    JevUnavailable,
    NoulAnswer,
    QuestionSpec,
    ScoreAnswer,
)
from kernel.providers.fakes import ScriptedJev, choice_answer, noul_answer

__all__ = [
    "Answer", "ChoiceAnswer", "JevBatch", "JevError", "JevInvalidResponse", "JevPayloadTooLarge",
    "JevPort", "JevResult", "JevUnavailable", "NoulAnswer", "QuestionSpec", "ScoreAnswer",
    "ScriptedJev", "choice_answer", "noul_answer",
]

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:00 [python-coder]: Package init stays free of vendor imports.
#   (#KernelBootstrapV0/P1)
# ====================================================================
