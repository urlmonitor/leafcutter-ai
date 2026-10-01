"""
MODULE: kernel.scheduler.routing
GOAL: Turn eligibility reports into RoutingAssessment outcomes: deterministic selection or
    exclusion, plus one batched Jev choice question per item that needs semantic routing.
BUSINESS CONTEXT: Code decides what is allowed; Jev only chooses among what is allowed (Rev 3
    section 6.1). A low-confidence answer is never silently turned into a selection, and a
    provider failure is an `unavailable` outcome, never a capability gap (spec 13.4).
ARCHITECTURE: Pure helpers plus one async function that calls the JevPort. Thresholds come from
    config.routing; the question template is literal and versioned (design part 4, routing).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kernel.config import KernelConfig, RoutingConfig
from kernel.contracts import CorrelationIds, RoutingOutcome, Usage
from kernel.contracts.work import RequestBody
from kernel.providers.base import (
    ChoiceAnswer,
    JevBatch,
    JevInvalidResponse,
    JevPayloadTooLarge,
    JevPort,
    JevUnavailable,
    QuestionSpec,
)
from kernel.registry.eligibility import EligibilityReport

ROUTE_TEMPLATE_ID = "kernel.route"
ROUTE_TEMPLATE_REV = "1"
ROUTE_PURPOSE = "kernel.route"
NONE_ID = "__NONE__"
NEEDS_CONTEXT_ID = "__NEEDS_CONTEXT__"
_NONE_TEXT = "None of the listed capabilities can handle the request."
_CONTEXT_TEXT = "The request lacks the information needed to choose a capability."


@dataclass
class RouteEntry:
    """One work item awaiting routing with its deterministic eligibility report."""

    item_id: str
    request: RequestBody
    report: EligibilityReport
    clarifications: list[str] = field(default_factory=list)


@dataclass
class RouteResult:
    """Outcome of routing one item (before it is recorded as a RoutingAssessment)."""

    outcome: RoutingOutcome
    selected: str | None = None
    probabilities: dict[str, float] = field(default_factory=dict)
    confidence: float | None = None
    reason_codes: list[str] = field(default_factory=list)
    jev_called: bool = False
    model_id: str | None = None
    failure: str | None = None
    usage: list[Usage] = field(default_factory=list)


def deterministic_result(report: EligibilityReport) -> RouteResult | None:
    """Return the outcome fixed by eligibility alone, or None when Jev must choose."""
    hint = report.outcome_hint
    if hint == "selected":
        return RouteResult(RoutingOutcome.SELECTED, selected=report.selected_id,
                           reason_codes=["deterministic"])
    if hint == "no_match":
        return RouteResult(RoutingOutcome.NO_MATCH, reason_codes=["no_eligible_candidate"])
    if hint == "unavailable":
        codes = sorted({e.reason_code.split(":", 1)[0] for e in report.excluded
                        if e.capability_id in report.matched_ids})
        return RouteResult(RoutingOutcome.UNAVAILABLE, reason_codes=codes)
    return None


def _request_state(entry: RouteEntry) -> dict:
    """Return the JSON state describing one request for the routing question."""
    body = entry.request
    return {"kind": body.kind.value, "goal": body.goal or "", "question": body.question or "",
            "payload_schema": body.payload_schema, "payload_keys": sorted(body.payload),
            "clarifications": list(entry.clarifications)}


def build_batch(entries: list[RouteEntry], goal: str, component_ids: list[str],
                corr: CorrelationIds) -> JevBatch:
    """Build one JevBatch with a choice question per entry (`route.<work_item_id>`)."""
    state = {"task": {"goal": goal, "component_ids": sorted(component_ids)},
             "requests": {e.item_id: _request_state(e) for e in entries}}
    questions = []
    for entry in entries:
        criteria = {d.id: d.description for d in entry.report.semantic_candidates}
        criteria[NONE_ID] = _NONE_TEXT
        criteria[NEEDS_CONTEXT_ID] = _CONTEXT_TEXT
        instructions = (f"Which capability should handle `requests.{entry.item_id}`? Choose "
                        f"exactly one listed capability, {NONE_ID} if none fits, or "
                        f"{NEEDS_CONTEXT_ID} if the request lacks information to decide.")
        questions.append(QuestionSpec(
            id=f"route.{entry.item_id}", kind="choice", template_id=ROUTE_TEMPLATE_ID,
            template_version=ROUTE_TEMPLATE_REV, instructions=instructions,
            criteria=criteria))
    return JevBatch(purpose=ROUTE_PURPOSE, state=state, questions=questions, correlation=corr)


def interpret_answer(answer: ChoiceAnswer, candidate_ids: list[str], cfg: RoutingConfig
                     ) -> RouteResult:
    """Map a choice answer to an outcome (design part 4 table).

    Raises:
        JevInvalidResponse: The answer names an id outside the offered candidates.
    """
    base = {"probabilities": dict(answer.probabilities), "confidence": answer.confidence,
            "jev_called": True}
    if answer.choice == NONE_ID:
        return RouteResult(RoutingOutcome.NO_MATCH, reason_codes=["jev_none"], **base)
    if answer.choice == NEEDS_CONTEXT_ID:
        return RouteResult(RoutingOutcome.INSUFFICIENT_CONTEXT,
                           reason_codes=["jev_needs_context"], **base)
    if answer.choice not in candidate_ids:
        reason = f"jev chose {answer.choice!r}, which is not an offered candidate"
        raise JevInvalidResponse(reason)
    probability = answer.probabilities.get(answer.choice, 0.0)
    confident = answer.confidence is not None and answer.confidence >= cfg.min_confidence
    if probability >= cfg.min_selected_probability and confident:
        return RouteResult(RoutingOutcome.SELECTED, selected=answer.choice,
                           reason_codes=["jev_selected"], **base)
    return RouteResult(RoutingOutcome.INSUFFICIENT_CONTEXT, reason_codes=["low_confidence"],
                       **base)


def _failed(code: str) -> RouteResult:
    """Return the unavailable outcome for a routing failure (never a gap)."""
    return RouteResult(RoutingOutcome.UNAVAILABLE, reason_codes=[code], failure=code)


async def _assess_chunk(jev: JevPort, chunk: list[RouteEntry], batch: JevBatch,
                        cfg: RoutingConfig) -> dict[str, RouteResult]:
    """Call Jev once for a chunk and interpret each answer; failures become outcomes."""
    try:
        result = await jev.assess(batch)
    except JevUnavailable:
        return {e.item_id: _failed("provider_unavailable") for e in chunk}
    except JevInvalidResponse:
        return {e.item_id: _failed("invalid_provider_response") for e in chunk}
    except JevPayloadTooLarge:
        return {e.item_id: _failed("payload_too_large") for e in chunk}
    out: dict[str, RouteResult] = {}
    for position, entry in enumerate(chunk):
        try:
            routed = interpret_answer(result.choice(f"route.{entry.item_id}"),
                                      [d.id for d in entry.report.semantic_candidates], cfg)
        except (JevInvalidResponse, KeyError):
            routed = _failed("invalid_provider_response")
        routed.model_id = result.model_id
        routed.usage = [result.usage] if position == 0 else []  # one usage per Jev call
        out[entry.item_id] = routed
    return out


async def route_semantic(jev: JevPort, entries: list[RouteEntry], *, goal: str,
                         component_ids: list[str], cfg: KernelConfig, calls_available: int,
                         corr: CorrelationIds) -> tuple[dict[str, RouteResult], int]:
    """Route every entry that needs Jev, batching questions and reserving calls first.

    Args:
        jev: The Jev port.
        entries: Entries whose eligibility hint is `needs_semantic`.
        goal: The task goal (routing context).
        component_ids: Scope component ids (routing context).
        cfg: Kernel configuration (routing thresholds, questions per call).
        calls_available: Jev calls still allowed by the budget.
        corr: Correlation ids for the batches.

    Returns:
        tuple: (results by work item id, Jev calls made). Chunks beyond the budget become
            `unavailable` with reason `budget_exhausted` without calling Jev.
    """
    size = cfg.jev.max_questions_per_call
    results: dict[str, RouteResult] = {}
    calls = 0
    for start in range(0, len(entries), size):
        chunk = entries[start:start + size]
        if calls >= calls_available:
            results.update({e.item_id: _failed("budget_exhausted") for e in chunk})
            continue
        calls += 1
        batch = build_batch(chunk, goal, component_ids, corr)
        results.update(await _assess_chunk(jev, chunk, batch, cfg.routing))
    return results, calls


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 20:00 [python-coder]: A chunk's usage rides on its first entry only, so the
#   flattened usage of a route pass holds exactly one record per Jev call; copying it onto every
#   entry and truncating to the call count counted one call twice and lost another.
#   (#KernelBootstrapV0/FIXB)
# - 2026-09-30 22:30 [python-coder]: The routing state carries all batched requests under
#   `requests.<work_item_id>` (design shows one request) because a JevBatch has a single state
#   shared by its questions. (#KernelBootstrapV0/P4)
# - 2026-09-30 22:30 [python-coder]: A choice answer without confidence never selects: the
#   confidence threshold cannot be met by an unknown value. (#KernelBootstrapV0/P4)
# ====================================================================
