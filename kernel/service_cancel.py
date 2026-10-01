"""
MODULE: kernel.service_cancel
GOAL: The durable mechanics of cancelling a run: a compare-and-update commit of the cancellation
    to run.json (first actor wins, idempotent), a service-level `run.cancelled` event in
    events.jsonl, and the closing of a paused graph thread so its state agrees with run.json.
BUSINESS CONTEXT: A cancellation must never be lost to a stale write and must never be
    overwritten by a later actor (Rev 3 section 13.1, design part 3 "Cancellation"): run.json is
    the authority, the graph follows it at its next superstep, and a paused run has no next
    superstep, so its checkpoint is closed explicitly.
ARCHITECTURE: `commit_cancel` re-reads run.json and retries the compare-and-update against the
    stored `state_revision`; it bumps that revision so a concurrent writer that read the record
    before the cancel fails its own compare. `append_service_event` gives service events a
    sequence number in a reserved range (`SERVICE_SEQ_BASE` and up) that graph events, numbered
    from 0 by the reducer, can never reach, so the two writers never collide. `close_paused_graph`
    uses `aupdate_state(as_node="finalize")`; verified on LangGraph 1.2.12 (design risk 5) to drop
    the pending interrupt and leave a thread that later resumes cannot continue.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, cast

from kernel.contracts.enums import RunStatus, WorkItemStatus
from kernel.contracts.run import RunEvent
from kernel.persistence.base import CancelInfo, RunRecord, RunStorePort
from kernel.scheduler import guards
from kernel.scheduler.nodes_lifecycle import decide_outcome
from kernel.scheduler.state import KernelState

logger = logging.getLogger(__name__)

#: First sequence number of service-level events; graph events count up from 0 and a run holds
#: far fewer than this many (the LangGraph recursion limit bounds supersteps).
SERVICE_SEQ_BASE = 1_000_000_000
MAX_COMMIT_ATTEMPTS = 5
TERMINAL_RECORD_STATUSES = frozenset({RunStatus.COMPLETED, RunStatus.PARTIAL, RunStatus.BLOCKED,
                                      RunStatus.FAILED, RunStatus.CANCELLED})


class CancelContended(RuntimeError):
    """The run record kept changing under the cancellation; nothing was written."""

    def __init__(self, run_id: str) -> None:
        """Build the message from the run id."""
        super().__init__(f"could not commit the cancellation of {run_id}: record kept changing")
        self.run_id = run_id


def compare_and_write(run_store: RunStorePort, record: RunRecord, expected_revision: int) -> bool:
    """Write the record if the stored revision still equals `expected_revision`.

    Every RunStorePort implements `compare_and_update`; this stays as the named seam the
    cancel and persist paths share.
    """
    return run_store.compare_and_update(record, expected_revision)


def commit_cancel(run_store: RunStorePort, run_id: str, actor_id: str, now: datetime
                  ) -> tuple[RunRecord, bool]:
    """Record the cancellation in run.json; the first actor wins and later calls change nothing.

    Returns:
        tuple[RunRecord, bool]: The record now stored and whether THIS call wrote the
            cancellation (False: already cancelled or already terminal).

    Raises:
        CancelContended: The record changed on every attempt.
    """
    for _ in range(MAX_COMMIT_ATTEMPTS):
        record = run_store.get_run(run_id)
        if record.cancel is not None or record.status in TERMINAL_RECORD_STATUSES:
            return record, False
        cancelled = record.model_copy(update={
            "cancel": CancelInfo(by=actor_id, at=now), "status": RunStatus.CANCELLED,
            "updated_at": now, "state_revision": record.state_revision + 1})
        if compare_and_write(run_store, cancelled, record.state_revision):
            return cancelled, True
    raise CancelContended(run_id)


def append_service_event(run_store: RunStorePort, run_id: str, kind: str, at: datetime,
                         detail: str = "", **refs: str) -> RunEvent:
    """Append an event numbered in the reserved service range and return it."""
    used = run_store.read_events(run_id, after_seq=SERVICE_SEQ_BASE - 1)
    event = RunEvent(seq=SERVICE_SEQ_BASE + len(used), run_id=run_id, kind=kind, at=at,
                     refs=dict(refs), detail=detail)
    try:
        run_store.append_event(event)
    except OSError:
        logger.warning("could not persist %s for run %s", kind, run_id, exc_info=True)
    return event


def _cancelled_items(values: dict[str, Any], actor_id: str, now: datetime) -> dict[str, Any]:
    """Return the work items (root and children) that are still open, now cancelled."""
    revision = int(values.get("state_revision", 0)) + 1
    changed: dict[str, Any] = {}
    for item in values["work_items"].values():
        if item.status in guards.TERMINAL_STATUSES:
            continue
        changed[item.id] = item.model_copy(update={
            "status": WorkItemStatus.CANCELLED, "interaction_ref": None, "updated_at": now,
            "updated_revision": max(item.updated_revision, revision),
            "limitations": [*item.limitations, f"cancelled: the run was cancelled by {actor_id}"]})
    return changed


async def close_paused_graph(session: Any, actor_id: str, now: datetime) -> dict[str, Any]:
    """Close a graph thread that is paused on an interrupt and return its new state values.

    The open work items (children included) become cancelled, the pending queue is emptied, the
    outcome is decided from the closed state and the thread is advanced to its end, so a later
    resume finds nothing to continue. A thread that is not paused is left alone: a running graph
    follows run.json at its next superstep.

    Args:
        session: The open service Session (graph and config).
        actor_id: The cancelling actor's id.
        now: Cancellation time.

    Returns:
        dict[str, Any]: The state values after the call (unchanged when not paused).
    """
    snapshot = await session.graph.aget_state(session.config)
    values = dict(snapshot.values)
    paused = any(getattr(task, "interrupts", ()) for task in snapshot.tasks)
    if not paused or not values.get("task"):
        return values
    changed = _cancelled_items(values, actor_id, now)
    closed = {**values, "work_items": {**values["work_items"], **changed},
              "halt_reason": "cancelled"}
    update = {"work_items": changed,
              "status": RunStatus.CANCELLED, "halt_reason": "cancelled", "interaction_queue": [],
              "outcome": decide_outcome(cast(KernelState, closed)),
              "state_revision": int(values.get("state_revision", 0)) + 1}
    await session.graph.aupdate_state(session.config, update, as_node="finalize")
    return dict((await session.graph.aget_state(session.config)).values)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 14:00 [python-coder]: Risk 5 verified on LangGraph 1.2.12: `aupdate_state(...,
#   as_node="finalize")` on a thread paused at `await_interaction` drops the interrupt (no next
#   node, no pending task), applies the reducers, and a later `Command(resume=...)` returns the
#   cancelled state without running a node. The kernel still keeps run.json authoritative
#   because a graph running in another process cannot be safely updated from here.
#   (#KernelBootstrapV0/P9)
# - 2026-10-01 14:00 [python-coder]: `run.cancelled` uses the reserved sequence range instead of
#   the graph's next number: the graph numbers events inside its reducer from the length of its
#   own list, so a service-side `max(seq)+1` could be taken again by the running graph and, with
#   first-write-wins, silently drop one of the two events. (#KernelBootstrapV0/P9)
# - 2026-10-01 14:00 [python-coder]: The cancel commit bumps `state_revision` in run.json: a
#   compare-and-update keyed on that revision is the only staleness signal the store offers, so
#   a writer holding the pre-cancel record must fail its compare and re-read.
#   (#KernelBootstrapV0/P9)
# ====================================================================
