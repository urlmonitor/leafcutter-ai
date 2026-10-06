"""MODULE: retrieval_needs_probe
GOAL: Evaluate all retrieval-needs dimensions in one actual Jev provider request.
BUSINESS CONTEXT: Test needs interpretation before changing the working retrieval flow.
ARCHITECTURE: One isolated LangGraph node uses the existing TypeSafe adapter with no retries.
"""
from __future__ import annotations

from typing import Any, NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph

from integrations.retrieval_needs_models import (
    MULTI_DIMENSIONS, NeedsCatalog, NeedsProbeResult, NeedsRequest, ProbeLimits,
)
from integrations.retrieval_needs_questions import CHOICES, build_needs_batch
from kernel.providers.base import JevBatch, JevInvalidResponse, JevResult
from kernel.providers.jev import JevTransport, TypeSafeJevAdapter
from kernel.providers.jev_errors import JevInvalidRequest
from kernel.providers.jev_wire import RawResponse

__all__ = ["NeedsCatalog", "NeedsProbeResult", "NeedsRequest", "ProbeLimits", "build_needs_batch", "run_needs_probe"]
Selections = dict[str, list[str]]


class _SingleSend:
    """Reject a second actual transport invocation even if future adapter behavior changes."""

    def __init__(self, transport: JevTransport) -> None:
        """Borrow the caller-owned transport; the caller retains resource ownership."""
        self.transport = transport
        self.name = transport.name
        self.version = transport.version
        self.calls = 0

    async def send(self, state: dict[str, Any], questions: dict[str, dict[str, Any]], *, purpose: str = "") -> RawResponse:
        """Send once and reject missing or surplus returned question IDs."""
        if self.calls:
            raise JevInvalidRequest("Standalone needs probe refuses a second provider request")
        self.calls += 1
        raw = await self.transport.send(state, questions, purpose=purpose)
        if set(raw.answers) != set(questions):
            raise JevInvalidResponse("Provider answer IDs must exactly match the submitted needs questions")
        return raw

    async def aclose(self) -> None:
        """Leave the borrowed transport open for its caller to close."""


class _ProbeState(TypedDict):
    """Only the immutable request and typed result enter the isolated graph."""

    request: NeedsRequest
    result: NotRequired[NeedsProbeResult]


def _selections(batch: JevBatch, result: JevResult, limits: ProbeLimits) -> tuple[Selections, Selections, Selections]:
    """Keep selected, rejected and uncertain alternatives separate for every dimension."""
    selected: Selections = {dimension: [] for dimension in MULTI_DIMENSIONS}
    uncertain: Selections = {dimension: [] for dimension in MULTI_DIMENSIONS}
    rejected: Selections = {dimension: [] for dimension in MULTI_DIMENSIONS}
    for spec in batch.questions:
        if "." not in spec.id:
            continue
        dimension, label = spec.id.split(".", 1)
        probability = result.noul(spec.id).probability
        bucket = selected if probability >= limits.selected_probability else rejected
        if limits.rejected_probability < probability < limits.selected_probability:
            bucket = uncertain
        bucket[dimension].append(label)
    return selected, uncertain, rejected


def _choice(result: JevResult, identifier: str, limits: ProbeLimits) -> str:
    """Treat low-confidence finite selections as unknown without guessing."""
    answer = result.choice(identifier)
    if answer.probabilities.get(answer.choice, 0) < limits.selected_probability:
        return "unknown"
    return answer.choice


def _missing_dimensions(selected: Selections, choices: dict[str, str]) -> list[str]:
    """Require subjects, source classes and detail while retaining discovery without IDs."""
    missing: list[str] = []
    if not selected["entity_types"]:
        missing.append("entity_types")
    missing.extend(key for key in ("detail_mode", "completeness") if choices[key] == "unknown")
    if choices["detail_mode"] == "fields" and not selected["required_fields"]:
        missing.append("required_fields")
    if not selected["document_types"]:
        missing.append("document_types")
    return missing


