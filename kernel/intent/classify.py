"""
MODULE: kernel.intent.classify
GOAL: The intake answer-kind classification: one bounded Jev choice question that says what kind
    of answer a goal needs (decision, evidence, ideas, change, out of domain), the interpretation
    of its answer against configured thresholds, and the effective goal after a clarification.
BUSINESS CONTEXT: The root request must pick a supported output contract (Rev 3 section 7.11),
    and Jev may only choose among candidates the kernel supplies (section 9, ADR-053): the five
    answer kinds are those candidates. A low-confidence answer never selects silently, and a
    provider failure keeps today's behaviour (a decision report) instead of failing the run.
ARCHITECTURE: Pure helpers plus one async function over the JevPort. No scheduler imports, so the
    scheduler can import this package. Thresholds come from `config.intent`; the question
    template is literal and versioned like the routing one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypedDict

from pydantic import JsonValue

from kernel.config import IntentConfig
from kernel.contracts import CorrelationIds, RoutingOutcome, Usage, schema_ids
from kernel.providers.base import (
    ChoiceAnswer,
    JevBatch,
    JevInvalidResponse,
    JevPayloadTooLarge,
    JevPort,
    JevUnavailable,
    QuestionSpec,
    json_strings,
)

INTENT_PURPOSE = "kernel.intent"
INTENT_TEMPLATE_ID = "kernel.intent"
INTENT_TEMPLATE_REV = "1"
INTENT_QUESTION_ID = "intent.answer_kind"
NEEDS_CONTEXT_ID = "__NEEDS_CONTEXT__"

DECISION, EVIDENCE, IDEAS, CHANGE, OUT_OF_DOMAIN = (
    "decision", "evidence", "ideas", "change", "out_of_domain")
ANSWER_KINDS = (DECISION, EVIDENCE, IDEAS, CHANGE, OUT_OF_DOMAIN)
#: Kinds the read-only kernel can serve, with the output contract each one resolves to.
KIND_SCHEMA = {DECISION: schema_ids.DECISION_REPORT, EVIDENCE: schema_ids.EVIDENCE_BUNDLE,
               IDEAS: schema_ids.OPTIONS}
#: How the root contract was resolved when no kind applies (Task.intent values).
INTENT_EXPLICIT, INTENT_DEFAULT = "explicit", "default"

_CRITERIA = {
    DECISION: "The goal asks to choose between options or approaches, or to decide what to do.",
    EVIDENCE: "The goal asks to find or locate facts in this software repository.",
    IDEAS: "The goal asks to generate options or ideas, without choosing between them.",
    CHANGE: "The goal asks to implement, edit or modify something.",
    OUT_OF_DOMAIN: "The goal is unrelated to software engineering or this repository.",
    NEEDS_CONTEXT_ID: "The goal lacks the information needed to tell which kind it is.",
}
_INSTRUCTIONS = ("Which kind of answer does the task goal need? Choose exactly one listed kind, "
                 f"or {NEEDS_CONTEXT_ID} if the goal lacks information to tell.")


@dataclass
class ClarificationAnswer:
    """What a human answered to a clarification question (a chosen option id and/or text)."""

    text: str
    choice_id: str | None = None


class _Answered(TypedDict):
    """The answer fields every interpreted outcome carries."""

    probabilities: dict[str, float]
    confidence: float | None
    jev_called: bool


@dataclass
class IntentAssessment:
    """Outcome of classifying one goal (before it is recorded as a RoutingAssessment)."""

    outcome: RoutingOutcome
    kind: str | None = None
    probabilities: dict[str, float] = field(default_factory=dict)
    confidence: float | None = None
    reason_codes: list[str] = field(default_factory=list)
    jev_called: bool = False
    model_id: str | None = None
    usage: list[Usage] = field(default_factory=list)


def effective_goal(original: str, answers: list[ClarificationAnswer], limit: int = 4000) -> str:
    """Return the goal as clarified: the latest answer first, the original request after it.

    The answer is the primary statement of intent (the user restated what they want); the
    original wording stays attached as context. Without answers the original goal is returned.
    """
    if not answers:
        return original
    clarified = answers[-1].text.strip()
    tail = f" (original request: {original})"
    return (clarified + tail)[:limit] if clarified else original


def chosen_kind(answers: list[ClarificationAnswer]) -> str | None:
    """Return the answer kind the human picked from the offered choices, if they did."""
    for answer in reversed(answers):
        if answer.choice_id in ANSWER_KINDS:
            return answer.choice_id
    return None


def build_batch(goal: str, answers: list[ClarificationAnswer], component_ids: list[str],
                corr: CorrelationIds) -> JevBatch:
    """Build the single-question batch for the goal (as clarified, when answers exist)."""
    state: dict[str, JsonValue] = {
        "task": {"goal": effective_goal(goal, answers),
                 "component_ids": json_strings(sorted(component_ids))},
        "clarifications": json_strings(a.text for a in answers)}
    question = QuestionSpec(
        id=INTENT_QUESTION_ID, kind="choice", template_id=INTENT_TEMPLATE_ID,
        template_version=INTENT_TEMPLATE_REV, instructions=_INSTRUCTIONS, criteria=dict(_CRITERIA))
    return JevBatch(purpose=INTENT_PURPOSE, state=state, questions=[question], correlation=corr)


def interpret(answer: ChoiceAnswer, cfg: IntentConfig) -> IntentAssessment:
    """Map a choice answer to an assessment.

    Raises:
        JevInvalidResponse: The answer names something outside the offered kinds.
    """
    base: _Answered = {"probabilities": dict(answer.probabilities),
                       "confidence": answer.confidence, "jev_called": True}
    if answer.choice == NEEDS_CONTEXT_ID:
        return IntentAssessment(RoutingOutcome.INSUFFICIENT_CONTEXT,
                                reason_codes=["jev_needs_context"], **base)
    if answer.choice not in ANSWER_KINDS:
        reason = f"jev chose {answer.choice!r}, which is not an offered answer kind"
        raise JevInvalidResponse(reason)
    probability = answer.probabilities.get(answer.choice, 0.0)
    confident = answer.confidence is not None and answer.confidence >= cfg.min_confidence
    if probability >= cfg.min_selected_probability and confident:
        return IntentAssessment(RoutingOutcome.SELECTED, kind=answer.choice,
                                reason_codes=["jev_selected"], **base)
    return IntentAssessment(RoutingOutcome.INSUFFICIENT_CONTEXT, reason_codes=["low_confidence"],
                            **base)


def _unavailable(code: str) -> IntentAssessment:
    """Return the outcome for a provider failure (never a gap; the default contract is kept)."""
    return IntentAssessment(RoutingOutcome.UNAVAILABLE, reason_codes=[code])


async def assess_intent(jev: JevPort, goal: str, answers: list[ClarificationAnswer],
                        component_ids: list[str], cfg: IntentConfig,
                        corr: CorrelationIds) -> IntentAssessment:
    """Ask Jev what kind of answer the goal needs and interpret the answer.

    Args:
        jev: The Jev port.
        goal: The original task goal.
        answers: Human clarification answers so far (the latest restates the intent).
        component_ids: Scope component ids (context).
        cfg: Intent thresholds.
        corr: Correlation ids for the batch.

    Returns:
        IntentAssessment: `selected` with the kind, `insufficient_context` (clarify) or
            `unavailable` (the provider failed; the caller keeps the default contract).
    """
    batch = build_batch(goal, answers, component_ids, corr)
    try:
        result = await jev.assess(batch)
    except JevUnavailable:
        return _unavailable("provider_unavailable")
    except JevInvalidResponse:
        return _unavailable("invalid_provider_response")
    except JevPayloadTooLarge:
        return _unavailable("payload_too_large")
    try:
        assessment = interpret(result.choice(INTENT_QUESTION_ID), cfg)
    except (JevInvalidResponse, KeyError):
        assessment = _unavailable("invalid_provider_response")
        assessment.jev_called = True
    assessment.model_id = result.model_id
    assessment.usage = [result.usage]
    return assessment


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-02 [python-coder]: mypy: the shared answer fields are a TypedDict so **base is checked. (#KernelBootstrapV0/GROUND)
# - 2026-10-01 22:00 [python-coder]: A failed or invalid classification is `unavailable` and keeps
#   the default decision contract rather than failing the run: the caller did not choose a
#   contract, so classification is help, not a gate. (#KernelBootstrapV0/INTENT)
# - 2026-10-01 22:00 [python-coder]: A clarification answer is the primary statement of intent
#   (answer first, original request after it) so a user who restates the request is not
#   re-classified on the words they just replaced. (#KernelBootstrapV0/INTENT)
# ====================================================================
