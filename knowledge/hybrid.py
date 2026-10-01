"""Semantic seeds and registered bounded correction/lesson graph expansions."""

from __future__ import annotations

from .contracts import Entity, Relation, KnowledgeRetrievalRequest, ProjectionSnapshot
from .semantic import QueryEmbeddings

from .errors import invalid, not_ready
from .catalog import HYBRID_EDGES


def validate_edges(edges: list[Relation], repository_id: str, source_sha: str) -> None:
    """Reject relationship source provenance outside the authorized snapshot.

    Args:
        edges: Relationships whose source provenance must remain in scope.
        repository_id: Authorized canonical repository identity.
        source_sha: Exact immutable source commit expected by the request.
    """
    for edge in edges:
        if edge.source and (
            edge.source.repository_id != repository_id or edge.source.source_sha != source_sha
        ):
            invalid("foreign relationship provenance rejected")


class SemanticSearch:
    """Expand model-matched semantic seeds through registered graph relations."""

    def __init__(self, backend: object, embeddings: QueryEmbeddings) -> None:
        """Store injected dependencies without performing network operations.

        Args:
            backend: Injected backend implementing the registered query and generation operations.
            embeddings: Model-bound query-vector cache.
        """
        self.backend = backend
        self.embeddings = embeddings

    async def retrieve(
        self, request: KnowledgeRetrievalRequest, snapshot: ProjectionSnapshot
    ) -> tuple[list[Entity], dict, int]:
        """Execute a registered scoped request and return attributable bounded evidence.

        Args:
            request: Validated request including scope, operation and disclosure budgets.
            snapshot: Immutable generation manifest or source projection.

        Returns:
            tuple[list[Entity], dict, int]: Ordered seeds and expanded entities, per-entity provenance and total candidate work.
        """
        capabilities = await self.backend.capabilities()
        if not capabilities.get("semantic"):
            not_ready("backend semantic API unavailable")
        vector = await self.embeddings.vector(request.arguments["query_text"], snapshot)
        kind = "Lesson" if request.operation == "find_similar_lessons" else "Decision"
        seed_limit = request.budget.max_candidates
        if request.mode in {"hybrid", "precedent"}:
            seed_limit = min(
                request.budget.max_results,
                max(
                    1, request.budget.max_candidates // (request.budget.max_neighbors_per_seed + 1)
                ),
            )
        hits = await self.backend.semantic(
            request.repository_id,
            snapshot.generation_id,
            vector,
            [kind],
            seed_limit,
            snapshot.embedding_model,
        )
        nodes = []
        candidate_work = len(hits[: request.budget.max_candidates])
        provenance = {}
        for node, score in hits[: request.budget.max_candidates]:
            if (
                node.source.repository_id != request.repository_id
                or node.source.source_sha != snapshot.source_sha
            ):
                invalid("foreign semantic seed rejected before expansion")
            if node.kind != kind:
                continue
            if (
                request.arguments.get("status")
                and node.properties.get("status") != request.arguments["status"]
            ):
                continue
            if (
                request.arguments.get("decision_type")
                and node.properties.get("decision_type") != request.arguments["decision_type"]
            ):
                continue
            nodes.append(node)
            provenance[node.canonical_id] = {
                "signals": {"vector_similarity": score},
                "seed_id": node.canonical_id,
            }
        nodes.sort(
            key=lambda n: (
                -provenance[n.canonical_id]["signals"]["vector_similarity"],
                n.canonical_id,
            )
        )
        candidate_work = await self._expand(request, snapshot, nodes, provenance, candidate_work)
        return nodes, provenance, candidate_work

    async def _expand(
        self,
        request: KnowledgeRetrievalRequest,
        snapshot: ProjectionSnapshot,
        nodes: list[Entity],
        provenance: dict,
        candidate_work: int,
    ) -> int:
        """Expand approved correction and lesson links within remaining candidate work.

        Args:
            request: Hybrid mode and per-seed budgets.
            snapshot: Pinned generation used for relation provenance checks.
            nodes: Ordered seeds extended in place with relevant neighbors.
            provenance: Per-entity explanations extended in place.
            candidate_work: Candidates already consumed by semantic seed retrieval.

        Returns:
            int: Work consumed by both seeds and bounded neighbor expansions.
        """
        if request.mode in {"hybrid", "precedent"} and request.budget.max_hops:
            seeds = nodes[: min(request.budget.max_results, request.budget.max_candidates)]
            for seed in seeds:
                remaining = request.budget.max_candidates - candidate_work
                if remaining <= 0:
                    break
                neighbors, edges = await self.backend.neighbors(
                    request.repository_id,
                    snapshot.generation_id,
                    [seed.canonical_id],
                    HYBRID_EDGES,
                    min(request.budget.max_neighbors_per_seed, remaining),
                )
                validate_edges(edges, request.repository_id, snapshot.source_sha)
                candidate_work += max(len(neighbors), len(edges))
                for neighbor in neighbors[: min(request.budget.max_neighbors_per_seed, remaining)]:
                    paths = [
                        e
                        for e in edges
                        if e.source_id == seed.canonical_id and e.target_id == neighbor.canonical_id
                    ]
                    if paths and neighbor.canonical_id not in provenance:
                        nodes.append(neighbor)
                        provenance[neighbor.canonical_id] = {
                            "seed_id": seed.canonical_id,
                            "path": paths,
                            "signals": {"graph_hops": 1.0},
                        }
        return candidate_work
