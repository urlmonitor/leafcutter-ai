"""
MODULE: kernel.scheduler.nodes_interaction
GOAL: The `open_interactions` and `await_interaction` nodes: create, redact and persist host-work
    and human-question packets, pause the graph with LangGraph `interrupt()`, re-validate the
    resume value, and turn a valid submission into a CapabilityResult for the owning work item.
BUSINESS CONTEXT: Host work and human questions are the only places the run waits on someone
    else (Rev 3 section 13.1). Nothing may be written before the interrupt, because LangGraph
    re-executes the node on resume; silence never answers a human question, and invalid host
    output is repaired a bounded number of times and then fails the item.
ARCHITECTURE: Packet building, validation and result conversion live in `kernel.interaction`;
    this module is the graph seam. Only the queue head is served, so host work is sequential
    (max_concurrent_host=1). The service validates and ledgers a submission before resuming; the
    node validates again with the same function, which makes the graph safe for any resumer.
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.runtime import Runtime
from langgraph.types import interrupt

from kernel.capabilities.host import emit_host_telemetry
from kernel.contracts import FallbackOutcome, HostWorkRequest, HumanQuestion, RunEvent
from kernel.contracts.interaction import Rejection
from kernel.interaction.packets import (
    build_host_request,
    build_human_question,
    current_invocation,
    redact_packet,
    write_input_artifact,
)
from kernel.interaction.results import repair_exhausted_result, result_from_submission
from kernel.interaction.submissions import Verdict, check_submission
from kernel.observability.redaction import Redactor
from kernel.scheduler.context import KernelRuntime, run_corr
from kernel.scheduler.merge import Draft
from kernel.scheduler.nodes_gaps import record_host_only
from kernel.scheduler.nodes_route import HUMAN_CAPABILITY
from kernel.scheduler.state import KernelState, new_event

logger = logging.getLogger(__name__)
MAX_REJECTION_MESSAGE_CHARS = 1500


def _redactor(ctx: KernelRuntime) -> Redactor:
    """Return the runtime redactor, or a pattern-only one from the data policy."""
    return ctx.redactor or Redactor({}, ctx.config.data_policy)


def _persist(ctx: KernelRuntime, run_id: str, packet: HostWorkRequest | HumanQuestion) -> None:
    """Save the packet exactly as it will be delivered."""
    try:
        ctx.run_store.save_interaction(run_id, packet)
    except OSError:
        logger.exception("could not persist interaction %s", packet.id)
        raise


def _packet_for(state: KernelState, ctx: KernelRuntime, item: Any, revision: int, now: Any,
                human: bool) -> HostWorkRequest | HumanQuestion:
    """Build, attach the input artifact to, and redact the packet of one interaction item."""
    redactor = _redactor(ctx)
    if human:
        return redact_packet(build_human_question(state, item, revision, now), redactor)
    packet = build_host_request(state, item, revision, now,
                                max_input_chars=ctx.config.host.max_input_chars,
                                mask=redactor.mask_text)
    packet = write_input_artifact(
        ctx.artifacts, redactor, state["run_id"], state, packet,
        send_repo_excerpts=ctx.config.data_policy.send_repo_excerpts_to_jev)
    return redact_packet(packet, redactor)


async def open_interactions(state: KernelState, runtime: Runtime[KernelRuntime]
                            ) -> dict[str, Any]:
    """Create and persist a packet per interaction item and append it to the queue."""
    ctx = runtime.context
    draft = Draft(state, ctx.clock())
    revision = state.get("state_revision", 0)
    packets: dict[str, HostWorkRequest | HumanQuestion] = {}
    queue = list(state.get("interaction_queue", []))
    for item_id in state.get("dispatch", {}).get("interaction", []):
        item = draft.items[item_id]
        human = item.binding is not None and item.binding.capability_id == HUMAN_CAPABILITY
        packet = _packet_for(state, ctx, item, revision, draft.now, human)
        _persist(ctx, state["run_id"], packet)
        packets[packet.id] = packet
        queue.append(packet.id)
        draft.put_item(item, interaction_ref=packet.id)
        draft.emit("interaction.opened", "human" if human else "host", work_item_id=item.id,
                   interaction_id=packet.id)
        ctx.tracer.event("interaction.opened", run_corr(
            state, work_item_id=item.id, interaction_id=packet.id),
            payload={"kind": "human" if human else "host", "state_revision": revision})
    update = draft.update(include_budgets=False)
    update.update(interactions=packets, interaction_queue=queue)
    return update


def _rejection_text(verdict: Verdict) -> str:
    """Return the message shown to the host for repair: the reason plus the validator detail."""
    extra = verdict.details.get("detail") or "; ".join(verdict.details.get("violations", []))
    text = f"{verdict.message}: {extra}" if extra else verdict.message
    return text[:MAX_REJECTION_MESSAGE_CHARS]


def _counted(ctx: KernelRuntime, run_id: str, packet: HostWorkRequest, verdict: Verdict
             ) -> HostWorkRequest:
    """Return the packet with this invalid submission recorded as a repair, redacted and saved."""
    code = verdict.code.value if verdict.code else "invalid"
    counted = packet.model_copy(update={"rejections": [
        *packet.rejections, Rejection(code=code, message=_rejection_text(verdict))]})
    counted = redact_packet(counted, _redactor(ctx))
    _persist(ctx, run_id, counted)
    return counted


async def await_interaction(state: KernelState, runtime: Runtime[KernelRuntime]
                            ) -> dict[str, Any]:
    """Pause on the queue head; on a valid answer emit its CapabilityResult and dequeue it.

    A rejected submission keeps the node waiting *inside* the node (a second `interrupt()`):
    returning `Command(goto=...)` would also fire the static edge to `integrate` and run the
    scheduler beside the pending interrupt. LangGraph replays the earlier resume values of this
    node in order, so the loop is deterministic and the repair count survives a restart.
    """
    queue = state["interaction_queue"]
    packet = state["interactions"][queue[0]]
    ctx, events = runtime.context, []
    while True:
        raw = interrupt(packet.model_dump(mode="json"))
        now = ctx.clock()
        verdict = check_submission(raw, state)
        if verdict.ok and verdict.submission is not None:
            break
        code = verdict.code.value if verdict.code else "invalid"
        events.append(new_event(state["run_id"], now, "interaction.rejected", code,
                                interaction_id=packet.id))
        if not (verdict.repairable and isinstance(packet, HostWorkRequest)):
            continue
        packet = _counted(ctx, state["run_id"], packet, verdict)
        if len(packet.rejections) > ctx.config.host.max_repair_attempts:
            return _exhausted(state, ctx, packet, code, events, now)
    item = state["work_items"][packet.work_item_id]
    result = result_from_submission(packet, verdict.submission,
                                    current_invocation(state, item), now,
                                    known_evidence_ids=state.get("evidence", {}).keys())
    corr = run_corr(state, work_item_id=item.id, interaction_id=packet.id)
    if isinstance(packet, HostWorkRequest):
        emit_host_telemetry(ctx.tracer, corr, packet, verdict.submission, result, now)
    ctx.tracer.event("submission.accepted", corr,
        payload={"actor_kind": verdict.submission.actor.kind.value,
                 "rejections_before": len(packet.rejections) if isinstance(
                     packet, HostWorkRequest) else 0})
    events.append(new_event(state["run_id"], now, "interaction.answered",
                            verdict.submission.actor.kind.value, work_item_id=item.id,
                            interaction_id=packet.id))
    update: dict[str, Any] = {"results": {result.invocation_id: result},
                              "interaction_queue": queue[1:], "events": events}
    _add_host_only(update, state, ctx, packet, item, FallbackOutcome.HOST_COMPLETED)
    return update


def _add_host_only(update: dict[str, Any], state: KernelState, ctx: KernelRuntime, packet: Any,
                   item: Any, outcome: FallbackOutcome) -> None:
    """Add the `host_only` gap observation of an executed host operation to the node update.

    Runs only after the interrupt resumed (the node re-executes on resume) and only for host
    packets; `settle_gap_outcomes` skips items that already have a `gap.recorded` event.
    """
    if not isinstance(packet, HostWorkRequest):
        return
    rec = record_host_only(state, ctx, item, outcome)
    if rec:
        gap, gap_events = rec
        update["events"] = [*update["events"], *gap_events]
        update["gaps"] = {gap.id: gap}


def _exhausted(state: KernelState, ctx: KernelRuntime, packet: HostWorkRequest, code: str,
               events: list[RunEvent], now: Any) -> dict[str, Any]:
    """Fail the host item whose repair attempts ran out and dequeue its interaction."""
    item = state["work_items"][packet.work_item_id]
    result = repair_exhausted_result(packet, current_invocation(state, item), code)
    emit_host_telemetry(ctx.tracer, run_corr(state, work_item_id=item.id, interaction_id=packet.id),
                        packet, None, result, now)
    events.append(new_event(state["run_id"], now, "interaction.repair_exhausted", code,
                            work_item_id=item.id, interaction_id=packet.id))
    update: dict[str, Any] = {"results": {result.invocation_id: result}, "events": events,
                              "interactions": {packet.id: packet},
                              "interaction_queue": state["interaction_queue"][1:]}
    _add_host_only(update, state, ctx, packet, item, FallbackOutcome.HOST_FAILED)
    return update


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 17:30 [python-coder]: The `host_only` gap observation is recorded when the host
#   answer (or the exhausted repair budget) is turned into a result, after the interrupt has
#   resumed, so it happens once per operation; `settle_gap_outcomes` skips items that already
#   carry a `gap.recorded` event, which is what keeps a restart from counting twice.
#   (#KernelBootstrapV0/INT2)
# - 2026-10-01 11:10 [python-coder]: A host answer (and an exhausted repair budget) records a
#   `host.<operation>` telemetry event with the packet fingerprint, time to answer and usage;
#   conversion gets the ids of the run's evidence so it can drop citations of evidence that does
#   not exist. (#KernelBootstrapV0/P8)
# - 2026-09-30 22:30 [python-coder]: `await_interaction` is not wrapped by sequential_node: its
#   tracer span must open only after resume (nothing before interrupt, design risk 6).
#   (#KernelBootstrapV0/P4)
# - 2026-09-30 22:30 [python-coder]: `open_interactions` is not wrapped either: it runs beside
#   the Send workers and the wrapper writes `budgets` (replace reducer); its time is negligible.
#   (#KernelBootstrapV0/P4)
# - 2026-09-30 23:59 [python-coder]: The repair counter is the `rejections` list of the packet the
#   node rebuilds from its replayed resume values (checkpointed with the paused task, so it
#   survives a restart); a host gets max_repair_attempts corrections after its first invalid
#   output and the next invalid one fails the item. (#KernelBootstrapV0/P6)
# - 2026-09-30 23:59 [python-coder]: `submission.accepted` is traced after the loop (once, when
#   the node completes) and `submission.rejected` by `submit_interaction`, which sees each
#   submission exactly once; a rejection traced inside the node would repeat on every replay of
#   the loop. (#KernelBootstrapV0/P6)
# - 2026-09-30 23:59 [python-coder]: Rejections loop inside the node instead of returning
#   `Command(goto="await_interaction")`: the goto leaves the static edge to `integrate` active,
#   so integrate and schedule ran beside the pending interrupt and a later valid answer crashed
#   on two writers of `budgets`. (#KernelBootstrapV0/P6)
# - 2026-09-30 23:59 [python-coder]: Every packet is redacted before it is stored in state, so
#   what the checkpoint holds, what `interrupt()` delivers and what the run store keeps are the
#   same masked text. (#KernelBootstrapV0/P6)
# - 2026-10-03 15:10 [python-coder]: Preserve verbatim goals and separate meaning, caller and clarification channels. (#DK-300/entity-context)
# ====================================================================
