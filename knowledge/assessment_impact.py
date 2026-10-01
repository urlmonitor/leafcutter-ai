"""Declared-edge comparison across two supplied pinned retrieval results.
MODULE: knowledge.assessment_impact
GOAL: Compare only observed direct dependency populations with both revisions visible.
BUSINESS CONTEXT: A missing revision or truncated result cannot establish removed dependencies.
ARCHITECTURE: Neutral assessment of actual serialized retrieval outputs; no fallback source reads.
"""

from __future__ import annotations
from .contracts import KnowledgeRetrievalResult


def impact(payload: dict) -> dict:
    """Compare two established direct declared populations without inferring code impact.

    Args:
        payload: Repository scope plus before and after actual serialized retrieval results.

    Returns:
        Attributed revisions, observed subsets and differences only when comparison is complete.
    """
    before, before_ids, before_scope = _population(payload.get("before"), payload["repository_id"])
    after, after_ids, after_scope = _population(payload.get("after"), payload["repository_id"])
    comparable = bool(
        before
        and after
        and before_scope == after_scope
        and before_scope
        and after.source_sha == payload["source_sha"]
    )
    return {
        "kind": "impact",
        "status": "fulfilled" if comparable else "unresolved",
        "before_sha": before.source_sha if before else None,
        "after_sha": after.source_sha if after else None,
        "observed_before": sorted(before_ids),
        "observed_after": sorted(after_ids),
        "added": sorted(after_ids - before_ids) if comparable else None,
        "removed": sorted(before_ids - after_ids) if comparable else None,
        "relation": "depends_on",
        "direction": "incoming",
        "depth": 1,
        "complete_comparison": comparable,
        "complete_code_impact": False,
        "limitations": (
            [
                "both complete, matching declared populations and the requested after revision are required"
            ]
            if not comparable
            else []
        )
        + [
            "source differences are limited to inspected direct declarations; transitive and code-consumer impact uninspected"
        ],
    }


def _population(
    raw: dict | None, repository_id: str
) -> tuple[object | None, set[str], dict | None]:
    """Validate source, directed declaration provenance and enumeration completeness.

    Args:
        raw: One supplied actual serialized retrieval response, possibly absent.
        repository_id: Requested repository namespace.

    Returns:
        Parsed response, observed identities and comparable scope only when fully established.
    """
    if raw is None:
        return None, set(), None
    try:
        result = KnowledgeRetrievalResult.model_validate(raw)
    except ValueError:
        return None, set(), None
    ids = {item.entity.canonical_id for item in result.evidence}
    population = result.stats.get("population", {})
    complete = _complete_enumeration(result, population)
    if not complete or not _attributed(result, population, repository_id):
        return result, ids, None
    return (
        result,
        ids,
        {
            name: population.get(name)
            for name in (
                "population",
                "root_id",
                "levels",
                "inclusion",
                "relation",
                "direction",
                "depth",
            )
        },
    )


def _complete_enumeration(result: KnowledgeRetrievalResult, population: dict) -> bool:
    """Require complete population evidence rather than a final continuation slice.

    Args:
        result: Actual retrieval result, including optional question assessment.
        population: Backend and service population metadata.

    Returns:
        Whether the result establishes a whole pinned direct-dependency population.
    """
    return bool(
        result.status == "ok"
        and not result.truncated
        and not result.continuation
        and result.source_sha
        and result.generation_id
        and population.get("complete")
        and population.get("population") == "declared_dependents"
        and population.get("root_id")
        and (result.answer is None or result.answer.completeness.complete)
    )


def _attributed(result: KnowledgeRetrievalResult, population: dict, repository_id: str) -> bool:
    """Require every observed dependent's actual incoming declaration at the same revision.

    Args:
        result: Validated retrieval output containing observed declaration paths.
        population: Claimed direct incoming dependency scope to verify.
        repository_id: Required canonical repository namespace.

    Returns:
        Whether each observed dependent has matching source and directed edge provenance.
    """
    if (
        population.get("relation") != "depends_on"
        or population.get("direction") != "incoming"
        or population.get("depth") != 1
    ):
        return False
    for item in result.evidence:
        if (
            item.entity.source.repository_id != repository_id
            or item.entity.source.source_sha != result.source_sha
        ):
            return False
        supported = [
            edge
            for edge in item.path
            if edge.edge_type == "depends_on"
            and edge.source_id == item.entity.canonical_id
            and edge.target_id == population["root_id"]
            and edge.source
            and edge.source.source_sha == result.source_sha
            and edge.source.repository_id == repository_id
        ]
        if not supported:
            return False
    return True


# DECISION HISTORY
# - 2026-10-01 [python-coder]: Never replace a missing historical revision with current workspace facts. (#EPIC-RepositoryResearchAnswers/TICKET-20261001-KM-500f-1)
