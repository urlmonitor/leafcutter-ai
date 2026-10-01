"""
MODULE: kernel.scheduler.nodes_gaps
GOAL: The `record_gaps` node and the gap-outcome settlement run by `schedule`: record capability
    gap observations through the GapStorePort, rebind an unsupported item to an approved generic
    host operation when fallback is allowed (else block it), write template-authored backlog
    drafts, and record the fallback outcome once the host work ended.
BUSINESS CONTEXT: A request no capability can serve is product evidence (Rev 3 section 14): it is
    recorded once per distinct need so the backlog learns what is missing. Only `unsupported` and
    `host_only` are build opportunities; a denied native action is never reclassified as a missing
    capability and routed through a permissive fallback, and `unavailable` is never a gap.
ARCHITECTURE: Deterministic housekeeping, never Jev-routed. `_block_no_capability` and
    `_rebind_to_host` are the two outcomes of an unsupported item. Rebinding sets the item READY
    with a pinned host binding, so the next `schedule`/`route` pass re-validates it through the
    ordinary bound-dispatch path and opens the interaction: no second pause mechanism. The
    fallback observation is stored when its outcome is known (`settle_gap_outcomes`, called from
    `schedule`), so the append-only store holds exactly one observation per occurrence.
"""

from __future__ import annotations

from typing import Any

from langgraph.runtime import Runtime

from kernel.contracts import (
    CapabilityDescriptor,
    CapabilityGap,
    ExecutionMode,
    FallbackOutcome,
    GapType,
    Request,
    RequestKind,
    RoutingAssessment,
    RoutingOutcome,
    RunEvent,
    WorkItem,
    WorkItemStatus,
    compute_gap_key,
    new_id,
)
from kernel.contracts.work import Binding
from kernel.persistence.gap_store import publish_gap
from kernel.registry.eligibility import MVP_SIDE_EFFECTS
from kernel.scheduler import guards
from kernel.scheduler.context import KernelRuntime, run_corr
from kernel.scheduler.guards import normalize_text
from kernel.scheduler.merge import Draft
from kernel.scheduler.state import KernelState, new_event

#: Number of goal tokens that identify a free-form capability need (design part 4).
MAX_NEED_TOKENS = 12
#: Exclusion reasons that mean "the run may not do this" (never a missing capability).
DENIAL_CODES = frozenset({"permission_denied", "side_effect_forbidden"})
HUMAN_CAPABILITY = "kernel.human"
_DONE = frozenset({WorkItemStatus.COMPLETED, WorkItemStatus.PARTIAL})
_FAILED = frozenset({WorkItemStatus.FAILED, WorkItemStatus.BLOCKED, WorkItemStatus.CANCELLED})


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


def denied_candidates(assessment: RoutingAssessment | None) -> list[str]:
    """Return ids of candidates excluded because the run may not use them (permission, effects)."""
    if assessment is None:
        return []
    return sorted(e.capability_id for e in assessment.excluded
                  if e.reason_code.split(":", 1)[0] in DENIAL_CODES)


def build_gap(state: KernelState, item: WorkItem, request: Request,
              assessment: RoutingAssessment | None, gap_type: GapType, now: Any,
              outcome: FallbackOutcome = FallbackOutcome.NONE, **extra: Any) -> CapabilityGap:
    """Build the CapabilityGap observation for one unserved request."""
    need = normalized_need(request)
    component_ids = list(state["task"].scope.component_ids)
    eligible = assessment.eligible_candidate_ids if assessment else []
    excluded = assessment.excluded if assessment else []
    considered = sorted({*eligible, *(e.capability_id for e in excluded)})
    return CapabilityGap(
        id=new_id("gap"), created_at=now, updated_at=now, first_seen=now, last_seen=now,
        gap_key=compute_gap_key(gap_type, request.kind, request.payload_schema,
                                request.requested_output_schema, need, component_ids),
        gap_type=gap_type, goal=request.goal or request.question or "", normalized_need=need,
        request_kind=request.kind, input_schema=request.payload_schema,
        output_schema=request.requested_output_schema, scope_component_ids=component_ids,
        registry_snapshot_hash=state["registry"].content_hash, candidates_considered=considered,
        why_insufficient=", ".join(assessment.reason_codes) if assessment else "",
        example_run_ids=[state["run_id"]], fallback_outcome=outcome, **extra)


