"""MODULE: graph_population
GOAL: Bind reviewed population scope and retain it across authorized source disclosure.
BUSINESS CONTEXT: Reading source bodies must not erase enumeration limits or invent totals.
ARCHITECTURE: Pure binding and metadata transfer around the existing knowledge answer assessor.
"""
from __future__ import annotations

from integrations.retrieval_decision import RetrievalChoice
from kernel.contracts.payloads import RetrievalRequestPayload
from knowledge.answer_models import AnswerRequirements, AnswerScope
from knowledge.answers import assess_answer
from knowledge.contracts import KnowledgeRetrievalRequest, KnowledgeRetrievalResult


def selected_requirements(payload: RetrievalRequestPayload, choice: RetrievalChoice) -> dict | None:
    """Bind only the reviewed natural-descendants recipe; retain supplied obligations.

    Args:
        payload: Original question and any caller-supplied answer requirements.
        choice: Selected finite operation with Python-bound authorized root.

    Returns:
        Unchanged supplied requirements or the explicitly offered hierarchy definition.
    """
    if payload.answer_requirements is not None or choice.operation != "get_ac_descendants":
        return payload.answer_requirements
    return AnswerRequirements(original_question=payload.need.question, required_fields=["canonical_id"],
        scope=AnswerScope(population="ac_descendants", root_id=choice.arguments["root_id"],
                          levels=["L0", "L1", "L2", "L3"], inclusion="root_excluded"),
        require_complete=True).model_dump(mode="json")


def _complete_disclosure(discovery: KnowledgeRetrievalResult, result: KnowledgeRetrievalResult) -> bool:
    """Require the same complete population and immutable generation after disclosure."""
    expected = {item.entity.canonical_id for item in discovery.evidence}
    actual = {item.entity.canonical_id for item in result.evidence}
    return all((discovery.stats["population"].get("complete", False), expected == actual,
                discovery.generation_id == result.generation_id, discovery.source_sha == result.source_sha,
                discovery.status == "ok", result.status == "ok",
                not discovery.truncated, not discovery.continuation,
                not result.truncated, not result.continuation))


def preserve_population(discovery: KnowledgeRetrievalResult | None, result: KnowledgeRetrievalResult,
                        request: KnowledgeRetrievalRequest) -> None:
    """Carry authorized population facts into final disclosure without widening completeness.

    Args:
        discovery: First authorized population response, before source disclosure.
        result: Actual final bounded disclosure response, updated in place.
        request: Final request retaining original answer obligations.
    """
    if discovery is None or discovery is result:
        return
    population = dict(discovery.stats["population"])
    complete = _complete_disclosure(discovery, result)
    population["complete"] = bool(complete)
    result.stats["population"] = population
    result.warnings = list(dict.fromkeys([*discovery.warnings, *result.warnings]))
    if not complete:
        result.truncated = True
        result.warnings.append("population enumeration or subsequent disclosure remains incomplete")
        if result.status == "ok":
            result.status = "partial"
    result.answer = assess_answer(request, result)


# DECISION HISTORY
# ================================================================================
# - 2026-10-03 20:00 [python-coder]: Preserve reviewed population scope across permission-checked disclosure. (#TICKETLESS reason=user-approved-DK300-graph-routing)
