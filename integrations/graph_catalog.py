"""MODULE: integrations.graph_catalog
GOAL: Offer admitted single-seed queries beside the existing registered graph operations.
BUSINESS CONTEXT: Installing a query catalog must not change the meaning of an exact lookup.
ARCHITECTURE: Deterministic binding over permitted entity cards and digest-pinned catalog data.
"""
from __future__ import annotations

from integrations.graph_offers import GraphOffer, _identity, interpreted_targets
from kernel.capabilities.base import ExecutionContext
from kernel.contracts.payloads import RetrievalRequestPayload
from knowledge.contracts import OPERATIONS
from knowledge.query_catalog import QueryCatalog
from knowledge.query_models import QueryDescriptor
from kernel.contracts.entity_context import EntityCard


def _targets(ctx: ExecutionContext, payload: RetrievalRequestPayload, descriptor: QueryDescriptor,
             cards: list[EntityCard], wanted: set[str] | None) -> list[str]:
    """Keep descriptor seed-kind and explicit target-role constraints on every saved query.

    Args:
        ctx: Trusted execution scope, configuration and services.
        payload: Typed retrieval request and preserved question obligations.
        descriptor: Verified saved query contract and seed recipe.
        cards: Currently permitted recognized native identities.
        wanted: Accepted target identities, or None for the compatibility path.

    Returns:
        Eligible target groups bound to the requested seed kind.
    """
    targets = [identity for card in cards if (identity := _identity(card))
        and (descriptor.recipe.seed_kind is None or card.native_kind == descriptor.recipe.seed_kind)
        and (wanted is None or identity in wanted or card.identity in wanted)]
    if descriptor.recipe.seed_kind == "Component":
        targets += [identity for identity in ctx.scope.component_ids if wanted is None or identity in wanted]
    targets += list(interpreted_targets(payload, descriptor.recipe.seed_kind))
    targets = list(dict.fromkeys(targets))
    return targets


def catalog_offers(ctx: ExecutionContext, payload: RetrievalRequestPayload, catalog: QueryCatalog,
                   capabilities: dict) -> dict[str, GraphOffer]:
    """Offer only saved queries whose required inputs can be bound without generation.

    Args:
        ctx: Current-policy-filtered entity context and trusted component scope.
        payload: Original interpreted need and answer requirements.
        catalog: Verified immutable query descriptors.
        capabilities: Actual backend readiness.

    Returns:
        Existing selector offers, each retaining the exact reviewed query version and digest.
    """
    if not capabilities.get("graph") or capabilities.get("status") not in {None, "ready", "ok"}:
        return {}
    cards = ctx.entity_context.entities if ctx.entity_context is not None else []
    wanted = set(payload.retrieval_needs.selections["target_ids"]) if payload.retrieval_needs else None
    offers = {}
    for row in catalog.descriptors()[:50]:
        if row["operation"] in OPERATIONS:
            continue
        descriptor = catalog.get(row["operation"], row["version"], row["digest"])
        seed = descriptor.recipe.seed_parameter
        if any(name != seed and parameter.required for name, parameter in descriptor.parameters.items()):
            continue
        targets = _targets(ctx, payload, descriptor, cards, wanted)
        if 1 <= len(targets) <= 20:
            offers[descriptor.operation] = GraphOffer(descriptor.description, tuple(targets), seed,
                "graph", True, descriptor.version, row["digest"])
    return offers


# DECISION HISTORY
# ================================================================================
# - 2026-10-09 15:40 [python-coder]: Share the entity selector across builtin and admitted query offers. (#KM-500/KM-500e-1-i)
