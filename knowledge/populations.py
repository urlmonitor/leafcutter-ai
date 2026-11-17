"""Finite canonical populations over fixed read operations.
MODULE: knowledge.populations
GOAL: Enumerate explicit AC hierarchy and declared dependency scopes within budgets.
BUSINESS CONTEXT: A bounded subset must not be reported as an exhaustive status count.
ARCHITECTURE: Parent-field traversal and incoming depends_on only; no caller Cypher.
"""

from __future__ import annotations

from .ports import KnowledgeBackend
from .contracts import (
    Relation,
    Entity,
    KnowledgeRetrievalRequest,
    KnowledgeRetrievalResult,
    ProjectionSnapshot,
)
from .answer_models import AnswerScope


async def retrieve_population(
    backend: KnowledgeBackend,
    request: KnowledgeRetrievalRequest,
    out: KnowledgeRetrievalResult,
    snapshot: ProjectionSnapshot,
    remaining: int,
) -> tuple[list[Entity], dict, int]:
    """Fetch one explicitly scoped population and retain enumeration limitations.

    Args:
        backend: Selected scoped backend.
        request: Validated public query and explicit question scope.
        out: Result collecting actual population identity.
        snapshot: Pinned immutable manifest.
        remaining: Remaining cumulative candidate-work allowance.

    Returns:
        Tuple of actual entities, relationship provenance and consumed work.
    """
    if request.operation == "get_declared_dependents":
        return await _dependents(backend, request, out, snapshot, remaining)
    root_id = request.arguments["root_id"]
    scope = request.answer_requirements.scope if request.answer_requirements else None
    definition = {
        "population": "ac_descendants",
        "root_id": root_id,
        "levels": scope.levels if scope else None,
        "inclusion": scope.inclusion if scope else None,
        "relation": "structural_parent",
        "direction": "children",
        "complete": False,
    }
    out.stats["population"] = definition
    if (
        not scope
        or scope.population != "ac_descendants"
        or scope.root_id != root_id
        or scope.levels is None
        or scope.inclusion is None
    ):
        out.status = "partial"
        out.warnings.append("clarify hierarchy root, levels and root/terminal-leaf inclusion")
        return [], {}, 0
    roots = await backend.query(
        request.repository_id, snapshot.generation_id, "get_entities", {"entity_ids": [root_id]}, 1
    )
    if not roots or roots[0].kind != "AcceptanceCriterion":
        out.status = "partial"
        out.warnings.append("canonical hierarchy root is unavailable")
        return [], {}, len(roots)
    nodes, work, complete = await _children(backend, request, snapshot, roots, remaining)
    selected = _select(nodes, roots[0], scope)
    definition["complete"] = complete
    definition["depth"] = request.budget.max_hops
    if not complete:
        out.truncated = True
        out.status = "partial"
        out.warnings.append(
            "hierarchy depth, fanout, mapping or candidate budget leaves population incomplete"
        )
    return selected, {}, work


def _select(nodes: list[Entity], root: Entity, scope: AnswerScope) -> list[Entity]:
    """Apply explicit hierarchy inclusion independently from traversal.

    Args:
        nodes: Actual scoped descendants.
        root: Actual canonical root entity.
        scope: Explicit population inclusion and level selection.

    Returns:
        Only entities belonging to the requested population.
    """
    selected = [
        node for node in nodes if not scope.levels or node.properties.get("level") in scope.levels
    ]
    if scope.inclusion == "include_root" and (
        not scope.levels or root.properties.get("level") in scope.levels
    ):
        selected.insert(0, root)
    if scope.inclusion == "terminal_leaves":
        selected = [node for node in selected if node.properties.get("has_children") is False]
    return selected


