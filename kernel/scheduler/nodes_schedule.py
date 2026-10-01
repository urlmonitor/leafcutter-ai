"""
MODULE: kernel.scheduler.nodes_schedule
GOAL: The `schedule` node and its conditional edge: check the run guards and cancellation, put
    ready work with satisfied dependencies on the agenda, and decide between route, awaiting an
    interaction and finalize.
BUSINESS CONTEXT: The scheduler must always make progress or stop with diagnostics: a tripped
    guard, a cancellation or a deadlock (nothing runnable, nothing pending) ends in finalize
    instead of looping (Rev 3 sections 8.1 and 8.4).
ARCHITECTURE: Reads the pure guard functions; reserves capacity by trimming the agenda to
    `max_concurrent_native`; stamps the head interaction packet with the current state revision
    just before the graph pauses, because that revision is what a resume must echo back.
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.runtime import Runtime

from kernel.contracts import HostWorkRequest, Priority, RunStatus, WorkItemStatus
from kernel.scheduler import guards
from kernel.scheduler.context import KernelRuntime, flush_events, run_corr, sequential_node
from kernel.scheduler.merge import Draft
from kernel.scheduler.nodes_gaps import settle_gap_outcomes
from kernel.scheduler.state import KernelState

logger = logging.getLogger(__name__)


def block_failed_dependencies(draft: Draft) -> None:
    """Block new READY items whose required dependency already failed, blocked or was cancelled."""
    for item in draft.sorted_items():
        if item.status is not WorkItemStatus.READY or item.continuation is not None:
            continue
        deps = [draft.items[d] for d in item.dependency_ids if d in draft.items]
        if not deps or any(d.status not in guards.TERMINAL_STATUSES for d in deps):
            continue
        bad = [d.id for d in deps if d.status in (WorkItemStatus.FAILED, WorkItemStatus.BLOCKED,
                                                  WorkItemStatus.CANCELLED)]
        if bad and draft.request_of(item).priority is Priority.REQUIRED:
            draft.put_item(item, status=WorkItemStatus.BLOCKED,
                           limitations=[*item.limitations,
                                        f"dependency_failed: {', '.join(bad)}"])
            draft.emit("guard.tripped", "dependency_failed", work_item_id=item.id,
                       guard="dependency_failed")


def ready_agenda(draft: Draft, capacity: int) -> list[str]:
    """Return ready item ids (dependencies terminal), required first, trimmed to capacity."""
    ready = []
    for item in draft.sorted_items():
        if item.status is not WorkItemStatus.READY:
            continue
        if any(d in draft.items and draft.items[d].status not in guards.TERMINAL_STATUSES
               for d in item.dependency_ids):
            continue
        rank = 0 if draft.request_of(item).priority is Priority.REQUIRED else 1
        ready.append((rank, item.created_seq, item.id))
    return [item_id for _, _, item_id in sorted(ready)[:capacity]]


def stop_unresolved(draft: Draft, root_id: str, guard: str) -> list[str]:
    """End the work a tripped guard leaves open and return the ids of the items it ended.

    A cancellation cancels every open item, children included, and the root. Any other guard
    blocks the open non-root items with an `unresolved_at_<guard>` limitation naming their goal,
    so the partial or blocked envelope lists the unresolved work; the root stays open so the
    outcome decides between partial and blocked from what was achieved.
    """
    cancelled = guard == "cancelled"
    ids = guards.unresolved_item_ids(draft.items, root_id)
    if cancelled and draft.items[root_id].status not in guards.TERMINAL_STATUSES:
        ids.append(root_id)
    for item_id in ids:
        item = draft.items[item_id]
        if cancelled:
            draft.put_item(item, status=WorkItemStatus.CANCELLED, interaction_ref=None,
                           limitations=[*item.limitations, "cancelled: the run was cancelled"])
        else:
            text = guards.unresolved_text(guard, draft.request_of(item).goal)
            draft.put_item(item, status=WorkItemStatus.BLOCKED, interaction_ref=None,
                           limitations=[*item.limitations, text])
    return ids


def _stamp_head_packet(state: KernelState, runtime: KernelRuntime) -> dict[str, Any]:
    """Re-stamp the head interaction with the current state revision and persist it."""
    head = state["interaction_queue"][0]
    packet = state["interactions"][head]
    revision = state.get("state_revision", 0)
    if packet.state_revision == revision:
        return {}
    stamped = packet.model_copy(update={"state_revision": revision})
    try:
        runtime.run_store.save_interaction(state["run_id"], stamped)
    except OSError:
        logger.exception("could not persist interaction %s", head)
        raise
    return {"interactions": {head: stamped}}


def _status_for(state: KernelState, agenda: list[str]) -> RunStatus:
    """Return the run status the envelope should show while the graph is between steps."""
    queue = state.get("interaction_queue", [])
    if agenda or not queue:
        return RunStatus.RUNNING
    packet = state["interactions"][queue[0]]
    return RunStatus.WAITING_HOST if isinstance(packet, HostWorkRequest) \
        else RunStatus.WAITING_HUMAN


@sequential_node("schedule")
async def schedule(state: KernelState, runtime: Runtime[KernelRuntime]) -> dict[str, Any]:
    """Check guards, compute the agenda and record why the run stops, if it does."""
    ctx = runtime.context
    limits = ctx.config.limits
    draft = Draft(state, ctx.clock())
    queue = state.get("interaction_queue", [])
    draft.budgets = draft.budgets.model_copy(update={
        "scheduler_iterations": draft.budgets.scheduler_iterations + 1})
    block_failed_dependencies(draft)
    root = draft.items[state["task"].root_work_item_id]
    root_done = root.status in guards.TERMINAL_STATUSES
    agenda = [] if root_done else ready_agenda(draft, limits.max_concurrent_native)
    trip = guards.check_run_guards(
        draft.budgets, limits, max_iterations=guards.max_iterations_for(
            limits, ctx.max_scheduler_iterations), queue_empty=not queue,
        cancelled=ctx.cancel_probe())
    halt = None if root_done else (trip.guard if trip else None)
    if halt is None and not root_done and not agenda and not queue:
        halt, trip = "deadlock", guards.GuardTrip("deadlock", "nothing is runnable or pending")
    gaps = settle_gap_outcomes(state, ctx, draft, halting=halt is not None)
    if halt is not None:
        waited = guards.waiting_seconds(state.get("events", []))
        note = f"; {waited:.1f}s waiting on interactions is not active time" if waited else ""
        draft.emit("guard.tripped", f"{trip.detail if trip else halt}{note}", guard=halt)
        ctx.tracer.event("guard.tripped", run_corr(state), level="WARNING",
                         payload={"guard": halt})
        stop_unresolved(draft, state["task"].root_work_item_id, halt)
    update = draft.update()
    if gaps:
        update["gaps"] = gaps
    if halt is not None and queue:
        update["interaction_queue"] = []
    status = RunStatus.RUNNING if halt else _status_for(state, agenda)
    if status in (RunStatus.WAITING_HOST, RunStatus.WAITING_HUMAN):
        update.update(_stamp_head_packet(state, ctx))
    update.update(agenda=agenda, halt_reason=halt, status=status,
                  events_flushed=flush_events(ctx.run_store, state))
    return update


def after_schedule(state: KernelState) -> str:
    """Edge: finalize on halt or a terminal root, else route, else await, else finalize."""
    root = state["work_items"][state["task"].root_work_item_id]
    if state.get("halt_reason") or root.status in guards.TERMINAL_STATUSES:
        return "finalize"
    if state.get("agenda"):
        return "route"
    if state.get("interaction_queue"):
        return "await_interaction"
    return "finalize"


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 14:00 [python-coder]: A tripped guard ends the open work in the same step: children
#   are cancelled (cancellation) or blocked with `unresolved_at_<guard>` (other guards), and the
#   pending queue is cleared, so the envelope names the unresolved work and a late submission is
#   rejected as cancelled_or_superseded. (#KernelBootstrapV0/P9)
# - 2026-10-01 14:00 [python-coder]: Gap outcomes are settled here, before unresolved work is
#   marked, because schedule is the one sequential node that sees every item after each
#   integrate pass (record_gaps only runs when something is unsupported). (#KernelBootstrapV0/P9)
# - 2026-09-30 22:30 [python-coder]: A root that is already terminal suppresses guard trips:
#   finishing work is never turned into a guard stop by a late counter. (#KernelBootstrapV0/P4)
# - 2026-09-30 22:30 [python-coder]: Head-packet revision stamping happens in schedule (right
#   before await_interaction) so the revision the host echoes back is the paused state's.
#   (#KernelBootstrapV0/P4)
# ====================================================================
