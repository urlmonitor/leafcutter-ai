"""
MODULE: kernel.scheduler.nodes_gaps
GOAL: The `record_gaps` node (first version): record a capability gap observation through the
    GapStorePort for work the catalog could not serve, then block the item.
BUSINESS CONTEXT: A request no capability can serve is product evidence (Rev 3 section 14): it is
    recorded once per distinct need so the backlog learns what is missing. Only `no_match` is a
    gap to block on; `unavailable` (exists but cannot run) is never a gap.
ARCHITECTURE: Deterministic housekeeping, never Jev-routed. The seam for P9: replace
    `_block_no_capability` with fallback-to-host rebinding, drafts and dedup hardening; the gap
    identity (`compute_gap_key`) and the store port are already the final ones.
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.runtime import Runtime

from kernel.contracts import (
    CapabilityGap,
    FallbackOutcome,
    GapType,
    Request,
    RequestKind,
    RoutingAssessment,
    RoutingOutcome,
    WorkItem,
    WorkItemStatus,
    compute_gap_key,
    new_id,
)
from kernel.scheduler.context import KernelRuntime
from kernel.scheduler.guards import normalize_text
from kernel.scheduler.merge import Draft
from kernel.scheduler.state import KernelState

logger = logging.getLogger(__name__)
#: Number of goal tokens that identify a free-form capability need (design part 4).
MAX_NEED_TOKENS = 12


def normalized_need(request: Request) -> str:
    """Return the gap identity text: need category, operation, or the sorted goal tokens."""
    payload = request.payload
    if request.kind is RequestKind.EVIDENCE:
        need = payload.get("need")
        category = need.get("category") if isinstance(need, dict) else None
        if category is None and request.evidence_needs:
            category = request.evidence_needs[0].category.value
        return str(category or "evidence")
    if request.kind in (RequestKind.OPTIONS, RequestKind.SYNTHESIS):
        return str(payload.get("operation") or request.kind.value)
    tokens = normalize_text(request.goal or request.question).split()
    return " ".join(tokens[:MAX_NEED_TOKENS])


def build_gap(state: KernelState, item: WorkItem, request: Request,
              assessment: RoutingAssessment, gap_type: GapType, now: Any) -> CapabilityGap:
    """Build the CapabilityGap observation for one unserved request."""
    need = normalized_need(request)
    component_ids = list(state["task"].scope.component_ids)
    considered = sorted({*assessment.eligible_candidate_ids,
                         *(e.capability_id for e in assessment.excluded)})
    blocked = gap_type is GapType.UNSUPPORTED
    return CapabilityGap(
        id=new_id("gap"), created_at=now, updated_at=now, first_seen=now, last_seen=now,
        gap_key=compute_gap_key(gap_type, request.kind, request.payload_schema,
                                request.requested_output_schema, need, component_ids),
        gap_type=gap_type, goal=request.goal or request.question or "", normalized_need=need,
        request_kind=request.kind, input_schema=request.payload_schema,
        output_schema=request.requested_output_schema, scope_component_ids=component_ids,
        registry_snapshot_hash=state["registry"].content_hash, candidates_considered=considered,
        why_insufficient=", ".join(assessment.reason_codes), example_run_ids=[state["run_id"]],
        fallback_outcome=FallbackOutcome.BLOCKED if blocked else FallbackOutcome.NONE)


def _block_no_capability(draft: Draft, item: WorkItem) -> None:
    """Block the item because nothing can serve it (P9 replaces this with host fallback)."""
    draft.put_item(item, status=WorkItemStatus.BLOCKED,
                   limitations=[*item.limitations,
                                "no_capability: no registered capability can serve this request"])
    draft.progress = True
    draft.emit("work_item.blocked", "no_capability", work_item_id=item.id)


def _store(runtime: KernelRuntime, gap: CapabilityGap) -> bool:
    """Record the observation; a store failure is logged and reported, never fatal."""
    try:
        runtime.gap_store.record(gap)
    except OSError:
        logger.warning("could not record capability gap %s", gap.gap_key, exc_info=True)
        return False
    return True


async def record_gaps(state: KernelState, runtime: Runtime[KernelRuntime]) -> dict[str, Any]:
    """Record a gap for each no_match (unsupported) or insufficient_context (ambiguous) item."""
    ctx = runtime.context
    draft = Draft(state, ctx.clock())
    gaps: dict[str, CapabilityGap] = {}
    for item_id in state.get("dispatch", {}).get("gap", []):
        item = draft.items[item_id]
        assessment = state["routing"].get(item.routing_ref or "")
        if assessment is None or assessment.outcome not in (RoutingOutcome.NO_MATCH,
                                                            RoutingOutcome.INSUFFICIENT_CONTEXT):
            continue
        unsupported = assessment.outcome is RoutingOutcome.NO_MATCH
        gap = build_gap(state, item, draft.request_of(item), assessment,
                        GapType.UNSUPPORTED if unsupported else GapType.AMBIGUOUS, draft.now)
        gaps[gap.id] = gap
        draft.emit("gap.recorded", gap.gap_type.value, work_item_id=item.id, gap_id=gap.id)
        if not _store(ctx, gap):
            draft.emit("gap.record_failed", gap.gap_key, work_item_id=item.id)
        if unsupported:
            _block_no_capability(draft, item)
    update = draft.update(include_budgets=False)
    update["gaps"] = gaps
    return update


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:30 [python-coder]: `ambiguous` observations are recorded for every
#   insufficient_context outcome (design part 4 gap table) but never block here: the route node
#   already chose between a human clarification and blocking. (#KernelBootstrapV0/P4)
# ====================================================================
