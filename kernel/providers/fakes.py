"""
MODULE: kernel.providers.fakes
GOAL: ScriptedJev, a deterministic in-memory JevPort that answers from a script and records
    every batch.
BUSINESS CONTEXT: Kernel, routing, decision and research tests must run offline and
    reproducibly; a scripted provider lets them assert exactly which questions were asked and how
    the code reacts to each answer, including provider failures.
ARCHITECTURE: Rules match (purpose glob, question-id glob). An unmatched question raises
    JevInvalidResponse so a missing script entry fails the test loudly instead of guessing.
"""

from __future__ import annotations

import fnmatch
from collections.abc import Callable
from dataclasses import dataclass

from kernel.contracts.capability import Usage
from kernel.providers.base import (
    Answer,
    ChoiceAnswer,
    JevBatch,
    JevError,
    JevInvalidResponse,
    JevResult,
    NoulAnswer,
    QuestionSpec,
)

AnswerSource = Answer | Callable[[QuestionSpec, JevBatch], Answer]


def noul_answer(probability: float, confidence: float | None = None) -> NoulAnswer:
    """Build a NoulAnswer for scripting (question id is filled in on use)."""
    return NoulAnswer(probability=probability, confidence=confidence)


def choice_answer(choice: str, probability: float = 0.95, confidence: float | None = 0.9,
                  others: dict[str, float] | None = None) -> ChoiceAnswer:
    """Build a ChoiceAnswer; remaining mass is spread over `others` (or left out).

    Args:
        choice: The chosen criterion id.
        probability: Probability of the chosen criterion.
        confidence: Provider confidence.
        others: Explicit probabilities for other criteria.

    Returns:
        ChoiceAnswer: Scripted answer.
    """
    probs = {choice: probability, **(others or {})}
    return ChoiceAnswer(choice=choice, probabilities=probs, confidence=confidence)


@dataclass
class _Rule:
    """One script entry."""

    purpose: str
    question_glob: str
    source: AnswerSource


class ScriptedJev:
    """JevPort double: answers from rules, records batches, can be told to fail."""

    def __init__(self, *, model_id: str = "jev-scripted", usage: Usage | None = None) -> None:
        """Create an empty script.

        Args:
            model_id: Model id reported in results.
            usage: Usage returned per call (default: one jev call, everything else unknown).
        """
        self.model_id = model_id
        self.usage = usage or Usage(provider="jev", model_id=model_id, calls=1)
        self.batches: list[JevBatch] = []
        self._rules: list[_Rule] = []
        self._failures: list[JevError] = []

    def script(self, purpose: str, question_glob: str, answer: AnswerSource) -> ScriptedJev:
        """Add a rule; earlier rules win. Globs use fnmatch. Returns self for chaining."""
        self._rules.append(_Rule(purpose, question_glob, answer))
        return self

    def fail_next(self, error: JevError, times: int = 1) -> ScriptedJev:
        """Make the next `times` assess calls raise `error` (recorded in batches first)."""
        self._failures.extend([error] * times)
        return self

    @property
    def call_count(self) -> int:
        """Number of assess calls so far, including failed ones."""
        return len(self.batches)

    def questions_asked(self, purpose: str | None = None) -> list[str]:
        """Return question ids asked, optionally only for one purpose."""
        return [q.id for b in self.batches if purpose in (None, b.purpose)
                for q in b.questions]

    def _answer_for(self, batch: JevBatch, question: QuestionSpec) -> Answer:
        """Find the first matching rule and build the answer for this question."""
        for rule in self._rules:
            if (fnmatch.fnmatchcase(batch.purpose, rule.purpose)
                    and fnmatch.fnmatchcase(question.id, rule.question_glob)):
                source = rule.source
                answer = source(question, batch) if callable(source) else source
                return answer.model_copy(update={"question_id": question.id})
        reason = f"no scripted answer for {batch.purpose}/{question.id}"
        raise JevInvalidResponse(reason)

    async def assess(self, batch: JevBatch) -> JevResult:
        """Record the batch, raise a queued failure, or answer every question from the script."""
        self.batches.append(batch)
        if self._failures:
            raise self._failures.pop(0)
        answers = {q.id: self._answer_for(batch, q) for q in batch.questions}
        return JevResult(model_id=self.model_id, request_id=f"scripted-{len(self.batches)}",
                         answers=answers, usage=self.usage, latency_ms=0,
                         input_fingerprint=batch.input_fingerprint())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:00 [python-coder]: Unmatched questions raise instead of defaulting, so a test
#   cannot pass by accident on an unscripted answer. (#KernelBootstrapV0/P1)
# ====================================================================
