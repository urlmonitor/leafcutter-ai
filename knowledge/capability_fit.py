"""Source-aware query fitness without query creation side effects.
MODULE: knowledge.capability_fit
GOAL: Distinguish reusable operations from absent mappings and missing query recipes.
BUSINESS CONTEXT: Generating another query cannot manufacture unavailable evidence.
ARCHITECTURE: Pure assessment of explicit pinned manifest metadata.
"""

from __future__ import annotations

from .contracts import ProjectionSnapshot


def assess_capability_fit(
    manifest: ProjectionSnapshot | dict,
    *,
    required_kinds: list[str],
    required_relationships: list[str],
    required_fields: dict[str, list[str]],
    matching_operation: str | None,
    catalog_complete: bool,
) -> dict:
    """Classify source support before any governed query-build dispatch.

    Args:
        manifest: Published manifest model or serializable pinned metadata.

    Returns:
        dict: Classified gap and query-only build eligibility with explicit unknowns.

    Keyword-only required_kinds: Canonical kinds demanded by the question.
    Keyword-only required_relationships: Actual declared relationships needed.
    Keyword-only required_fields: Required fields grouped by canonical kind.
    Keyword-only matching_operation: Established compatible registered operation.
    Keyword-only catalog_complete: Whether the authorized catalog search completed.
    """
    data = manifest if isinstance(manifest, dict) else manifest.model_dump()
    kinds = data.get("supported_kinds", [])
    fields = data.get("supported_fields", {})
    relationships = data.get("supported_relationships", [])
    missing_kinds = sorted(set(required_kinds) - set(kinds))
    missing_relations = sorted(set(required_relationships) - set(relationships))
    missing_fields = {
        kind: sorted(set(names) - set(fields.get(kind, [])))
        for kind, names in required_fields.items()
    }
    missing_fields = {kind: names for kind, names in missing_fields.items() if names}
    limits = []
    if (
        not data.get("source_sha")
        or not data.get("generation_id")
        or not kinds
        or ((required_fields or required_relationships) and not fields)
    ):
        state = "unknown"
        limits.append("pinned generation mapping metadata is not established")
    elif missing_kinds or missing_relations:
        state = "unsupported_mapping"
    elif missing_fields:
        state = "field_availability_gap"
    elif matching_operation:
        state = "supported"
    elif not catalog_complete:
        state = "unknown"
        limits.append("authorized catalog search is incomplete")
    else:
        state = "missing_query"
    return {
        "status": state,
        "query_build_eligible": state == "missing_query",
        "matching_operation": matching_operation,
        "source_sha": data.get("source_sha"),
        "generation_id": data.get("generation_id"),
        "missing_kinds": missing_kinds,
        "missing_relationships": missing_relations,
        "missing_fields": missing_fields,
        "limitations": limits,
        "authorization": "query build and activation require existing separate authorization",
    }


# DECISION HISTORY
# - 2026-10-01 [python-coder]: Use pinned source support before governed query-only growth. (#EPIC-RepositoryResearchAnswers/TICKET-20261001-KM-500e-4)