def fallback_candidate(state: KernelState, ctx: KernelRuntime, draft: Draft, request: Request
                       ) -> tuple[CapabilityDescriptor | None, str]:
    """Return the host operation that may serve an unsupported request, or (None, reason).

    Fallback is bounded: fallback must be enabled, the request must not be human, and the
    candidate must be an enabled, available, bound host_handoff capability that accepts the
    request kind, produces the requested output schema, needs only granted permissions, has no
    forbidden side effects, fits the scope and leaves host-operation budget.
    """
    if not (ctx.config.host.enabled and ctx.config.host.fallback_on_no_match):
        return None, "host fallback is disabled"
    if request.kind is RequestKind.HUMAN:
        return None, "human questions are never routed to a host fallback"
    scope_ids = set(state["task"].scope.component_ids)
    granted = set(state.get("permissions", []))
    left = guards.host_operations_available(draft.budgets, ctx.config.limits)
    for d in sorted(state["registry"].descriptors, key=lambda x: x.id):
        ops = d.cost_hints.host_operations if d.cost_hints.host_operations is not None else 1
        usable = (d.execution_mode is ExecutionMode.HOST_HANDOFF and d.enabled
                  and d.availability.status != "unavailable"
                  and request.kind in d.request_kinds
                  and request.requested_output_schema in d.produces_schemas
                  and ctx.bindings.has(d.binding, d.version)
                  and set(d.permissions_required) <= granted
                  and d.side_effect_class in MVP_SIDE_EFFECTS
                  and (not d.components or bool(set(d.components) & scope_ids)))
        if usable and ops <= left:
            return d, ""
    return None, "no approved host operation produces the requested output"


def _block_no_capability(draft: Draft, item: WorkItem, reason: str = "") -> None:
    """Block the item because nothing can serve it (and, if given, why fallback was not used)."""
    text = "no_capability: no registered capability can serve this request"
    draft.put_item(item, status=WorkItemStatus.BLOCKED,
                   limitations=[*item.limitations, f"{text}; {reason}" if reason else text])
    draft.progress = True
    draft.emit("work_item.blocked", "no_capability", work_item_id=item.id)


def _rebind_to_host(draft: Draft, item: WorkItem, descriptor: CapabilityDescriptor,
                    gap: CapabilityGap) -> None:
    """Pin a host binding on the item and make it READY so the next route pass dispatches it."""
    binding = Binding(capability_id=descriptor.id, version=descriptor.version,
                      execution_mode=ExecutionMode.HOST_HANDOFF)
    ops = descriptor.cost_hints.host_operations
    draft.budgets = draft.budgets.model_copy(update={
        "host_operations": draft.budgets.host_operations + (ops if ops is not None else 1)})
    draft.put_item(item, status=WorkItemStatus.READY, binding=binding)
    draft.emit("gap.fallback_started", descriptor.id, work_item_id=item.id, gap_id=gap.id,
               capability_id=descriptor.id)


def _trace_gap(runtime: KernelRuntime, state: KernelState, item: WorkItem,
               gap: CapabilityGap) -> None:
    """Emit the `gap.recorded` tracer event (countable: key, type, need; no payload)."""
    runtime.tracer.event(
        "gap.recorded", run_corr(state, work_item_id=item.id),
        payload={"gap_id": gap.id, "gap_key": gap.gap_key, "gap_type": gap.gap_type.value,
                 "normalized_need": gap.normalized_need,
                 "request_kind": gap.request_kind.value,
                 "fallback_outcome": gap.fallback_outcome.value})


def _record_with_events(ctx: KernelRuntime, state: KernelState, item: WorkItem,
                        gap: CapabilityGap, now: Any, *, with_draft: bool = True
                        ) -> tuple[CapabilityGap, list[RunEvent]]:
    """Publish one observation; return the gap as stored and the run events to append."""
    stored = publish_gap(ctx.gap_store, gap, with_draft=with_draft)
    events = [new_event(state["run_id"], now, "gap.recorded", gap.gap_type.value,
                        work_item_id=item.id, gap_id=gap.id)]
    _trace_gap(ctx, state, item, gap)
    if stored is None:
        events.append(new_event(state["run_id"], now, "gap.record_failed", gap.gap_key,
                                work_item_id=item.id))
    return stored or gap, events


def _record(ctx: KernelRuntime, state: KernelState, draft: Draft, item: WorkItem,
            gap: CapabilityGap) -> CapabilityGap:
    """Publish one observation and queue its run events on the draft."""
    stored, events = _record_with_events(ctx, state, item, gap, draft.now)
    draft.events.extend(events)
    return stored


def _handle_unsupported(state: KernelState, ctx: KernelRuntime, draft: Draft, item: WorkItem,
                        assessment: RoutingAssessment) -> CapabilityGap:
    """Decide between permission block, host fallback and plain block for a no_match item."""
    request = draft.request_of(item)
    denied = denied_candidates(assessment)
    if denied:
        gap = build_gap(state, item, request, assessment, GapType.PERMISSION,
                        draft.now, FallbackOutcome.BLOCKED)
        _block_no_capability(draft, item, f"denied, not missing: {', '.join(denied)}")
        return _record(ctx, state, draft, item, gap)
    descriptor, why = fallback_candidate(state, ctx, draft, request)
    if descriptor is None:
        gap = build_gap(state, item, request, assessment, GapType.UNSUPPORTED,
                        draft.now, FallbackOutcome.BLOCKED)
        _block_no_capability(draft, item, why)
        return _record(ctx, state, draft, item, gap)
    gap = build_gap(state, item, request, assessment, GapType.UNSUPPORTED, draft.now,
                    missing_native_capability=f"native implementation of {descriptor.id}")
    _rebind_to_host(draft, item, descriptor, gap)
    return gap


