"""
MODULE: kernel.scheduler.nodes_integrate
GOAL: The `integrate` node: validate and merge every new capability result in sorted
    invocation-id order, update fingerprints and budgets, resume parents whose children are done
    and advance the state revision.
BUSINESS CONTEXT: This is the only place where capability output becomes run state, so it is
    where forged ids, invalid outputs, repeated work and false completion are stopped
    (Rev 3 section 8.1 steps 6 to 10).
ARCHITECTURE: Runs once per superstep after all workers finished (several edges into it trigger
    it once). Results are found through the current invocation of each DISPATCHED item (or of an
    item parked on an interaction), processed in sorted order, and merged through Draft so the
    outcome is independent of worker completion order.
"""

from __future__ import annotations

from typing import Any

from langgraph.runtime import Runtime

from kernel.contracts import CapabilityInvocation, ResultStatus, WorkItem, WorkItemStatus
from kernel.scheduler import guards
from kernel.scheduler.context import KernelRuntime, sequential_node
from kernel.scheduler.merge import Draft, reject_result, resume_ready_parents, settle_result
from kernel.scheduler.nodes_execute import ELAPSED_KEY, JEV_RESERVED_KEY
from kernel.scheduler.state import KernelState
from kernel.scheduler.validation import validate_result


def pending_invocations(state: KernelState, items: dict[str, WorkItem]
                        ) -> list[CapabilityInvocation]:
    """Return current invocations whose result arrived and is not integrated, sorted by id."""
    results = state.get("results", {})
    pending: list[CapabilityInvocation] = []
    for invocation in state.get("invocations", {}).values():
        item = items.get(invocation.work_item_id)
        if item is None or invocation.id not in results or invocation.attempt != item.attempts:
            continue
        parked = item.status is WorkItemStatus.WAITING and item.interaction_ref is not None
        if item.status is WorkItemStatus.DISPATCHED or parked:
            pending.append(invocation)
    return sorted(pending, key=lambda i: i.id)


def _versions(invocation: CapabilityInvocation, continuation_state: dict | None
              ) -> dict[str, str]:
    """Return the version map folded into the no-progress fingerprint."""
    versions = dict(invocation.versions)
    for key, value in (continuation_state or {}).items():
        if key.endswith("_version"):
            versions[key] = str(value)
    return versions


def _no_progress(state: KernelState, draft: Draft, item: WorkItem,
                 invocation: CapabilityInvocation, continuation_state: dict | None,
                 scope_revision: dict | None, limit: int) -> bool:
    """Count this attempt's fingerprint and return True when it repeats beyond the limit."""
    request = draft.request_of(item)
    fingerprint = guards.attempt_fingerprint(
        request.dedup_key or "", request.requested_output_schema, scope_revision,
        guards.evidence_revision(draft.evidence.values()),
        _versions(invocation, continuation_state))
    seen = state.get("fingerprints", {}).get(fingerprint, 0) + draft.fingerprints.get(
        fingerprint, 0)
    draft.fingerprints[fingerprint] = draft.fingerprints.get(fingerprint, 0) + 1
    return seen + 1 > limit


def _integrate_one(state: KernelState, draft: Draft, invocation: CapabilityInvocation,
                   runtime: KernelRuntime) -> None:
    """Validate one result and settle it onto its work item."""
    limits = runtime.config.limits
    item = draft.items[invocation.work_item_id]
    result = draft.results[invocation.id]
    verdict = validate_result(result, invocation, draft.request_of(item), draft.evidence,
                              draft.findings)
    if not verdict.ok:
        reject_result(draft, item, invocation, verdict.code, verdict.text())
        return
    revision = state["task"].scope.revision
    scope_revision = revision.model_dump() if revision else None
    repeated = False
    if result.status is ResultStatus.WAITING:
        repeated = _no_progress(state, draft, item, invocation, result.continuation_state,
                                scope_revision, limits.no_progress_limit)
    settle_result(draft, item, invocation, result, limits, scope_revision, no_progress=repeated)
    draft.emit("result.integrated", result.status.value, work_item_id=item.id,
               invocation_id=invocation.id)


@sequential_node("integrate")
async def integrate(state: KernelState, runtime: Runtime[KernelRuntime]) -> dict[str, Any]:
    """Merge all new results deterministically and resume finished parents."""
    ctx = runtime.context
    draft = Draft(state, ctx.clock())
    draft.rev += 1
    pending = pending_invocations(state, draft.items)
    for invocation in pending:
        _integrate_one(state, draft, invocation, ctx)
    resumed = resume_ready_parents(draft)
    results = [draft.results[i.id] for i in pending]
    reserved = sum(int(r.diagnostics.get(JEV_RESERVED_KEY, 0)) for r in results)
    elapsed = max((float(r.diagnostics.get(ELAPSED_KEY, 0.0)) for r in results), default=0.0)
    budgets = draft.budgets.model_copy(update={
        "jev_calls": draft.budgets.jev_calls + reserved,
        "active_seconds": draft.budgets.active_seconds + elapsed})
    budgets = guards.account_usage(budgets, [u for r in results for u in r.usage],
                                   ctx.config.jev.price_per_input_token_usd)
    if len(pending) > draft.neutral:
        streak = 0 if draft.progress else budgets.no_progress_streak + 1
        budgets = budgets.model_copy(update={"no_progress_streak": streak})
    draft.budgets = budgets
    update = draft.update()
    update["dispatch"] = {}
    changed = bool(pending or resumed or state.get("dispatch"))
    update["state_revision"] = draft.rev if changed else draft.rev - 1
    return update


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:30 [python-coder]: The no-progress fingerprint counts only WAITING attempts:
#   a completed result ends the work and a retried transient failure is not a new attempt.
#   (#KernelBootstrapV0/P4)
# - 2026-09-30 22:30 [python-coder]: Transient retries are neutral for the run-level streak
#   (they do not reset it and do not add to it): max_retries bounds them on its own, and
#   counting them would halt a run after `no_progress_limit` retries although `max_retries`
#   is larger by default. (#KernelBootstrapV0/P4)
# - 2026-09-30 22:30 [python-coder]: Creating a new work item counts as progress for the run
#   streak (design lists evidence, finding, decision status, terminal item): otherwise a healthy
#   root -> child -> grandchild chain trips the guard before any evidence exists.
#   (#KernelBootstrapV0/P4)
# ====================================================================
