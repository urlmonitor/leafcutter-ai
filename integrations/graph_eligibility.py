"""MODULE: graph_eligibility
GOAL: Exclude only proved result-population contradictions before semantic selection.
BUSINESS CONTEXT: Preserve potentially useful reads while excluding proved answer-contract mismatches.
ARCHITECTURE: Pure contract facts over bound offers; no provider, source or authority changes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from pydantic import JsonValue

from integrations.retrieval_relationships import relation_role
from kernel.contracts.payloads import RetrievalRequestPayload
from knowledge.answer_models import AnswerRequirements
from knowledge.query_models import QueryRecipe

if TYPE_CHECKING:
    from integrations.graph_offers import GraphOffer


@dataclass(frozen=True)
class OperationResult:
    """Authoritative result shape, independent of description and source availability."""

    population: Literal["exact_entities", "ac_descendants", "declared_dependents",
                        "related_entities", "recipe_endpoints", "mixed_entities", "relevance"]
    result_kind: str | None = None
    relationship: str | None = None


_BUILTINS = {
    "get_entities": OperationResult("exact_entities"),
    "get_ac_descendants": OperationResult("ac_descendants", "AcceptanceCriterion", "all_descendants"),
    "get_declared_dependents": OperationResult("declared_dependents", "AcceptanceCriterion", "declared_dependents"),
    "get_related_tests": OperationResult("related_entities", "Test", "covered_by"),
    "get_component_context": OperationResult("mixed_entities", relationship="component_context"),
    "get_acceptance_criteria": OperationResult("related_entities", "AcceptanceCriterion", "component_membership"),
    "get_relevant_adrs": OperationResult("related_entities", "ADR", "governing_adrs"),
    "get_previous_decisions": OperationResult("related_entities", "Decision", "ABOUT"),
    "get_corrected_decisions": OperationResult("related_entities", "Decision", "CORRECTED_BY"),
    "get_related_lessons": OperationResult("related_entities", "Lesson", "TAUGHT"),
    "get_decision_evidence": OperationResult("related_entities", relationship="USED_EVIDENCE"),
    "find_similar_decisions": OperationResult("relevance", "Decision"),
    "find_similar_lessons": OperationResult("relevance", "Lesson"),
}
_KINDS = {"ac": "AcceptanceCriterion", "adr": "ADR", "ticket": "Ticket", "component": "Component",
          "flow": "Flow", "decision": "Decision", "test": "Test", "document": "Document"}
_SOURCE_FIELDS = {"criteria", "test_spec", "content"}


def builtin_result_contract(operation: str) -> OperationResult | None:
    """Describe fixed retrieval_steps/populations/backend contracts, never inferred prose."""
    return _BUILTINS.get(operation)


def recipe_result_contract(recipe: QueryRecipe) -> OperationResult:
    """Describe a pinned recipe's endpoints without inventing population metadata.

    Args:
        recipe: Admitted structural recipe, independent of its authored description.

    Returns:
        Seed or path endpoints; paths can return seeds and do not establish named populations.
    """
    if not recipe.steps:
        return OperationResult("exact_entities", recipe.seed_kind)
    endpoint = recipe.steps[-1]
    relation = endpoint.edge_type if len(recipe.steps) == 1 else None
    return OperationResult("recipe_endpoints", endpoint.kind, relation)


def _requested_population(payload: RetrievalRequestPayload, requirements: AnswerRequirements | None) -> str | None:
    """Distinguish original result identities from relation anchors and unspecified scope.

    Args:
        payload: Typed request preserving distinct anchor and requested result roles.
        requirements: Validated original fields and population, if available.

    Returns:
        The requested result population, or None when no population is established.
    """
    if requirements is None:
        return None
    scope = requirements.scope
    if scope.population != "returned_entities":
        return scope.population
    if scope.entity_ids:
        return "exact_entities"
    if relation_role(payload.retrieval_needs) is not None:
        return "related_entities"
    return None


def _population_fit(expected: str | None, actual: OperationResult | None) -> tuple[str, str]:
    """Reject unsupported named scopes without equating population labels to disjoint identities.

    Args:
        expected: Established result population, not incidental recognized identities.
        actual: Explicit operation result contract, absent for legacy offers.

    Returns:
        Eligibility status and a compact attributable explanation, not a completeness verdict.
    """
    if expected is None or actual is None:
        return "unknown", "Requested or operation population metadata is absent."
    if expected == actual.population:
        return "eligible", "Result population matches; source availability and completeness remain unverified."
    if expected in {"ac_descendants", "declared_dependents"}:
        return "incompatible", "Operation cannot establish the requested named population metadata."
    if actual.population == "ac_descendants" and expected == "exact_entities":
        return "incompatible", "Hierarchy execution requires a named hierarchy scope, not exact identity scope."
    return "unknown", "Result identities can overlap; actual evidence must establish requested coverage."


def _kind_mismatch(payload: RetrievalRequestPayload, actual: OperationResult | None) -> bool:
    """Reject only a known disjoint result kind; anchors and result kinds stay distinct."""
    needs = payload.retrieval_needs
    if needs is None or actual is None or actual.result_kind is None:
        return False
    requested = {_KINDS.get(label) for label in needs.selections["entity_types"]} - {None}
    return bool(requested) and actual.result_kind not in requested


def operation_fit(offers: dict[str, GraphOffer], payload: RetrievalRequestPayload,
                  requirements: AnswerRequirements | None) -> dict[str, JsonValue]:
    """Record fit for every bound offer without changing the original answer obligations.

    Args:
        offers: Actual bound operations with optional authoritative result contracts.
        payload: Original typed meanings and permitted literal targets.
        requirements: Already validated original question, fields and population.

    Returns:
        JSON facts for the existing paid selector; only incompatible rows are removed.
    """
    expected = _requested_population(payload, requirements)
    source_fields = [field for field in requirements.required_fields if field in _SOURCE_FIELDS] if requirements else []
    facts: dict[str, JsonValue] = {}
    for name, offer in offers.items():
        result = offer.result_contract
        status, reason = _population_fit(expected, result)
        if _kind_mismatch(payload, result):
            status, reason = "incompatible", "Operation result kind differs from the requested record kind."
        facts[name] = {"status": status, "population": result.population if result else None,
            "result_kind": result.result_kind if result else None,
            "relationship": result.relationship if result else None,
            "source_hydration_fields": source_fields, "reason": reason}
    return facts


# DECISION HISTORY
# ================================================================================
# - 2026-10-10 10:51 [python-coder]: Separate proved contract mismatches from unknown identity overlap and eventual completeness. (#KM-500/KM-500a-2-i)
