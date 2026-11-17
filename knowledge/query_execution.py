"""Execute compiler-owned Cypher using scoped bound values and existing transactions.

DECISION HISTORY
- 2026-10-01 15:46 [python-coder]: No host or Jev text reaches executable Cypher. (#KM-500/TICKET-20261001-KM-500b-2)

MODULE: knowledge.query_execution
GOAL: Provide the scoped knowledge retrieval query_execution responsibility.
BUSINESS CONTEXT: Make attributable research capabilities reusable and explicitly governed.
ARCHITECTURE: Dependencies point inward to neutral contracts; see docs/architecture/components/knowledge-retrieval.md.
"""

from __future__ import annotations

from .contracts import Entity, ProjectionSnapshot
from .ports import CompiledQueryBackend

from .query_compile import compile_query
from .query_models import QueryDescriptor, validate_arguments
from .adapters.neo4j_backend import scope_key, entity_from_row
from .errors import invalid, KnowledgeError


class QueryRows(list[Entity]):
    """Bounded entities with measured expansion-saturation metadata."""

    def __init__(self, entities: list[Entity], truncated: bool) -> None:
        """Store query results and the lookahead outcome.

        Args:
            entities: Scoped canonical entities.
            truncated: Whether an actual fanout or result limit hid candidates.
        """
        super().__init__(entities)
        self.truncated = truncated


async def execute_query(
    backend: CompiledQueryBackend,
    descriptor: QueryDescriptor,
    repository_id: str,
    generation_id: str,
    arguments: dict,
    limit: int = 200,
    fanout: int = 10,
) -> QueryRows:
    """Execute only compiled parameterized reads of a ready scoped generation.

    Args:
        backend: Trusted database adapter owning transactions and deadlines.
        descriptor: Verified operation contract or candidate under independent admission.
        repository_id: Trusted namespace.
        generation_id: Pinned generation within that namespace.
        arguments: Validated values, never database syntax.
        limit: Candidate result cap.
        fanout: Per-seed expansion bound, clamped to the compiler maximum.

    Returns:
        Canonical entities with verified repository/revision provenance.
    """
    validate_arguments(descriptor, arguments)
    manifest = await backend.get_generation(repository_id, generation_id)
    if manifest is None:
        raise KnowledgeError("stale", "query generation is not retained")
    validate_mapping(descriptor, manifest)
    compiled = compile_query(descriptor)
    params = {
        **compiled["constants"],
        "scope_key": scope_key(repository_id, generation_id),
        "result_limit": max(1, min(limit, 200)),
        "fanout": max(1, min(fanout, 10)),
    }
    params.update({"arg_" + name: arguments.get(name) for name in descriptor.parameters})
    params["probe_fanout"] = params["fanout"] + 1
    rows = await backend._run(compiled["cypher"], params)
    truncated = True
    if rows and "payloads" in rows[0]:
        truncated = bool(rows[0]["expansion_truncated"])
        rows = [{"payload": payload} for payload in rows[0]["payloads"]]
    entities = [entity_from_row(row) for row in rows]
    for entity in entities:
        if (
            entity.source.repository_id != repository_id
            or entity.source.source_sha != manifest.source_sha
        ):
            invalid("compiled query result crossed repository or generation scope")
    if len(entities) > params["result_limit"]:
        invalid("compiled query exceeded result limit")
    return QueryRows(entities, truncated)


def validate_mapping(descriptor: QueryDescriptor, manifest: ProjectionSnapshot) -> None:
    """Reject absent canonical memory mapping before issuing a query.

    Args:
        descriptor: Authored recipe with explicit or implicit endpoint kinds.
        manifest: Published generation's supported source kinds.
    """
    kinds = {descriptor.recipe.seed_kind, *(step.kind for step in descriptor.recipe.steps)} - {None}
    for step in descriptor.recipe.steps:
        if step.edge_type in {"ABOUT", "CORRECTED_BY", "TAUGHT", "USED_EVIDENCE"}:
            kinds.add("Decision")
        if step.edge_type == "TAUGHT":
            kinds.add("Lesson")
    if manifest.supported_kinds and kinds - set(manifest.supported_kinds):
        raise KnowledgeError(
            "unsupported", "query has no approved source mapping for requested kinds"
        )
