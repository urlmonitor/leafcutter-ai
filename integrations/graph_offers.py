"""MODULE: graph_offers
GOAL: Bind finite graph choices to currently permitted native identities.
BUSINESS CONTEXT: Recognized meanings are hints, never authorization or query programs.
ARCHITECTURE: Pure offer construction over trusted scope and the registered read catalog.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from collections.abc import Callable
from pathlib import Path

from kernel.capabilities.base import ExecutionContext
from kernel.capabilities.retrieval.access import ReadPolicy
from kernel.capabilities.retrieval.executor import select_sources
from kernel.capabilities.retrieval.locators import parse_locator
from kernel.contracts.entity_context import EntityBudgets, EntityCard, EntityCoverage
from kernel.contracts.payloads import RetrievalRequestPayload
from kernel.contracts.retrieval_needs import RetrievalNeedsOutput
from knowledge.contracts import OPERATIONS


@dataclass(frozen=True)
class GraphOffer:
    """A registered operation with Python-bound argument name and finite targets."""

    description: str
    targets: tuple[str, ...]
    argument: str
    mode: str
    many: bool = False
    version: str | None = None
    digest: str | None = None


def _permitted(ctx: ExecutionContext, card: EntityCard) -> bool:
    """Recheck the card owner independently of a graph-only transport child.

    Args:
        ctx: Trusted execution scope, configuration and services.
        card: Recognized native identity with source provenance.

    Returns:
        Whether the native owner is readable in the current scope.
    """
    source = next((s for s in ctx.config.sources if s.id == card.provenance.source_id), None)
    if source is None or source.kind != "repo_text":
        return False
    if ctx.scope.source_ids and source.id not in ctx.scope.source_ids:
        return False
    policy = ReadPolicy(Path(ctx.scope.repository_root).resolve(), tuple(ctx.scope.read_roots),
                        (*ctx.config.retrieval.deny_globs, *source.deny_globs),
                        source.max_file_bytes or ctx.config.retrieval.max_file_bytes)
    path, _, _ = parse_locator(card.provenance.locator)
    target = policy.root / path
    relative = policy.relative(target)
    if relative is None or policy.is_denied(path) or policy.is_denied(relative):
        return False
    resolved = target.resolve()
    return any(resolved == root or root in resolved.parents
               for root in policy.resolve_roots(source.roots).roots)


def selection_context(ctx: ExecutionContext) -> ExecutionContext:
    """Project permitted cards without changing the original checkpoint or leaking counts.

    Args:
        ctx: Trusted current task scope and the original interpretation snapshot.

    Returns:
        A copy whose optional meaning channel contains only currently readable owners.
    """
    context = ctx.entity_context
    if context is None:
        return replace(ctx, context_enrichment=None)
    same_root = Path(context.repository_root).resolve() == Path(ctx.scope.repository_root).resolve()
    cards = [c for c in context.entities if same_root and _permitted(ctx, c)]
    scoped = context.model_copy(update={"entities": cards, "unresolved": [],
        "coverage": EntityCoverage(), "budgets": EntityBudgets(), "limitations": [],
        "status": "recognized" if cards else "no_matches"})
    return replace(ctx, entity_context=scoped, context_enrichment=None)


def _identity(card: EntityCard) -> str | None:
    """Translate native owner identity exactly as the graph canonical mapper does.

    Args:
        card: Recognized native identity with source provenance.

    Returns:
        Canonical graph identity, or None for unresolved or non-native cards.
    """
    if card.family != "artifact_id" or card.resolution != "resolved":
        return None
    if card.native_kind in {"AcceptanceCriterion", "ADR", "Component"}:
        return card.identity
    if card.native_kind in {"Ticket", "Flow", "Decision"}:
        return f"{card.native_kind}:{card.identity}"
    return None


def interpreted_targets(payload: RetrievalRequestPayload, native_kind: str | None = None) -> tuple[str, ...]:
    """Bind accepted literal candidates as lookup seeds, not proof of existence or permission.

    Returned evidence still passes repository, revision and read-root authorization.
    Native cards are optional enrichment; the host cannot introduce an unoffered target.

    Args:
        payload: Typed retrieval request and preserved question obligations.
        native_kind: Optional canonical kind restricting eligible query seeds.

    Returns:
        Deduplicated lookup seeds without claiming their existence.
    """
    needs = payload.retrieval_needs
    return canonical_target_ids(needs, native_kind) if needs is not None else ()


def canonical_target_ids(needs: RetrievalNeedsOutput, native_kind: str | None = None) -> tuple[str, ...]:
    """Use the same canonical IDs for query seeds and immutable answer obligations.

    Args:
        needs: Accepted host interpretation retaining the original selected identities.
        native_kind: Optional canonical kind restricting eligible query seeds.

    Returns:
        Deduplicated canonical identities, without asserting source existence or permission.
    """
    kinds = {"ac": "AcceptanceCriterion", "adr": "ADR", "ticket": "Ticket",
             "component": "Component", "flow": "Flow", "decision": "Decision"}
    selected = {kinds[label] for label in needs.selections["entity_types"] if label in kinds}
    if native_kind is not None and selected != {native_kind}:
        return ()
    prefix = next(iter(selected)) if len(selected) == 1 else None
    return tuple(dict.fromkeys(
        f"{prefix}:{identifier}" if prefix in {"Ticket", "Flow", "Decision"}
        and not identifier.startswith(prefix + ":") else identifier
        for identifier in needs.selections["target_ids"]))


def _targets(ctx: ExecutionContext, payload: RetrievalRequestPayload) -> tuple:
    """Combine optional verified native cards with accepted unverified lookup candidates.

    Args:
        ctx: Trusted execution scope, configuration and services.
        payload: Typed retrieval request and preserved question obligations.

    Returns:
        Eligible target groups bound to the requested seed kind.
    """
    cards = ctx.entity_context.entities if ctx.entity_context is not None else []
    if payload.retrieval_needs is not None:
        wanted = set(payload.retrieval_needs.selections["target_ids"])
        cards = [card for card in cards if _identity(card) in wanted or card.identity in wanted]
    all_ids = tuple(dict.fromkeys([*(i for c in cards if (i := _identity(c))),
                                  *interpreted_targets(payload)]))
    ac_ids = tuple(dict.fromkeys([*(c.identity for c in cards
        if _identity(c) and c.native_kind == "AcceptanceCriterion"),
        *interpreted_targets(payload, "AcceptanceCriterion")]))
    decisions = tuple(dict.fromkeys([*(i for c in cards
        if c.native_kind == "Decision" and (i := _identity(c))), *interpreted_targets(payload, "Decision")]))
    components = (_components(ctx, cards) if payload.retrieval_needs is None else
                  interpreted_targets(payload, "Component"))
    return all_ids, ac_ids, decisions, components


def graph_offers(ctx: ExecutionContext, payload: RetrievalRequestPayload,
                 capabilities: dict) -> dict[str, GraphOffer]:
    """Offer only registered operations whose required inputs are already authorized.

    Args:
        ctx: Copy with current-policy-filtered entity cards.
        payload: Current need and any explicit population obligation.
        capabilities: Mechanism readiness reported by the injected knowledge port.

    Returns:
        Finite operation names and deterministic argument bindings.
    """
    if not capabilities.get("graph") or capabilities.get("status") not in {None, "ready", "ok"}:
        return {}
    all_ids, ac_ids, decisions, components = _targets(ctx, payload)
    offers: dict[str, GraphOffer] = {}

    def add(operation: str, targets: tuple[str, ...], description: str) -> None:
        """Bind a registered argument without accepting provider-generated arguments."""
        if targets:
            mode, argument = OPERATIONS[operation]
            offers[operation] = GraphOffer(description, targets, argument, mode, argument == "entity_ids")

    add("get_entities", all_ids,
        "Look up or explain the specifically named record itself: an acceptance criterion, ADR, ticket, "
        "component, flow or decision. Choose this for 'What is ID about?' or 'Explain this acceptance "
        "criterion/ADR' so its authored content can be read. It does not retrieve related records or "
        "enumerate a filtered population.")
    add("get_related_tests", ac_ids,
        "Find automated tests or executable checks that demonstrate the named acceptance criterion "
        "is met. Choose this when the requested answer is its verification evidence, rather than an "
        "explanation of the acceptance criterion itself.")
    for operation, description in (
        ("get_component_context", "Read context for a trusted component."),
        ("get_acceptance_criteria", "Read acceptance criteria linked to a trusted component."),
        ("get_relevant_adrs", "Read architecture decisions governing a trusted component."),
        ("get_previous_decisions", "Read previous decisions linked to a trusted component."),
    ):
        add(operation, components, description)
    for operation in ("get_corrected_decisions", "get_related_lessons", "get_decision_evidence"):
        add(operation, decisions, "Read the registered relationship of the named historical decisions.")
    _population_offers(payload, ac_ids, all_ids, add)
    if ctx.config.knowledge.embeddings_enabled and capabilities.get("semantic_ready") and capabilities.get("semantic"):
        for operation in ("find_similar_decisions", "find_similar_lessons"):
            add(operation, (payload.need.question,), "Find similar historical material; similarity is not proof.")
    return offers


def _components(ctx: ExecutionContext, cards: list[EntityCard]) -> tuple[str, ...]:
    """Respect explicit component scope; otherwise use only readable recognized components."""
    if ctx.scope.component_ids:
        return tuple(dict.fromkeys(ctx.scope.component_ids))
    return tuple(dict.fromkeys(c.identity for c in cards
                              if _identity(c) and c.native_kind == "Component"))


def _population_offers(payload: RetrievalRequestPayload, ac_ids: tuple[str, ...],
                       all_ids: tuple[str, ...],
                       add: Callable[[str, tuple[str, ...], str], None]) -> None:
    """Offer bounded discovery, or bind an explicitly scoped population to its real root.

    Args:
        payload: Typed retrieval request and preserved question obligations.
        ac_ids: Eligible acceptance-criterion identity candidates.
        all_ids: Eligible canonical identity candidates.
        add: Callback adding one bound registered operation.
    """
    requirements = payload.answer_requirements or {}
    scope = requirements.get("scope", {})
    root = scope.get("root_id")
    descendant_ids = (root,) if root in ac_ids else ac_ids if not root else ()
    dependent_ids = (root,) if root in all_ids else all_ids if not root else ()
    if payload.answer_requirements is None and len(payload.need.question) <= 4000:
        add("get_ac_descendants", descendant_ids,
            "Find child or descendant acceptance criteria beneath a named criterion, rather than "
            "explain that criterion itself. Read all L0-L3 descendants, excluding the root. "
            "Enumeration is bounded and truncation leaves completeness unresolved.")
    elif (scope.get("population") == "ac_descendants" and root in ac_ids
          and scope.get("levels") is not None and scope.get("inclusion") is not None):
        add("get_ac_descendants", descendant_ids, "Read the explicitly supplied hierarchy population and inclusion.")
    add("get_declared_dependents", dependent_ids,
        "Find other records that explicitly declare a dependency on the named entity, rather than "
        "explain the entity itself. Results are bounded; truncation does not establish completeness.")


def repository_sources(ctx: ExecutionContext, payload: RetrievalRequestPayload) -> list[str]:
    """Return native fallback IDs within both the request and trusted source scope."""
    return [source.id for source in select_sources(ctx, payload)[0]]


# DECISION HISTORY
# ================================================================================
# - 2026-10-03 20:00 [python-coder]: Bind graph offers to permitted native identities and trusted components. (#TICKETLESS reason=user-approved-DK300-graph-routing)
# - 2026-10-03 22:56 [python-coder]: Distinguish explaining a named record from retrieving its related records. (#TICKETLESS reason=user-approved-DK300-live-routing-correction)

# - 2026-10-09 15:40 [python-coder]: Preserve typed question obligations through public research and scoped query selection. (#KM-500/KM-500e-1-i)

# - 2026-10-09 18:49 [python-coder]: Share canonical target normalization between query offers and answer scope. (#KM-500/KM-500e-1-i)
