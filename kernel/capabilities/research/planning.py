"""
MODULE: kernel.capabilities.research.planning
GOAL: The `plan_needs` and `resolve_sources` nodes: choose which of the six generic evidence
    categories are needed (Jev, preserving caller-mandated ones) and map each need to sources and
    child retrieval requests (deterministic).
BUSINESS CONTEXT: Research is domain-agnostic: generic categories carry no vendor names, and
    which source serves a category is configuration, not graph topology (Rev 3 section 10.2).
    Independent needs become independent children so they can run in parallel.
ARCHITECTURE: plan_needs makes at most one Jev batch (need.<category> nouls). resolve_sources is
    pure apart from path-existence checks: it filters config.sources by category, scope source
    ids, caller restrictions and availability, then emits retrieval_request.v1 children; a need
    with no native source becomes a host.research child only if config.host.enabled.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pydantic import JsonValue

from kernel.capabilities.base import ExecutionContext
from kernel.capabilities.call_costs import (
    batch_allowance,
    jev_available,
    judgement_calls,
    rerank_calls,
)
from kernel.capabilities.decision.jev_support import ask_jev, make_batch, noul_question
from kernel.capabilities.research.baseline import baseline_needs
from kernel.capabilities.research.state import Plan
from kernel.capabilities.research.targeting import (
    NeedQuery,
    claims_left_out,
    default_query,
    existing_locators,
    locator_sources,
    targeted,
    with_symbol_locators,
)
from kernel.capabilities.retrieval.access import ReadPolicy
from kernel.capabilities.retrieval.knowledge_map import PATHS_JSON, SCRIPT, trusted_root
from kernel.capabilities.retrieval.locators import parse_locator
from kernel.config import SourceConfig
from kernel.contracts import schema_ids
from kernel.contracts.capability import Usage
from kernel.contracts.enums import EvidenceCategory, NeedStatus, Priority, RequestKind
from kernel.contracts.evidence import EvidenceNeed, UnavailableSource
from kernel.contracts.payloads import RetrievalRequestPayload
from kernel.contracts.work import CapabilityInvocation, RequestProposal

PURPOSE = "research.plan_needs"
NATIVE_KINDS = ("repo_text", "knowledge_map", "graph_query")


@dataclass
class Resolution:
    """Outcome of resolve_sources: children to run, per-need source ids and unavailability."""

    requests: list[RequestProposal] = field(default_factory=list)
    child_map: dict[str, list[str]] = field(default_factory=dict)
    unavailable: list[UnavailableSource] = field(default_factory=list)
    needs: list[EvidenceNeed] = field(default_factory=list)
    attempted: list[str] = field(default_factory=list)
    deferred: list[RequestProposal] = field(default_factory=list)


def _targeted(ctx: ExecutionContext, plan: Plan) -> list[tuple[EvidenceNeed, NeedQuery]]:
    """Return the gap and claim needs of the plan with their queries (bounded by config)."""
    cfg = ctx.config.research
    return targeted(plan, cfg.max_claim_needs, cfg.max_targeted_needs,
                    ctx.config.retrieval.max_explicit_locators)


def claim_limitations(ctx: ExecutionContext, plan: Plan) -> list[str]:
    """Return one limitation per human-added option the claim cap leaves unresearched."""
    return claims_left_out(plan, ctx.config.research.max_claim_needs)


def need_queries(ctx: ExecutionContext, plan: Plan) -> dict[str, NeedQuery]:
    """Return the query of every targeted need, keyed by need id."""
    return {need.id: query for need, query in _targeted(ctx, plan)}


async def plan_needs(ctx: ExecutionContext, invocation: CapabilityInvocation, plan: Plan
                     ) -> tuple[list[EvidenceNeed], list[Usage]]:
    """Return the needs: mandated ones, Jev-selected ones, then gap and claim needs.

    Raises:
        StopCapability: Jev was unavailable or over budget.
    """
    needs, usage = await _select_needs(ctx, invocation, plan)
    return [*needs, *(need for need, _ in _targeted(ctx, plan))], usage


def afford_needs(ctx: ExecutionContext, plan: Plan, needs: list[EvidenceNeed]
                 ) -> tuple[list[EvidenceNeed], list[str]]:
    """Trim the planned needs to the number the budget affords beside the requester's reserve.

    Each need is one retrieval child (one rerank batch) and the round ends with one judgement.
    Needs are kept in planning order (mandated, then Jev-selected, then claim and gap needs), so
    the targeted extras are the first to go; each dropped need is named in a limitation.

    Args:
        ctx: Existing execution context and available budget.
        plan: Research plan carrying the requester's reserve.
        needs: Ordered evidence needs considered for retrieval.

    Returns:
        tuple: (the needs to run, one limitation per dropped need).
    """
    left = jev_available(ctx.budget)
    if left is None:
        return needs, []
    spare, per_need = left - plan.jev_reserve, rerank_calls(ctx.config)
    keep = len(needs)
    while keep > 0 and keep * per_need + judgement_calls(keep, ctx.config) > spare:
        keep -= 1
    return needs[:keep], [
        f"need {n.id} not researched: {spare} Jev call(s) are left for research after the "
        f"{plan.jev_reserve} kept in reserve for the requester's final assessment"
        for n in needs[keep:]]


def affordable_judgement(ctx: ExecutionContext, plan: Plan, needs: list[EvidenceNeed]) -> bool:
    """True if the round's judgement fits in the budget without touching the requester's reserve."""
    left = jev_available(ctx.budget)
    return left is None or left - plan.jev_reserve >= judgement_calls(len(needs), ctx.config)


async def _select_needs(ctx: ExecutionContext, invocation: CapabilityInvocation, plan: Plan
                        ) -> tuple[list[EvidenceNeed], list[Usage]]:
    """Return the caller-mandated needs (kept required) plus the Jev-selected ones.

    Args:
        ctx: Trusted execution context.
        invocation: Current registered capability invocation.
        plan: Existing research plan.

    Returns:
        tuple[list[EvidenceNeed], list[Usage]]: Result of the documented operation.
    """
    needs = list(plan.mandated)
    if plan.needs_only:
        return needs, []
    covered = {n.category for n in needs}
    remaining = [c for c in EvidenceCategory if c not in covered]
    if not remaining:
        return needs, []
    described = ctx.config.research.category_descriptions
    state: dict[str, JsonValue] = {"question": plan.question,
             "categories": {c.value: described[c] for c in remaining}}
    questions = [noul_question(
        f"need.{c.value}", "research.need",
        f"Is `categories.{c.value}` evidence needed to answer `question`?") for c in remaining]
    result = await ask_jev(ctx, invocation, make_batch(ctx, PURPOSE, state, questions))
    cfg = ctx.config.research
    for category in remaining:
        p = result.noul(f"need.{category.value}").probability
        if p >= cfg.need_required_threshold:
            priority = Priority.REQUIRED
        elif p >= cfg.need_supporting_threshold:
            priority = Priority.SUPPORTING
        else:
            continue
        needs.append(EvidenceNeed(
            id=f"need.{category.value}", category=category, priority=priority,
            question=f"{described[category]} Question: {plan.question}"))
    return needs or baseline_needs(plan.question, described), [result.usage]


def _native_available(ctx: ExecutionContext, source: SourceConfig) -> str | None:
    """Return None if the native source can be read, else the reason it cannot.

    Args:
        ctx: Trusted execution context.
        source: Configured evidence source or failing configuration path.

    Returns:
        str | None: Result of the documented operation.
    """
    if source.kind == "graph_query":
        if ctx.config.knowledge.backend == "none":
            return "knowledge backend is disabled"
        configured = ctx.config.knowledge.repository_root
        if not configured or Path(configured).resolve() != Path(ctx.scope.repository_root).resolve():
            return "knowledge repository binding does not match task scope"
        return None
    if source.kind == "knowledge_map":
        script = trusted_root() / SCRIPT  # the bridge never comes from the scope
        if not script.is_file():
            return "knowledge map script not found"
        data = Path(ctx.scope.repository_root) / PATHS_JSON  # the scope is data the script reads
        return None if data.is_file() else f"knowledge map needs {PATHS_JSON.as_posix()} in scope"
    policy = ReadPolicy(root=Path(ctx.scope.repository_root),
                        read_roots=tuple(ctx.scope.read_roots),
                        deny_globs=tuple(ctx.config.retrieval.deny_globs),
                        max_file_bytes=ctx.config.retrieval.max_file_bytes)
    resolved = policy.resolve_roots(source.roots)
    return None if resolved.roots else "; ".join(resolved.rejected) or "no readable roots"


def retrieval_operation(payload: dict, sources: list[SourceConfig]) -> str:
    """Return the registry operation a retrieval_request.v1 child needs.

    `bounded_research` when the request names a host_research source, else `retrieve`. Both
    `retrieve.repository` and `host.research` accept retrieval requests, so `_child` stores it in
    `RequestProposal.operation` and the scheduler passes it to filter_candidates.
    """
    host_ids = {s.id for s in sources if s.kind == "host_research"}
    asked = set(payload.get("source_ids") or [])
    return "bounded_research" if asked and asked <= host_ids else "retrieve"


def _child(need: EvidenceNeed, source_ids: list[str], sources: list[SourceConfig],
           query: NeedQuery, answer_requirements: dict[str, JsonValue] | None = None,
           assessment: dict[str, JsonValue] | None = None, *,
           batches: int | None = None, jev_reserve: int = 0) -> RequestProposal:
    """Build one retrieval child with original answer obligations and its rerank allowance.

    Query hints go to every child; exact locators and their owners stay on file-search
    children so they cannot widen a graph-only source selection.

    Args:
        need: Evidence need to address.
        source_ids: Authorized source identifiers.
        sources: Configured available evidence sources.
        query: Focused source query.
        answer_requirements: Original caller facts and population obligations.
        assessment: Unmodified scoped supplied evidence packet.

    Returns:
        RequestProposal: Scoped retrieval child preserving both branches' contracts.

    Keyword-only batches: Maximum rerank batches the requester's budget affords.
    Keyword-only jev_reserve: Calls retained for the requester after child retrieval.
    """
    operation = retrieval_operation({"source_ids": source_ids}, sources)
    native = operation == "retrieve"
    graph_ids = {source.id for source in sources if source.kind == "graph_query"}
    graph_only = bool(source_ids) and set(source_ids) <= graph_ids
    file_search = native and not graph_only
    holders = locator_sources(query.locators, sources) if file_search else []
    payload = RetrievalRequestPayload(
        need=need, answer_requirements=answer_requirements, assessment=assessment,
        source_ids=list(dict.fromkeys([*source_ids, *holders])),
        query_hints=query.hints, explicit_locators=query.locators if file_search else [],
        max_rerank_batches=batches, jev_reserve=jev_reserve)
    return RequestProposal(
        kind=RequestKind.EVIDENCE, question=need.question, evidence_needs=[need],
        operation=operation,
        payload_schema=schema_ids.RETRIEVAL_REQUEST, payload=payload.model_dump(mode="json"),
        requested_output_schema=schema_ids.EVIDENCE_BUNDLE, priority=need.priority)


def _children(need: EvidenceNeed, chosen: list[SourceConfig], sources: list[SourceConfig],
              query: NeedQuery, plan: Plan, batches: int | None) -> list[RequestProposal]:
    """Keep graph and native children distinct while carrying the same caller obligations.

    Args:
        need: Original evidence need served by both source groups.
        chosen: Sources selected for this need.
        sources: Complete configured source catalog for locator ownership.
        query: Checked hints and locators for this need.
        plan: Original answer, assessment and reserve obligations.
        batches: Native rerank allowance computed by research planning.

    Returns:
        One scoped request per nonempty graph or native source group.
    """
    groups = [[s.id for s in chosen if s.kind == "graph_query"],
              [s.id for s in chosen if s.kind != "graph_query"]]
    return [_child(need, group, sources, query,
                   answer_requirements=plan.answer_requirements, assessment=plan.assessment,
                   batches=batches, jev_reserve=plan.jev_reserve)
            for group in groups if group]


def _candidates(ctx: ExecutionContext, need: EvidenceNeed, plan: Plan) -> list[SourceConfig]:
    """Catalog sources covering the need, narrowed by scope source ids and caller restrictions."""
    scope_ids, restricted = set(ctx.scope.source_ids), set(plan.source_restrictions)
    return [s for s in ctx.config.sources if need.category in s.categories
            and (s.automatic_research or s.id in restricted)
            and (not scope_ids or s.id in scope_ids) and (not restricted or s.id in restricted)]


def _checked(root: Path, query: NeedQuery) -> NeedQuery:
    """Return the query with only the explicit locators that name a file that exists."""
    kept = with_symbol_locators(root, existing_locators(root, query.locators), query.hints)
    return query if kept == query.locators else NeedQuery(query.hints, kept)


def _defer_host_only(out: Resolution) -> None:
    """Hold back supporting needs only a host can serve while native children can run.

    A host pause is the costliest step of a run: a supporting need that only a host can serve
    waits until the native evidence has been judged, and is dispatched only if it proves thin.
    Required needs are never deferred, and neither is a run whose only children are host ones.

    Args:
        out: Mutable source resolution accumulator.
    """
    held = [r for r in out.requests if r.operation == "bounded_research"
            and r.evidence_needs[0].priority is Priority.SUPPORTING]
    if not held or len(held) == len(out.requests):
        return
    out.requests = [r for r in out.requests if r not in held]
    out.deferred = held
    for request in held:
        for source_id in out.child_map.pop(request.evidence_needs[0].id, []):
            if source_id in out.attempted:
                out.attempted.remove(source_id)


def _permitted_entity_locator(ctx: ExecutionContext, source: SourceConfig, locator: str) -> bool:
    """Check a cached locator against the current resolved-path and source restrictions."""
    policy = ReadPolicy(Path(ctx.scope.repository_root), tuple(ctx.scope.read_roots),
                        (*ctx.config.retrieval.deny_globs, *source.deny_globs),
                        source.max_file_bytes or ctx.config.retrieval.max_file_bytes)
    path, _, _ = parse_locator(locator)
    target = policy.root / path
    relative = policy.relative(target)
    if relative is None or policy.is_denied(path) or policy.is_denied(relative):
        return False
    resolved = target.resolve()
    return any(resolved == root or root in resolved.parents
               for root in policy.resolve_roots(source.roots).roots)


def _entity_locators(ctx: ExecutionContext, plan: Plan) -> list[str]:
    """Recheck resolved meaning locators against current scope and source policy before hints."""
    if ctx.entity_context is None:
        return []
    sources = {source.id: source for source in ctx.config.sources
               if source.kind == "repo_text"
               and (not ctx.scope.source_ids or source.id in ctx.scope.source_ids)
               and (not plan.source_restrictions or source.id in plan.source_restrictions)}
    result = []
    for card in ctx.entity_context.entities:
        source = sources.get(card.provenance.source_id)
        if card.resolution != "resolved" or source is None:
            continue
        if _permitted_entity_locator(ctx, source, card.provenance.locator):
            result.append(card.provenance.locator)
    return list(dict.fromkeys(result))[:ctx.config.retrieval.max_explicit_locators]


def _context_query(ctx: ExecutionContext, query: NeedQuery, locators: list[str]) -> NeedQuery:
    """Carry bounded caller claims and later clarifications as search hints, never evidence."""
    context = ctx.entity_context or ctx.context_enrichment
    caller = ([*reversed(context.caller_context.conversation), *context.caller_context.observations]
              if context is not None else [])
    return NeedQuery([*query.hints, *ctx.clarifications, *caller],
                     list(dict.fromkeys([*locators, *query.locators]))[
                         :ctx.config.retrieval.max_explicit_locators])


def resolve_sources(ctx: ExecutionContext, needs: list[EvidenceNeed], plan: Plan) -> Resolution:
    """Map each need to a native retrieval child, a host.research child, or unavailable.

    Args:
        ctx: Trusted execution context.
        needs: Selected evidence needs.
        plan: Existing research plan.

    Returns:
        Resolution: Result of the documented operation.
    """
    out = Resolution()
    root = Path(ctx.scope.repository_root)
    own = {i: _checked(root, q) for i, q in need_queries(ctx, plan).items()}
    shared = _checked(root, default_query(plan, ctx.config.retrieval.max_explicit_locators))
    locators = _entity_locators(ctx, plan)
    shared = _context_query(ctx, shared, locators)
    own = {key: _context_query(ctx, query, locators) for key, query in own.items()}
    batches = batch_allowance(jev_available(ctx.budget), plan.jev_reserve, len(needs), ctx.config)
    for need in needs:
        candidates = _candidates(ctx, need, plan)
        native, unavailable_reasons = [], []
        for source in (s for s in candidates if s.kind in NATIVE_KINDS):
            reason = _native_available(ctx, source)
            if reason is None:
                native.append(source)
            else:
                unavailable_reasons.append(UnavailableSource(source_id=source.id, reason=reason))
        hosts = [s for s in candidates if s.kind == "host_research"]
        chosen = native or (hosts if ctx.config.host.enabled else [])
        out.unavailable += unavailable_reasons
        if chosen:
            ids = [s.id for s in chosen]
            out.needs.append(need)
            out.requests.extend(_children(need, chosen, ctx.config.sources,
                                           own.get(need.id, shared), plan, batches))
            out.child_map[need.id] = ids
            out.attempted += ids
            continue
        why = "no source serves this category"
        if hosts:
            why = "host research is disabled"
        elif unavailable_reasons:
            why = "all native sources are unavailable"
        out.needs.append(need.model_copy(update={"status": NeedStatus.UNAVAILABLE,
                                                 "resolution": [why]}))
        out.unavailable.append(UnavailableSource(source_id=f"need:{need.id}", reason=why))
    _defer_host_only(out)
    return out


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-02 [python-coder]: Claim needs and gap needs are capped separately; claim_limitations
#   names the added options the claim cap leaves out. (#KernelResearchEveryAddedOption)
# - 2026-10-01 [python-coder]: Checked locators also gain `path::Symbol` for a contract or class
#   the need's text names (round 8 defect f). (#KernelDecisionStore)
# - 2026-10-01 [python-coder]: Every retrieval child carries `max_rerank_batches` (what the Jev
#   calls beyond the plan and the requester's reserve afford per need), so deeper reranking stays
#   within the decision's reserve. (#KernelV01/F)
# - 2026-10-01 [python-coder]: afford_needs trims the plan to what the budget affords beside the
#   requester's reserve; explicit locators are checked against the repository before a child
#   asks for them (a placeholder such as `-NNN.yaml` was requested live). (#KernelV01/E)
# - 2026-10-01 [python-coder]: Needs from named gaps and human-added option claims are appended
#   after the planned ones, and every child carries query hints (goal first) and, when native, the
#   paths the options cite as explicit locators. (#KernelV01/D)
# - 2026-10-02 [python-coder]: Supporting needs only a host can serve are deferred behind the
#   native children (a live run paused for host work with its answer already found).
#   (#KernelBootstrapV0/GROUND)
# - 2026-10-01 23:00 [python-coder]: A request that says `evidence_needs_only` plans exactly its
#   mandated needs with no Jev call: grounding research for a decision is bounded to the three
#   categories about the option space. (#KernelBootstrapV0/GROUND)
# - 2026-09-30 23:59 [python-coder]: Retrieval children carry `operation` (set here from
#   retrieval_operation) instead of the scheduler deriving it. (#KernelBootstrapV0/INT)
# - 2026-09-30 23:00 [python-coder]: Source filtering by `technologies` is not applied because a
#   SourceConfig carries no technology field; technologies only feed retrieval query terms.
#   (#KernelBootstrapV0/P5)
# - 2026-10-03 15:10 [python-coder]: Preserve verbatim goals and separate meaning, caller and clarification channels. (#DK-300/entity-context)
# ====================================================================

# - 2026-10-09 [python-coder]: A goal for which Jev selects no category plans the baseline needs
#   (task context, existing patterns) instead of none. (#TICKET-20261009-KernelEvidenceLookupNoNeeds)
# - 2026-10-01 20:00 [python-coder]: Bind optional knowledge through existing scoped retrieval contracts. (#TICKET-20261001-KM-400e-3)

# - 2026-10-02 04:36 [conflict-resolver]: Preserve split graph sources and evidence packets alongside rerank limits. (#TICKETLESS reason=kernel-v01-integration)
# - 2026-10-03 17:00 [python-coder]: Select context-only owner stores through explicit sources or resolved locators, preserving ordinary research behavior. (#DK-300/entity-context)
# - 2026-10-03 22:24 [Codex]: Keep graph-only retrieval children scoped to their graph sources while retaining explicit locator ownership on file-search siblings. (#TICKETLESS reason=user-approved-DK-300d-5)
