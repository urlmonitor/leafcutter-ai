"""
MODULE: kernel.providers.jev_wire
GOAL: Pure conversion between kernel questions/answers and the TypeSafe System One wire shape,
    including strict validation of every answer.
BUSINESS CONTEXT: Both transports (langchain-typesafe classifier and the direct HTTP fallback)
    must yield identical, validated answers; a missing id, an unknown choice or probabilities
    that do not sum to one must fail loudly as JevInvalidResponse instead of steering routing.
ARCHITECTURE: No I/O and no vendor imports. Transports return a RawResponse of plain JSON
    dicts; map_answers turns it into kernel Answer models. Sentinel labels such as __NONE__ are
    ordinary choice labels here; their meaning belongs to the routing layer.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from kernel.providers.base import (
    Answer,
    ChoiceAnswer,
    JevInvalidResponse,
    NoulAnswer,
    QuestionSpec,
    ScoreAnswer,
)
from kernel.providers.jev_errors import JevInvalidRequest

PROBABILITY_TOLERANCE = 0.02


@dataclass(frozen=True)
class RawResponse:
    """One provider response as plain JSON data, independent of the transport."""

    model: str | None
    answers: dict[str, Any]
    input_tokens: int | None = None
    output_tokens: int | None = None
    request_id: str | None = None


def question_to_wire(spec: QuestionSpec) -> dict[str, Any]:
    """Build the System One question object for one QuestionSpec.

    Args:
        spec: The literal question.

    Returns:
        dict: ``{"type", "instructions", "criteria"?}`` ready for the request body.

    Raises:
        JevInvalidRequest: The criteria do not fit the question kind.
    """
    wire: dict[str, Any] = {"type": spec.kind, "instructions": spec.instructions}
    criteria = spec.criteria
    if spec.kind == "choice":
        if not isinstance(criteria, dict) or not criteria:
            reason = f"choice question {spec.id} needs a non-empty criteria mapping"
            raise JevInvalidRequest(reason)
        wire["criteria"] = dict(criteria)
    elif spec.kind == "score":
        levels = list(criteria.values()) if isinstance(criteria, dict) else list(criteria or [])
        if len(levels) < 2:
            reason = f"score question {spec.id} needs at least two ordered criteria"
            raise JevInvalidRequest(reason)
        wire["criteria"] = levels
    elif criteria:
        if not isinstance(criteria, dict) or not set(criteria) <= {"true", "false"}:
            reason = f"noul question {spec.id} criteria may only use the keys true and false"
            raise JevInvalidRequest(reason)
        wire["criteria"] = dict(criteria)
    return wire


def parse_body(body: object, request_id: str | None) -> RawResponse:
    """Validate the envelope of a successful response body.

    Args:
        body: Decoded JSON body.
        request_id: Provider request id from the response headers, if any.

    Returns:
        RawResponse: Envelope with unknown token counts kept as None.

    Raises:
        JevInvalidResponse: The body is not an object with an answers object.
    """
    if not isinstance(body, dict) or not isinstance(body.get("answers"), dict):
        reason = "response body has no answers object"
        raise JevInvalidResponse(reason)
    usage = body.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    model = body.get("model")
    body_rid = body.get("request_id")
    return RawResponse(
        model=model if isinstance(model, str) and model else None,
        answers=body["answers"],
        input_tokens=_count(usage.get("input_tokens")),
        output_tokens=_count(usage.get("output_tokens")),
        request_id=request_id or (body_rid if isinstance(body_rid, str) else None),
    )


def map_answers(raw_answers: Mapping[str, Any], specs: Sequence[QuestionSpec]) -> dict[str, Answer]:
    """Convert and validate the raw answer for every spec.

    Args:
        raw_answers: Wire answers keyed by question id.
        specs: The questions that were asked.

    Returns:
        dict[str, Answer]: Kernel answers keyed by question id, in spec order.

    Raises:
        JevInvalidResponse: An id is missing, the type differs, or the values are invalid.
    """
    answers: dict[str, Answer] = {}
    for spec in specs:
        raw = raw_answers.get(spec.id)
        if not isinstance(raw, dict):
            reason = f"no answer returned for question {spec.id}"
            raise JevInvalidResponse(reason)
        if raw.get("type") != spec.kind:
            reason = f"answer for {spec.id} has type {raw.get('type')!r}, expected {spec.kind}"
            raise JevInvalidResponse(reason)
        answers[spec.id] = _MAPPERS[spec.kind](spec, raw)
    return answers


def _count(value: object) -> int | None:
    """Return a non-negative int token count, or None when unknown or malformed."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _number(value: object, where: str, low: float, high: float) -> float:
    """Return a finite float within [low, high] or raise JevInvalidResponse."""
    number = float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) \
        else math.nan
    if not math.isfinite(number) or not low <= number <= high:
        reason = f"{where} is not a number in [{low}, {high}]: {value!r}"
        raise JevInvalidResponse(reason)
    return number


