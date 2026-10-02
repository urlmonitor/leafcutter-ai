"""MODULE: neo4j_queries
GOAL: Execute a finite reviewed catalog with explicit scope and work bounds.
BUSINESS CONTEXT: Prompt text is never executable database syntax.
ARCHITECTURE: Parameter-only read recipes over immutable projection entities.

DECISION HISTORY
========================================
- 2026-10-01 12:00 [python-coder]: Preserve relationship fields as data, not generated Cypher. (#TICKET-KM-400a-3)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from knowledge.contracts import Entity
    from knowledge.adapters.neo4j_backend import Neo4jBackend

from knowledge.adapters.neo4j_backend import scope_key, entity_from_row
from knowledge.contracts import Relation
from knowledge.errors import NotReady, KnowledgeError

# Fixed direction and endpoint kinds are part of this versioned catalog.
CATALOG = {
    "get_declared_dependents": ("depends_on", "AcceptanceCriterion", "incoming"),
    "get_acceptance_criteria": ("component_membership", "AcceptanceCriterion", "incoming"),
    "get_relevant_adrs": ("component_membership", "ADR", "incoming"),
    "get_related_tests": ("covered_by", "Test", "outgoing"),
    "get_previous_decisions": ("ABOUT", "Decision", "incoming"),
    "get_corrected_decisions": ("CORRECTED_BY", "Decision", "outgoing"),
    "get_related_lessons": ("TAUGHT", "Lesson", "outgoing"),
    "get_decision_evidence": ("USED_EVIDENCE", None, "outgoing"),
}


def bounded_limit(limit: int) -> int:
    """Clamp internal work to the server maximum and reject negative values."""
    if not isinstance(limit, int) or limit < 1:
        raise ValueError("limit must be positive")
    return min(limit, 200)


async def query(
    db: Neo4jBackend,
    repository_id: str,
    generation_id: str,
    operation: str,
    arguments: dict[str, object],
    limit: int,
) -> list[Entity]:
    """Dispatch only registered exact or one-hop recipes.

    Args:
        db: Scoped Neo4j adapter owning the driver and transaction policy.
        repository_id: Trusted repository namespace that isolates all reads and writes.
        generation_id: Immutable generation identifier within the repository.
        operation: Registered query operation; never arbitrary caller Cypher.
        arguments: Bound operation parameters passed separately from query text.
        limit: Maximum result count after enforcing the adapter bound.

    Returns:
        Matching canonical entities in the scoped generation, bounded by limit.
    """
    manifest = await db.get_generation(repository_id, generation_id)
    if manifest is None:
        raise KnowledgeError("stale", "generation no longer available")
    key = scope_key(repository_id, generation_id)
    params = {
        "key": key,
        "limit": bounded_limit(limit),
        "ids": arguments.get("entity_ids", [arguments.get("component_id")]),
    }
    if operation == "get_entities":
        rows = await db._run(
            "MATCH (n:KREntity {generation_key:$key}) WHERE n.canonical_id IN $ids RETURN n.payload AS payload ORDER BY n.canonical_id LIMIT $limit",
            params,
        )
        return [entity_from_row(row) for row in rows]
    if operation == "_get_ac_children":
        if "structural_parent" not in manifest.supported_fields.get("AcceptanceCriterion", []):
            raise NotReady("generation does not establish the canonical parent mapping")
        rows = await db._run(
            "MATCH (n:KREntity {generation_key:$key,kind:'AcceptanceCriterion'}) WHERE n.parent_id IN $ids RETURN n.payload AS payload ORDER BY n.canonical_id LIMIT $limit",
            params,
        )
        return [entity_from_row(row) for row in rows]
    if operation == "get_component_context":
        nodes, _ = await neighbors(
            db,
            repository_id,
            generation_id,
            params["ids"],
            ["component_membership", "depends_on", "covered_by", "implemented_by", "related_docs"],
            limit,
        )
        seeds = await query(
            db, repository_id, generation_id, "get_entities", {"entity_ids": params["ids"]}, limit
        )
        return (seeds + nodes)[:limit]
    if operation not in CATALOG:
        raise NotReady("operation has no approved canonical mapping")
    edge_type, kind, direction = CATALOG[operation]
    if kind and kind not in manifest.supported_kinds:
        raise NotReady("operation has no approved canonical mapping")
    if operation == "get_decision_evidence" and "Decision" not in manifest.supported_kinds:
        raise NotReady("operation has no approved canonical memory mapping")
    params.update(
        edge_type=edge_type,
        kind=kind,
        status=arguments.get("status"),
        decision_type=arguments.get("decision_type"),
    )
    arrow = "<-[r:KR_LINK]-" if direction == "incoming" else "-[r:KR_LINK]->"
    # The final limit alone is not our work limit: each seed expansion is bounded first.
    rows = await db._run(
        "UNWIND $ids AS id MATCH (s:KREntity {generation_key:$key,canonical_id:id}) CALL { WITH s MATCH (s)"
        + arrow
        + "(n:KREntity {generation_key:$key}) WHERE r.generation_key=$key AND r.edge_type=$edge_type AND ($kind IS NULL OR n.kind=$kind) AND ($status IS NULL OR n.status=$status) AND ($decision_type IS NULL OR n.decision_type=$decision_type) RETURN n ORDER BY n.canonical_id LIMIT $limit } RETURN DISTINCT n.payload AS payload,n.canonical_id AS id ORDER BY id LIMIT $limit",
        params,
    )
    return [entity_from_row(row) for row in rows]


async def neighbors(
    db: Neo4jBackend,
    repository_id: str,
    generation_id: str,
    entity_ids: list[str],
    edge_types: list[str],
    limit: int,
) -> tuple[list[Entity], list[Relation]]:
    """Bound each seed's expansion before combining its outgoing and incoming paths.

    Args:
        db: Scoped Neo4j adapter owning the driver and transaction policy.
        repository_id: Trusted repository namespace that isolates all reads and writes.
        generation_id: Immutable generation identifier within the repository.
        entity_ids: Canonical seed IDs within the selected generation.
        edge_types: Allowlisted relationship labels requested for expansion.
        limit: Maximum result count after enforcing the adapter bound.

    Returns:
        Bounded neighboring entities and their original directed relationships.
    """
    if await db.get_generation(repository_id, generation_id) is None:
        raise KnowledgeError("stale", "generation no longer available")
    params = {
        "key": scope_key(repository_id, generation_id),
        "ids": entity_ids[:200],
        "types": edge_types,
        "limit": bounded_limit(limit),
    }
    rows = await db._run(
        "UNWIND $ids AS id MATCH (s:KREntity {generation_key:$key,canonical_id:id}) CALL { WITH s MATCH (s)-[r:KR_LINK]-(n:KREntity {generation_key:$key}) WHERE r.generation_key=$key AND r.edge_type IN $types RETURN n,r ORDER BY n.canonical_id,r.key LIMIT $limit } RETURN n.payload AS payload,r.payload AS relation ORDER BY n.canonical_id LIMIT $limit",
        params,
    )
    nodes = {row["payload"]: entity_from_row(row) for row in rows}
    relations = [Relation.model_validate_json(row["relation"]) for row in rows]
    return list(nodes.values()), relations


# - 2026-10-01 [python-coder]: Preserve question evidence and explicit source support through bounded research. (#KM-500/KM-500e-2)
