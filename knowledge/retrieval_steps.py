"""Scoped generation selection, candidate fetching and evidence assembly steps.
MODULE: knowledge.retrieval_steps
GOAL: Provide the scoped knowledge retrieval retrieval_steps responsibility.
BUSINESS CONTEXT: Make attributable research capabilities reusable and explicitly governed.
ARCHITECTURE: Dependencies point inward to neutral contracts; see docs/architecture/components/knowledge-retrieval.md.
"""

from __future__ import annotations
from typing import TYPE_CHECKING
from .contracts import (
    KnowledgeRetrievalRequest,
    KnowledgeRetrievalResult,
    ProjectionSnapshot,
    Entity,
)

if TYPE_CHECKING:
    from .service import KnowledgeService
from .errors import KnowledgeError, invalid, not_ready
from .catalog import HYBRID_EDGES
from .hybrid import SemanticSearch, validate_edges
from .disclosure import evidence


async def load_generation(
    service: KnowledgeService,
    request: KnowledgeRetrievalRequest,
    out: KnowledgeRetrievalResult,
    state: dict | None,
) -> ProjectionSnapshot | None:
    """Resolve a published generation and enforce revision and source-kind scope.

    Args:
        service: Owner of the generation backend and cancellation probe.
        request: Authorized scope, revision and operation.
        out: Result receiving generation identity and stale diagnostics.
        state: Verified continuation state, if resuming.

    Returns:
        ProjectionSnapshot | None: Eligible manifest, or None when no permitted snapshot is available.
    """
    if service.cancel_probe():
        raise KnowledgeError("unavailable", "retrieval cancelled")
    snapshot = (
        (await service.backend.get_generation(request.repository_id, state["generation_id"]))
        if state
        else await service.backend.active(request.repository_id)
    )
    if snapshot is None:
        out.status = "stale"
        out.warnings.append("pinned generation expired" if state else "no published generation")
        return None
    if not state and request.revision != "latest" and request.revision != snapshot.source_sha:
        resolver = getattr(service.backend, "get_revision", None)
        retained = await resolver(request.repository_id, request.revision) if resolver else None
        if retained is not None:
            snapshot = retained
    if snapshot.repository_id != request.repository_id:
        invalid("backend generation crossed repository scope")
    out.source_sha = snapshot.source_sha
    out.generation_id = snapshot.generation_id
    out.stats["mapper_version"] = snapshot.mapper_version
    if request.revision != "latest" and request.revision != snapshot.source_sha:
        out.status = "stale"
        out.warnings.append("requested revision is not published")
        if not request.allow_stale:
            return None
    target_kinds = {
        "get_related_policies": "Policy",
        "get_previous_decisions": "Decision",
        "get_corrected_decisions": "Decision",
        "get_related_lessons": "Lesson",
        "get_decision_evidence": "Decision",
        "find_similar_decisions": "Decision",
        "find_similar_lessons": "Lesson",
    }
    required_kind = target_kinds.get(request.operation)
    if snapshot.supported_kinds and required_kind and required_kind not in snapshot.supported_kinds:
        not_ready("operation has no approved source mapping")
    return snapshot


async def fetch_candidates(
    service: KnowledgeService,
    request: KnowledgeRetrievalRequest,
    out: KnowledgeRetrievalResult,
    snapshot: ProjectionSnapshot,
    remaining_candidates: int,
    offset: int,
) -> tuple[list[Entity], dict, int | None]:
    """Fetch a bounded registered graph query or model-matched semantic seeds.

    Args:
        service: Owner of backend and query embeddings.
        request: Registered operation and work limits.
        out: Result receiving semantic model and shortfall diagnostics.
        snapshot: Published generation pinned for this page.
        remaining_candidates: Cumulative candidate budget still available.
        offset: Number of previously disclosed candidates.

    Returns:
        tuple[list[Entity], dict, int | None]: Candidates, semantic provenance, and semantic work count; graph work is counted after deduplication.
    """
    if request.operation in {"get_ac_descendants", "get_declared_dependents"}:
        from .populations import retrieve_population

        return await retrieve_population(
            service.backend, request, out, snapshot, remaining_candidates
        )
    if request.operation_digest and request.operation_digest != "builtin:1":
        from .query_execution import execute_query
        from .ports import CompiledQueryBackend

        if not isinstance(service.backend, CompiledQueryBackend):
            not_ready("backend does not support compiled catalog queries")

        if service.query_catalog is None:
            invalid("registered operation requires a query catalog")
        descriptor = service.query_catalog.get(
            request.operation, request.operation_version, request.operation_digest
        )
        query_rows = await execute_query(
            service.backend,
            descriptor,
            request.repository_id,
            snapshot.generation_id,
            request.arguments,
            min(remaining_candidates, offset + request.budget.max_results + 1),
            request.budget.max_neighbors_per_seed,
        )
        if query_rows.truncated:
            out.warnings.append("query expansion or result bound reached; omitted total unknown")
            out.truncated = True
            out.status = "partial"
        out.stats["recipe_expansion_truncated"] = query_rows.truncated
        return query_rows, {}, None
    if request.mode in {"semantic", "hybrid"} or request.operation.startswith("find_similar"):
        rows, provenance, semantic_work = await SemanticSearch(
            service.backend, service.embeddings
        ).retrieve(
            request.model_copy(
                update={
                    "budget": request.budget.model_copy(
                        update={"max_candidates": remaining_candidates}
                    )
                }
            ),
            snapshot,
        )
        out.stats["embedding_model"] = snapshot.embedding_model
        if len(rows) < request.budget.max_candidates:
            out.warnings.append(
                "bounded semantic candidate search may have shortfall after filters; no completeness guarantee"
            )
    else:
        rows = await service.backend.query(
            request.repository_id,
            snapshot.generation_id,
            request.operation,
            request.arguments,
            min(remaining_candidates, offset + request.budget.max_results + 1),
        )
        provenance = {}
        semantic_work = None
    return rows, provenance, semantic_work