def _confidence(raw: dict[str, Any], qid: str) -> float | None:
    """Return the provider confidence (None when the provider sent none)."""
    if raw.get("confidence") is None:
        return None
    return _number(raw["confidence"], f"confidence of {qid}", 0.0, 1.0)


def _distribution(raw: dict[str, Any], qid: str, allowed: set[str]) -> dict[str, float]:
    """Validate a probability distribution: known keys, [0,1] values, sum 1 +- tolerance."""
    probs = raw.get("probabilities")
    if not isinstance(probs, dict) or not probs:
        reason = f"answer for {qid} has no probabilities"
        raise JevInvalidResponse(reason)
    clean: dict[str, float] = {}
    for key, value in probs.items():
        if str(key) not in allowed:
            reason = f"answer for {qid} has probability for unknown label {key!r}"
            raise JevInvalidResponse(reason)
        clean[str(key)] = _number(value, f"probability {key} of {qid}", 0.0, 1.0)
    if abs(sum(clean.values()) - 1.0) > PROBABILITY_TOLERANCE:
        reason = f"probabilities of {qid} sum to {sum(clean.values()):.4f}, not 1"
        raise JevInvalidResponse(reason)
    return clean


def _map_noul(spec: QuestionSpec, raw: dict[str, Any]) -> NoulAnswer:
    """Map a noul wire answer."""
    probability = _number(raw.get("noul"), f"noul of {spec.id}", 0.0, 1.0)
    return NoulAnswer(question_id=spec.id, probability=probability, confidence=None)


def _map_choice(spec: QuestionSpec, raw: dict[str, Any]) -> ChoiceAnswer:
    """Map a choice wire answer; the chosen label must be one of the criteria."""
    labels = set(spec.criteria or {})
    choice = raw.get("choice")
    if not isinstance(choice, str) or choice not in labels:
        reason = f"choice {choice!r} for {spec.id} is not one of the criteria"
        raise JevInvalidResponse(reason)
    probs = _distribution(raw, spec.id, labels)
    return ChoiceAnswer(question_id=spec.id, choice=choice, probabilities=probs,
                        confidence=_confidence(raw, spec.id))


def _map_score(spec: QuestionSpec, raw: dict[str, Any]) -> ScoreAnswer:
    """Map a score wire answer; levels are zero-based integers as strings."""
    levels = len(spec.criteria) if spec.criteria else 0
    score = _number(raw.get("score"), f"score of {spec.id}", 0.0, max(levels - 1, 0))
    probs = _distribution(raw, spec.id, {str(i) for i in range(levels)})
    return ScoreAnswer(question_id=spec.id, score=score, probabilities=probs,
                       confidence=_confidence(raw, spec.id))


_MAPPERS: dict[str, Callable[[QuestionSpec, dict[str, Any]],
                             NoulAnswer | ChoiceAnswer | ScoreAnswer]] = {
    "noul": _map_noul, "choice": _map_choice, "score": _map_score}

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-02 [python-coder]: mypy: the wire mappers are typed and the number check narrows before comparing (#KernelBootstrapV0/GROUND)
# - 2026-09-30 23:00 [python-coder]: One wire mapper for both transports; probabilities must sum
#   to 1 +- 0.02 (design part 4); a missing provider confidence stays None, never 0.
#   (#KernelBootstrapV0/P3)
# ====================================================================