async def _children(
    backend: KnowledgeBackend,
    request: KnowledgeRetrievalRequest,
    snapshot: ProjectionSnapshot,
    roots: list[Entity],
    remaining: int,
) -> tuple[list[Entity], int, bool]:
    """Walk canonical parent declarations with per-parent and cumulative lookahead.

    Args:
        backend: Configured scoped read adapter.
        request: Validated operation and work budgets.
        snapshot: Actual immutable generation.
        roots: Resolved canonical roots.
        remaining: Cumulative candidate work allowance.

    Returns:
        Actual descendants, consumed work and established completeness.
    """
    frontier, found, work, complete = roots, {}, len(roots), True
    seen = {node.canonical_id for node in roots}
    for _ in range(request.budget.max_hops):
        next_frontier = []
        for parent in frontier:
            if parent.properties.get("has_children") is False:
                continue
            available = remaining - work
            if available <= 0:
                complete = False
                break
            limit = min(available, request.budget.max_neighbors_per_seed + 1)
            children = await backend.query(
                request.repository_id,
                snapshot.generation_id,
                "_get_ac_children",
                {"entity_ids": [parent.canonical_id]},
                limit,
            )
            work += len(children)
            if (
                len(children) >= limit
                or not children
                or parent.properties.get("has_children") is None
            ):
                complete = False
            for child in children[: request.budget.max_neighbors_per_seed]:
                if child.canonical_id in seen:
                    complete = False
                    continue
                if child.properties.get("structural_parent") != parent.canonical_id:
                    raise ValueError("backend child crossed declared parent scope")
                seen.add(child.canonical_id)
                found[child.canonical_id] = child
                next_frontier.append(child)
        frontier = next_frontier
        if not frontier:
            break
    if any(node.properties.get("has_children") is not False for node in frontier):
        complete = False
    return list(found.values()), work, complete


async def _dependents(
    backend: KnowledgeBackend,
    request: KnowledgeRetrievalRequest,
    out: KnowledgeRetrievalResult,
    snapshot: ProjectionSnapshot,
    remaining: int,
) -> tuple[list[Entity], dict, int]:
    """Read direct declared incoming dependencies with bounded per-seed lookahead.

    Args:
        backend: Configured scoped read adapter.
        request: Validated operation and work budgets.
        out: Response receiving actual population identity.
        snapshot: Actual immutable generation.
        remaining: Cumulative candidate work allowance.

    Returns:
        Actual dependents, declared relationship provenance and work consumed.
    """
    scope = request.answer_requirements.scope if request.answer_requirements else None
    ids = request.arguments["entity_ids"]
    definition = {
        "population": "declared_dependents",
        "root_id": ids[0] if len(ids) == 1 else None,
        "levels": scope.levels if scope else None,
        "inclusion": scope.inclusion if scope else None,
        "relation": "depends_on",
        "direction": "incoming",
        "depth": 1,
        "complete": True,
        "limitations": [
            "direct declared dependencies only; transitive and code-consumer impact uninspected"
        ],
    }
    out.stats["population"] = definition
    seeds = await backend.query(
        request.repository_id,
        snapshot.generation_id,
        "get_entities",
        {"entity_ids": ids},
        min(remaining, len(ids)),
    )
    if set(ids) != {node.canonical_id for node in seeds}:
        definition["complete"] = False
    found: dict[str, Entity] = {}
    provenance: dict = {}
    work = len(seeds)
    for seed in seeds:
        limit = min(remaining - work, request.budget.max_neighbors_per_seed + 1)
        if limit <= 0:
            definition["complete"] = False
            break
        rows = await backend.query(
            request.repository_id,
            snapshot.generation_id,
            "get_declared_dependents",
            {"entity_ids": [seed.canonical_id]},
            limit,
        )
        work += len(rows)
        if len(rows) >= limit:
            definition["complete"] = False
        for row in rows[: request.budget.max_neighbors_per_seed]:
            if seed.canonical_id not in row.properties.get("depends_on", []):
                definition["complete"] = False
                continue
            if scope and scope.levels and row.properties.get("level") not in scope.levels:
                continue
            found[row.canonical_id] = row
            relation = Relation(
                source=row.source.model_copy(update={"locator": "/depends_on"}),
                source_id=row.canonical_id,
                target_id=seed.canonical_id,
                edge_type="depends_on",
                locator="/depends_on",
            )
            provenance.setdefault(row.canonical_id, {"path": []})["path"].append(relation)
    if not definition["complete"]:
        out.status, out.truncated = "partial", True
        out.warnings.append("declared dependency population is incomplete")
    return list(found.values()), provenance, work


# DECISION HISTORY
# - 2026-10-01 [python-coder]: Separate hierarchy inclusion from declared direct dependency scope. (#EPIC-RepositoryResearchAnswers/TICKET-20261001-KM-500e-4)
