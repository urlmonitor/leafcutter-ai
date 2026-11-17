"""MODULE: retrieval_relationships
GOAL: Preserve finite registered relationship reads through typed needs.
BUSINESS CONTEXT: An anchor and the returned records have different roles.
ARCHITECTURE: Pure finite contract checks; no traversal or query construction.
"""
from __future__ import annotations

from kernel.contracts.retrieval_needs import RetrievalNeedsOutput

# relation: (canonical seed kind, optional required result kind, registered operation)
ROLES = {
    "covered_by": ("AcceptanceCriterion", "test", "get_related_tests"),
    "governing_adrs": ("Component", "adr", "get_relevant_adrs"),
    "component_context": ("Component", None, "get_component_context"),
}


def relation_role(needs: RetrievalNeedsOutput | None) -> tuple[str, str | None, str] | None:
    """Return one supported relation role without conflating result and seed kinds."""
    relationships = needs.selections["relationships"] if needs is not None else []
    return ROLES.get(relationships[0]) if len(relationships) == 1 else None


def validate_relation(needs: RetrievalNeedsOutput) -> bool:
    """Require one explicit anchor and bounded examples for existing relation recipes.

    Args:
        needs: Accepted question interpretation, still not a retrieved answer.

    Returns:
        Whether the interpretation selects a finite registered relationship recipe.

    Raises:
        ValueError: Anchors, result kinds or completeness exceed the existing recipe.
    """
    role = relation_role(needs)
    if role is None:
        return False
    if len(needs.selections["target_ids"]) != 1:
        raise ValueError("unsupported_relationship: this bounded path requires one original anchor; it cannot narrow multiple anchors")
    if role[1] is not None and needs.selections["entity_types"] != [role[1]]:
        raise ValueError("unsupported_content_types: the requested relation and result kind differ")
    if needs.completeness != "examples":
        raise ValueError("unsupported_population: bounded relationship reads do not establish an exhaustive set or count")
    return True


# DECISION HISTORY
# ================================================================================
# - 2026-10-09 20:15 [python-coder]: Keep registered relationship anchors, returned kinds and examples-only limits distinct. (#KM-500/KM-500e-1-i)