async def record_gaps(state: KernelState, runtime: Runtime[KernelRuntime]) -> dict[str, Any]:
    """Record a gap for each no_match or insufficient_context item; fall back or block."""
    ctx = runtime.context
    draft = Draft(state, ctx.clock())
    gaps: dict[str, CapabilityGap] = {}
    host_budget_used = False
    for item_id in state.get("dispatch", {}).get("gap", []):
        item = draft.items[item_id]
        assessment = state["routing"].get(item.routing_ref or "")
        if assessment is None or assessment.outcome not in (RoutingOutcome.NO_MATCH,
                                                            RoutingOutcome.INSUFFICIENT_CONTEXT):
            continue
        if assessment.outcome is RoutingOutcome.NO_MATCH:
            gap = _handle_unsupported(state, ctx, draft, item, assessment)
            host_budget_used = host_budget_used or (
                draft.items[item.id].status is WorkItemStatus.READY)
        else:
            gap = _record(ctx, state, draft, item, build_gap(
                state, item, draft.request_of(item), assessment, GapType.AMBIGUOUS, draft.now))
        gaps[gap.id] = gap
    update = draft.update(include_budgets=host_budget_used)
    update["gaps"] = gaps
    return update


def native_alternatives(state: KernelState, request: Request) -> list[str]:
    """Return ids of native capabilities that share the request kind and requested output."""
    return sorted(d.id for d in state["registry"].descriptors
                  if d.execution_mode is ExecutionMode.NATIVE and request.kind in d.request_kinds
                  and request.requested_output_schema in d.produces_schemas)


def fallback_outcome_of(item: WorkItem, halting: bool) -> FallbackOutcome | None:
    """Map an item's state to the fallback outcome, or None while it is still running."""
    if item.status in _DONE:
        return FallbackOutcome.HOST_COMPLETED
    if item.status in _FAILED:
        return FallbackOutcome.HOST_FAILED
    return FallbackOutcome.NONE if halting else None


def _settle_fallbacks(state: KernelState, ctx: KernelRuntime, draft: Draft, halting: bool,
                      recorded: set[str]) -> dict[str, CapabilityGap]:
    """Store the observation of each started fallback whose host work ended."""
    out: dict[str, CapabilityGap] = {}
    pending = state.get("gaps", {})
    for event in state.get("events", []):
        gap_id = event.refs.get("gap_id")
        if event.kind != "gap.fallback_started" or gap_id in recorded or gap_id not in pending:
            continue
        item = draft.items[event.refs["work_item_id"]]
        outcome = fallback_outcome_of(item, halting)
        if outcome is None:
            continue
        final = pending[gap_id].model_copy(update={"fallback_outcome": outcome,
                                                   "last_seen": draft.now})
        out[gap_id] = _record(ctx, state, draft, item, final)
        recorded.add(gap_id)
    return out


def record_host_only(state: KernelState, ctx: KernelRuntime, item: WorkItem,
                     outcome: FallbackOutcome, now: Any | None = None
                     ) -> tuple[CapabilityGap, list[RunEvent]] | None:
    """Record the `host_only` observation of one executed host operation (Rev 3 section 14).

    A host operation is a capability that exists only as a host implementation: demand for it is
    evidence for a native one. The observation uses the same gap key, store and tracer event as
    every other gap type, so occurrences aggregate with the others of the same need. A host
    operation started as a gap fallback is skipped (its observation is the `unsupported` gap with
    the fallback outcome), as is a human question.

    Args:
        state: Graph state (work items, requests, registry, routing, events).
        ctx: The runtime (gap store, tracer, clock).
        item: The work item whose host operation ran.
        outcome: `host_completed` or `host_failed`.
        now: Observation time (default: the runtime clock).

    Returns:
        tuple[CapabilityGap, list[RunEvent]] | None: The gap as stored, to merge into
            `state["gaps"]`, and the events (`gap.recorded`) to append to the run's events;
            None when nothing is to be recorded.
    """
    binding = item.binding
    if (binding is None or binding.execution_mode is not ExecutionMode.HOST_HANDOFF
            or binding.capability_id == HUMAN_CAPABILITY):
        return None
    if any(e.kind == "gap.fallback_started" and e.refs.get("work_item_id") == item.id
           for e in state.get("events", [])):
        return None
    request = state["requests"][item.request_id]
    now = now or ctx.clock()
    twins = native_alternatives(state, request)
    gap = build_gap(state, item, request, state.get("routing", {}).get(item.routing_ref or ""),
                    GapType.HOST_ONLY, now, outcome,
                    missing_native_capability=f"native implementation of {binding.capability_id}")
    reason = (f"host-backed only; native alternatives for this request kind: {', '.join(twins)}"
              if twins else "host-backed only; no native implementation exists")
    gap = gap.model_copy(update={"why_insufficient": reason})
    return _record_with_events(ctx, state, item, gap, now, with_draft=not twins)