def _scope_gaps(selected: Selections, choices: dict[str, str]) -> list[str]:
    """Report incomplete explicit targets and missing choices without executing a human route."""
    missing: list[str] = []
    if choices["completeness"] in {"single_entity", "selected_entities"} and not selected["target_ids"]:
        missing.append("target_ids")
    if (choices["completeness"] == "selected_entities" and len(selected["target_ids"]) == 1
            and not selected["relationships"]):
        missing.append("multiple_target_ids")
    if choices["scope_resolution"] in {"unknown", "user_choice_missing"}:
        missing.append("scope_resolution")
    if choices["hierarchy_scope"] == "unknown" and choices["completeness"] in {"exhaustive_count", "exhaustive_set"}:
        missing.append("hierarchy_scope")
    return missing


def _unresolved(selected: Selections, choices: dict[str, str], result: JevResult, limits: ProbeLimits) -> list[str]:
    """Combine missing dimensions with explicit unsupported-catalog uncertainty."""
    missing = _missing_dimensions(selected, choices) + _scope_gaps(selected, choices)
    outside = result.noul("needs_outside_catalog").probability
    if outside > limits.rejected_probability:
        missing.append("needs_outside_catalog" if outside >= limits.selected_probability else "catalog_coverage_uncertain")
    return missing


def _result(request: NeedsRequest, batch: JevBatch, response: JevResult, calls: int, limits: ProbeLimits) -> NeedsProbeResult:
    """Retain raw distributions and the unchanged source need beside interpreted options."""
    selected, uncertain, rejected = _selections(batch, response, limits)
    choices = {identifier: _choice(response, identifier, limits) for identifier in CHOICES}
    unresolved = _unresolved(selected, choices, response, limits)
    return NeedsProbeResult(original_question=request.original_question, source_scope=request.source_scope,
        selections=selected, uncertain=uncertain, rejected=rejected,
        detail_mode=choices["detail_mode"], completeness=choices["completeness"],
        hierarchy_scope=choices["hierarchy_scope"], scope_resolution=choices["scope_resolution"],
        unresolved=unresolved,
        status="needs_resolution" if unresolved else "decided", response=response, provider_calls=calls,
        max_relation_depth=limits.max_relation_depth,
        limitations=["Needs interpretation only: no retrieval, availability check, final answer or fulfillment claim.",
            "Supplied context/known IDs are unverified candidates, not authority or permissions.",
            "The execution depth bound does not narrow semantic all-descendant requirements."])


async def run_needs_probe(request: NeedsRequest, transport: JevTransport, *, limits: ProbeLimits | None = None) -> NeedsProbeResult:
    """Run START -> determine_needs -> END with one batch and zero retries.

    The caller supplies and closes the existing provider transport. No tracing backend,
    retrieval adapter, global kernel configuration or production graph is modified.
    """
    limits = limits or ProbeLimits()
    request = NeedsRequest.model_validate(request.model_dump(mode="python"))
    batch = build_needs_batch(request)
    if len(batch.questions) > limits.max_questions_per_call:
        raise JevInvalidRequest(f"Needs batch has {len(batch.questions)} questions; one-call limit is {limits.max_questions_per_call}")
    single = _SingleSend(transport)
    adapter = TypeSafeJevAdapter(single, timeout_seconds=limits.timeout_seconds,
        max_questions_per_call=limits.max_questions_per_call, max_state_chars=limits.max_state_chars,
        max_retries=0, retry_backoff_seconds=0)

    async def determine_needs(state: _ProbeState) -> dict[str, NeedsProbeResult]:
        """Ask all independent dimensions once, then validate the resulting need."""
        response = await adapter.assess(batch)
        return {"result": _result(state["request"], batch, response, single.calls, limits)}

    graph = StateGraph(_ProbeState)
    graph.add_node("determine_needs", determine_needs)
    graph.add_edge(START, "determine_needs")
    graph.add_edge("determine_needs", END)
    initial_state: _ProbeState = {"request": request}
    result = await graph.compile().ainvoke(initial_state)
    return result["result"]


# DECISION HISTORY
# ================================================================================
# - 2026-10-03 00:00 [python-coder]: Enforce one physical send in an isolated LangGraph experiment. (#TICKETLESS reason=user-requested-standalone-experiment)
# - 2026-10-05 06:33 [python-coder]: Type the pre-result graph state and explicit result choices without changing probe decisions. (#TICKETLESS reason=user-authorized-release-typecheck-repair)