async def disclose_candidates(
    service: KnowledgeService,
    request: KnowledgeRetrievalRequest,
    out: KnowledgeRetrievalResult,
    snapshot: ProjectionSnapshot,
    selected: list[Entity],
    provenance: dict,
    used: int,
    remaining_candidates: int,
    candidate_work: int,
) -> int:
    """Append bounded entity evidence and selected canonical relationship context.

    Args:
        service: Owner of the backend, source reader and cancellation probe.
        request: Disclosure level and resource limits.
        out: Result receiving evidence, truncation and partial status.
        snapshot: Immutable generation used to verify provenance.
        selected: Ordered entities selected for this page.
        provenance: Existing semantic seed or path explanation by entity ID.
        used: Content bytes consumed by prior pages.
        remaining_candidates: Candidate budget available for this page.
        candidate_work: Work already consumed by primary candidate selection.

    Returns:
        int: Total candidate work including structural neighbors and edges.
    """
    for node in selected:
        if service.cancel_probe():
            raise KnowledgeError("unavailable", "retrieval cancelled")
        item = await evidence(
            node,
            request,
            provenance.get(node.canonical_id, {}),
            max(
                64,
                (
                    min(
                        request.budget.max_content_bytes - used,
                        request.budget.max_estimated_tokens * 4,
                    )
                    - 1600
                )
                // max(1, len(selected)),
            ),
            source_resolver=service.source_resolver,
        )
        if item.limitations:
            out.status = "partial"
            out.truncated = True
        if _include_context(request, candidate_work, remaining_candidates):
            neighbors, edges = await service.backend.neighbors(
                request.repository_id,
                snapshot.generation_id,
                [node.canonical_id],
                HYBRID_EDGES,
                min(request.budget.max_neighbors_per_seed, remaining_candidates - candidate_work),
            )
            validate_edges(edges, request.repository_id, snapshot.source_sha)
            candidate_work += max(len(neighbors), len(edges))
            for neighbor in neighbors[: request.budget.max_neighbors_per_seed]:
                if (
                    neighbor.source.repository_id != request.repository_id
                    or neighbor.source.source_sha != snapshot.source_sha
                ):
                    invalid("foreign structural neighbor rejected")
                item.related.append(
                    {
                        "canonical_id": neighbor.canonical_id,
                        "title": neighbor.title,
                        "kind": neighbor.kind,
                    }
                )
            ids = {r["canonical_id"] for r in item.related} | {node.canonical_id}
            item.relationships = [e for e in edges if e.source_id in ids and e.target_id in ids][
                : request.budget.max_neighbors_per_seed
            ]
            if node.properties.get("status") in {"corrected", "superseded"} and not any(
                e.edge_type in {"CORRECTED_BY", "SUPERSEDED_BY"} for e in item.relationships
            ):
                item.limitations.append("correction reference unresolved in retrieved scope")
        out.evidence.append(item)
    return candidate_work


def _include_context(request, candidate_work, remaining_candidates):
    """Reserve population work for enumeration rather than optional neighboring context."""
    return (
        request.disclosure_level >= 1
        and candidate_work < remaining_candidates
        and request.operation not in {"get_ac_descendants", "get_declared_dependents"}
    )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 15:46 [python-coder]: Bind verified reusable query versions through scoped retrieval. (#KM-500/TICKET-20261001-KM-500b-3)

# - 2026-10-01 [python-coder]: Preserve question evidence and explicit source support through bounded research. (#KM-500/KM-500e-2)
