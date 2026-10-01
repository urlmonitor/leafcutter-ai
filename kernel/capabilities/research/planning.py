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
from kernel.capabilities.call_costs import jev_available, judgement_calls, rerank_calls
from kernel.capabilities.decision.jev_support import ask_jev, make_batch, noul_question
from kernel.capabilities.research.state import Plan
from kernel.capabilities.research.targeting import (
    NeedQuery,
    default_query,
    existing_locators,
    locator_sources,
    targeted,
)
from kernel.capabilities.retrieval.access import ReadPolicy
from kernel.capabilities.retrieval.knowledge_map import PATHS_JSON, SCRIPT, trusted_root
from kernel.config import SourceConfig
from kernel.contracts import schema_ids
from kernel.contracts.capability import Usage
from kernel.contracts.enums import EvidenceCategory, NeedStatus, Priority, RequestKind
from kernel.contracts.evidence import EvidenceNeed, UnavailableSource
from kernel.contracts.payloads import RetrievalRequestPayload
from kernel.contracts.work import CapabilityInvocation, RequestProposal

PURPOSE = "research.plan_needs"
NATIVE_KINDS = ("repo_text", "knowledge_map")


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
    return targeted(plan, ctx.config.research.max_targeted_needs,
                    ctx.config.retrieval.max_explicit_locators)


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
    """Return the caller-mandated needs (kept required) plus the Jev-selected ones."""
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
    return needs, [result.usage]


def _native_available(ctx: ExecutionContext, source: SourceConfig) -> str | None:
    """Return None if the native source can be read, else the reason it cannot."""
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
           query: NeedQuery) -> RequestProposal:
    """Build the retrieval child request for one need, naming the operation it needs.

    Query hints go to every child; exact locators only to a native one (a host reads no files).
    """
    operation = retrieval_operation({"source_ids": source_ids}, sources)
    native = operation == "retrieve"
    holders = locator_sources(query.locators, sources) if native else []
    payload = RetrievalRequestPayload(
        need=need, source_ids=list(dict.fromkeys([*source_ids, *holders])),
        query_hints=query.hints, explicit_locators=query.locators if native else [])
    return RequestProposal(
        kind=RequestKind.EVIDENCE, question=need.question, evidence_needs=[need],
        operation=operation,
        payload_schema=schema_ids.RETRIEVAL_REQUEST, payload=payload.model_dump(mode="json"),
        requested_output_schema=schema_ids.EVIDENCE_BUNDLE, priority=need.priority)


def _candidates(ctx: ExecutionContext, need: EvidenceNeed, plan: Plan) -> list[SourceConfig]:
    """Catalog sources covering the need, narrowed by scope source ids and caller restrictions."""
    scope_ids, restricted = set(ctx.scope.source_ids), set(plan.source_restrictions)
    return [s for s in ctx.config.sources if need.category in s.categories
            and (not scope_ids or s.id in scope_ids) and (not restricted or s.id in restricted)]


def _checked(root: Path, query: NeedQuery) -> NeedQuery:
    """Return the query with only the explicit locators that name a file that exists."""
    kept = existing_locators(root, query.locators)
    return query if kept == query.locators else NeedQuery(query.hints, kept)


def _defer_host_only(out: Resolution) -> None:
    """Hold back supporting needs only a host can serve while native children can run.

    A host pause is the costliest step of a run: a supporting need that only a host can serve
    waits until the native evidence has been judged, and is dispatched only if it proves thin.
    Required needs are never deferred, and neither is a run whose only children are host ones.
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


def resolve_sources(ctx: ExecutionContext, needs: list[EvidenceNeed], plan: Plan) -> Resolution:
    """Map each need to a native retrieval child, a host.research child, or unavailable."""
    out = Resolution()
    root = Path(ctx.scope.repository_root)
    own = {i: _checked(root, q) for i, q in need_queries(ctx, plan).items()}
    shared = _checked(root, default_query(plan, ctx.config.retrieval.max_explicit_locators))
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
            out.requests.append(_child(need, ids, ctx.config.sources, own.get(need.id, shared)))
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
# ====================================================================