def _settle_host_only(state: KernelState, ctx: KernelRuntime, draft: Draft,
                      skip_items: set[str]) -> dict[str, CapabilityGap]:
    """Record a host_only observation for each finished host operation not yet recorded.

    This is the catch-all for runs where the interaction node does not record at answer time.
    """
    out: dict[str, CapabilityGap] = {}
    for item in draft.sorted_items():
        outcome = fallback_outcome_of(item, False)
        if item.id in skip_items or outcome in (None, FallbackOutcome.NONE):
            continue
        recorded = record_host_only(state, ctx, item, outcome, draft.now)
        if recorded is None:
            continue
        gap, events = recorded
        draft.events.extend(events)
        out[gap.id] = gap
        skip_items.add(item.id)
    return out


def settle_gap_outcomes(state: KernelState, ctx: KernelRuntime, draft: Draft, *,
                        halting: bool) -> dict[str, CapabilityGap]:
    """Record the outcome observations that became known since the last scheduling pass.

    Called by `schedule` before it marks unresolved work. A started fallback is stored with
    `host_completed` or `host_failed`; when the run halts while it is still open it is stored
    with `none` (no outcome). Every other finished host operation records a `host_only`
    observation once (unless `record_host_only` already did, at answer time).

    Returns:
        dict[str, CapabilityGap]: Gaps to merge into `state["gaps"]`.
    """
    events = state.get("events", [])
    recorded = {e.refs["gap_id"] for e in events
                if e.kind == "gap.recorded" and "gap_id" in e.refs}
    skip_items = {e.refs["work_item_id"] for e in events
                  if e.kind in ("gap.recorded", "gap.fallback_started")
                  and "work_item_id" in e.refs}
    done = _settle_fallbacks(state, ctx, draft, halting, recorded)
    done.update(_settle_host_only(state, ctx, draft, skip_items))
    return done


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 16:00 [python-coder]: `record_host_only` is public and returns the events to append
#   instead of writing state, so the interaction node can call it at answer time (every executed
#   host operation, ADR-056) and `schedule` can still settle runs where it did not. A native
#   alternative changes the wording and suppresses the draft, not the observation: demand for a
#   host operation is evidence either way, but "build a native one" only makes sense when none
#   exists. (#KernelBootstrapV0/P9)
# - 2026-10-01 14:00 [python-coder]: Fallback rebinds the item to READY with a pinned host
#   binding instead of opening the interaction inside the gap node: `open_interactions` owns the
#   queue (a replace-reducer list) and runs beside this node in the same superstep, so a second
#   writer would race; the next route pass dispatches bound items anyway. (#KernelBootstrapV0/P9)
# - 2026-10-01 14:00 [python-coder]: A fallback observation is stored once, when its outcome is
#   known, not once at detection and once at completion: the store is append-only and sums
#   occurrences, so two observations would count one need twice. A run that halts first stores it
#   with outcome `none`. (#KernelBootstrapV0/P9)
# - 2026-10-01 14:00 [python-coder]: Any `permission_denied` or `side_effect_forbidden` exclusion
#   makes a no_match a `permission` gap that blocks without fallback: a run that may not do
#   something must not get it done through a permissive host path (spec section 14).
#   (#KernelBootstrapV0/P9)
# - 2026-10-01 14:00 [python-coder]: Fallback candidates are chosen by produced output schema and
#   request kind, not by payload schema: the host receives the original payload as its input
#   artifact, and the output contract is what the parent needs. (#KernelBootstrapV0/P9)
# - 2026-10-01 00:30 [python-coder]: `gap.recorded` goes to the tracer next to the run event so
#   gaps stay countable in traces (design part 5, colony-memory prerequisites). The tracer call
#   is not wrapped: tracers degrade internally and never raise. (#KernelBootstrapV0/OBS)
# - 2026-09-30 22:30 [python-coder]: `ambiguous` observations are recorded for every
#   insufficient_context outcome (design part 4 gap table) but never block here: the route node
#   already chose between a human clarification and blocking. (#KernelBootstrapV0/P4)
# ====================================================================
