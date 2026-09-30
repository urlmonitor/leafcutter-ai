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

from kernel.capabilities.base import ExecutionContext
from kernel.capabilities.decision.jev_support import ask_jev, make_batch, noul_question
from kernel.capabilities.research.state import Plan
from kernel.capabilities.retrieval.access import ReadPolicy
from kernel.capabilities.retrieval.knowledge_map import SCRIPT
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


async def plan_needs(ctx: ExecutionContext, invocation: CapabilityInvocation, plan: Plan
                     ) -> tuple[list[EvidenceNeed], list[Usage]]:
    """Return the evidence needs: caller-mandated ones kept required plus Jev-selected ones.

    Raises:
        StopCapability: Jev was unavailable or over budget.
    """
    needs = list(plan.mandated)
    covered = {n.category for n in needs}
    remaining = [c for c in EvidenceCategory if c not in covered]
    if not remaining:
        return needs, []
    described = ctx.config.research.category_descriptions
    state = {"question": plan.question,
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
        script = Path(ctx.scope.repository_root) / SCRIPT
        return None if script.is_file() else "knowledge map script not found"
    policy = ReadPolicy(root=Path(ctx.scope.repository_root),
                        read_roots=tuple(ctx.scope.read_roots),
                        deny_globs=tuple(ctx.config.retrieval.deny_globs),
                        max_file_bytes=ctx.config.retrieval.max_file_bytes)
    resolved = policy.resolve_roots(source.roots)
    return None if resolved.roots else "; ".join(resolved.rejected) or "no readable roots"


def retrieval_operation(payload: dict, sources: list[SourceConfig]) -> str:
    """Return the registry operation a retrieval_request.v1 child needs.

    `bounded_research` when the request names a host_research source, else `retrieve`. Both
    `retrieve.repository` and `host.research` accept retrieval requests, so the scheduler passes
    this as the `operation` argument of filter_candidates to bind the child deterministically.
    """
    host_ids = {s.id for s in sources if s.kind == "host_research"}
    asked = set(payload.get("source_ids") or [])
    return "bounded_research" if asked and asked <= host_ids else "retrieve"


def _child(need: EvidenceNeed, source_ids: list[str]) -> RequestProposal:
    """Build the retrieval child request for one need."""
    payload = RetrievalRequestPayload(need=need, source_ids=source_ids)
    return RequestProposal(
        kind=RequestKind.EVIDENCE, question=need.question, evidence_needs=[need],
        payload_schema=schema_ids.RETRIEVAL_REQUEST, payload=payload.model_dump(mode="json"),
        requested_output_schema=schema_ids.EVIDENCE_BUNDLE, priority=need.priority)


def _candidates(ctx: ExecutionContext, need: EvidenceNeed, plan: Plan) -> list[SourceConfig]:
    """Catalog sources covering the need, narrowed by scope source ids and caller restrictions."""
    scope_ids, restricted = set(ctx.scope.source_ids), set(plan.source_restrictions)
    return [s for s in ctx.config.sources if need.category in s.categories
            and (not scope_ids or s.id in scope_ids) and (not restricted or s.id in restricted)]


def resolve_sources(ctx: ExecutionContext, needs: list[EvidenceNeed], plan: Plan) -> Resolution:
    """Map each need to a native retrieval child, a host.research child, or unavailable."""
    out = Resolution()
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
            out.requests.append(_child(need, ids))
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
    return out


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:00 [python-coder]: Source filtering by `technologies` is not applied because a
#   SourceConfig carries no technology field; technologies only feed retrieval query terms.
#   (#KernelBootstrapV0/P5)
# ====================================================================
