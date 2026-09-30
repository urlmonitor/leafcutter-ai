"""
MODULE: kernel.scheduler.nodes_interaction
GOAL: The `open_interactions` and `await_interaction` nodes (first versions): create host-work and
    human-question packets, queue them, pause the graph with LangGraph `interrupt()` and turn a
    valid submission into a CapabilityResult for the owning work item.
BUSINESS CONTEXT: Host work and human questions are the only places the run waits on someone
    else (Rev 3 section 13.1). Nothing may be written before the interrupt, because LangGraph
    re-executes the node on resume; silence never answers a human question.
ARCHITECTURE: P6 takes this module over (packets, submission ledger, repair tracking); the seam
    is the pair of node functions and the queue/`interactions` state keys. Only the queue head is
    served, so host work is sequential (max_concurrent_host=1).
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt
from pydantic import ValidationError

from kernel.contracts import (
    ActorKind,
    CapabilityInvocation,
    CapabilityResult,
    Evidence,
    EvidenceCategory,
    EvidenceSource,
    HostWorkRequest,
    HumanQuestion,
    InteractionSubmission,
    PayloadValidationError,
    Provenance,
    ResultStatus,
    SemanticContext,
    SemanticType,
    SemanticValidationError,
    SourceKind,
    TraceContext,
    UnknownSchemaError,
    Verification,
    WorkItem,
    content_hash,
    evidence_id,
    new_id,
    schema_ids,
    validate_payload,
    validate_semantics,
)
from kernel.contracts.interaction import Choice
from kernel.contracts.payloads import HumanQuestionRequestPayload
from kernel.contracts.schema_catalog import json_schema_for
from kernel.scheduler.context import KernelRuntime
from kernel.scheduler.merge import Draft
from kernel.scheduler.nodes_route import HUMAN_CAPABILITY
from kernel.scheduler.state import KernelState, new_event

logger = logging.getLogger(__name__)
FORBIDDEN_HOST_OPERATIONS = ("edit_repository", "approve_policy", "change_permissions",
                             "choose_next_step", "run_other_leafcutter_commands")


def current_invocation(state: KernelState, item: WorkItem) -> CapabilityInvocation | None:
    """Return the invocation of the item's current attempt, if any."""
    for invocation in state.get("invocations", {}).values():
        if invocation.work_item_id == item.id and invocation.attempt == item.attempts:
            return invocation
    return None


def build_human_question(state: KernelState, item: WorkItem, revision: int, now: Any
                         ) -> HumanQuestion:
    """Build the HumanQuestion for a human request (template wording, no model text)."""
    request = state["requests"][item.request_id]
    if request.payload_schema == schema_ids.HUMAN_QUESTION_REQUEST:
        body = HumanQuestionRequestPayload.model_validate(request.payload)
    else:
        body = HumanQuestionRequestPayload(question=request.question or request.goal or "?",
                                           free_text_allowed=True)
    return HumanQuestion(
        id=new_id("int"), created_at=now, updated_at=now, work_item_id=item.id,
        decision_id=body.decision_id, subject_ids=body.subject_ids, question=body.question,
        relevant_evidence_ids=[i for i in request.context_refs if i in state.get("evidence", {})],
        choices=body.choices, free_text_allowed=body.free_text_allowed,
        why_research_cannot_settle=body.why_research_cannot_settle, state_revision=revision)


def build_host_request(state: KernelState, item: WorkItem, revision: int, now: Any
                       ) -> HostWorkRequest:
    """Build the HostWorkRequest for a host_handoff binding (exactly one operation)."""
    request = state["requests"][item.request_id]
    descriptor = state["registry"].get(item.binding.capability_id)
    invocation = current_invocation(state, item)
    operations = list(descriptor.operations) if descriptor else []
    return HostWorkRequest(
        id=new_id("int"), created_at=now, updated_at=now, work_item_id=item.id,
        invocation_id=invocation.id if invocation else None,
        operation=operations[0] if operations else item.binding.capability_id,
        goal=request.goal or request.question or "",
        input_evidence_ids=[i for i in request.context_refs if i in state.get("evidence", {})],
        allowed_operations=operations, forbidden_operations=list(FORBIDDEN_HOST_OPERATIONS),
        output_schema_id=request.requested_output_schema,
        output_json_schema=json_schema_for(request.requested_output_schema),
        trace_context=invocation.trace if invocation else TraceContext(),
        state_revision=revision, attempt=item.attempts)


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
        packet = (build_human_question if human else build_host_request)(
            state, item, revision, draft.now)
        try:
            ctx.run_store.save_interaction(state["run_id"], packet)
        except OSError:
            logger.exception("could not persist interaction %s", packet.id)
            raise
        packets[packet.id] = packet
        queue.append(packet.id)
        draft.put_item(item, interaction_ref=packet.id)
        draft.emit("interaction.opened", "human" if human else "host", work_item_id=item.id,
                   interaction_id=packet.id)
    update = draft.update(include_budgets=False)
    update.update(interactions=packets, interaction_queue=queue)
    return update


def _rejection(packet: HostWorkRequest | HumanQuestion, raw: object, known_evidence: set[str]
               ) -> tuple[str, InteractionSubmission | None]:
    """Re-validate a resume value; return (problem text, submission) - problem empty if valid."""
    try:
        submission = InteractionSubmission.model_validate(raw)
    except ValidationError as exc:
        return f"schema_invalid: {exc.error_count()} errors", None
    human = isinstance(packet, HumanQuestion)
    expected_schema = schema_ids.HUMAN_ANSWER if human else packet.output_schema_id
    expected_actor = ActorKind.HUMAN if human else ActorKind.HOST
    if submission.interaction_id != packet.id:
        return "stale_submission: not the pending interaction", None
    if submission.response_schema_id != expected_schema or submission.actor.kind is not expected_actor:
        return "kind_mismatch: wrong response schema or actor kind", None
    context = SemanticContext(
        known_evidence_ids=frozenset(known_evidence),
        offered_choice_ids=frozenset(c.id for c in packet.choices) if human else None)
    try:
        payload = validate_payload(expected_schema, dict(submission.response))
        validate_semantics(expected_schema, payload, context)
    except (PayloadValidationError, SemanticValidationError, UnknownSchemaError) as exc:
        return f"semantic_invalid: {exc}", None
    return "", submission


def _answer_text(packet: HumanQuestion, response: dict) -> str:
    """Return the evidence text of a human answer (free text, or the chosen label)."""
    if response.get("free_text"):
        return str(response["free_text"])
    chosen: Choice | None = next((c for c in packet.choices if c.id == response.get("choice_id")),
                                 None)
    return f"{chosen.label}" if chosen else f"choice {response.get('choice_id')}"


def _evidence(packet: HostWorkRequest | HumanQuestion, submission: InteractionSubmission,
              now: Any) -> list[Evidence]:
    """Turn the answer and any new evidence of a submission into Evidence items."""
    human = isinstance(packet, HumanQuestion)
    texts = [(f"human:{packet.id}", _answer_text(packet, dict(submission.response)))] if human \
        else []
    texts += [(e.locator or f"{submission.actor.kind.value}:{packet.id}#{i}", e.excerpt)
              for i, e in enumerate(submission.new_evidence)]
    out: list[Evidence] = []
    for locator, excerpt in texts:
        digest = content_hash(excerpt)
        out.append(Evidence(
            id=evidence_id(locator, digest), created_at=now, updated_at=now,
            category=EvidenceCategory.TASK_CONTEXT,
            semantic_type=SemanticType.HUMAN_INPUT if human else SemanticType.REPOSITORY_FACT,
            excerpt=excerpt,
            source=EvidenceSource(id="human" if human else "host", locator=locator,
                                  kind=SourceKind.HUMAN if human else SourceKind.HOST_RESEARCH),
            content_hash=digest,
            provenance=Provenance(producer="kernel.interaction", actor=submission.actor.id,
                                  relayed_by=submission.relayed_by),
            verification=Verification.UNVERIFIED if human else Verification.HOST_REPORTED))
    return out


async def await_interaction(state: KernelState, runtime: Runtime[KernelRuntime]
                            ) -> dict[str, Any] | Command:
    """Pause on the queue head; on a valid answer emit its CapabilityResult and dequeue it."""
    queue = state["interaction_queue"]
    packet = state["interactions"][queue[0]]
    raw = interrupt(packet.model_dump(mode="json"))
    ctx = runtime.context
    now = ctx.clock()
    problem, submission = _rejection(packet, raw, set(state.get("evidence", {})))
    if submission is None:
        event = new_event(state["run_id"], now, "interaction.rejected", problem,
                          interaction_id=packet.id)
        return Command(goto="await_interaction", update={"events": [event]})
    item = state["work_items"][packet.work_item_id]
    invocation = current_invocation(state, item)
    result = CapabilityResult(
        invocation_id=invocation.id if invocation else packet.id, work_item_id=item.id,
        status=ResultStatus.COMPLETED,
        output_schema_id=submission.response_schema_id,
        output_payload=dict(submission.response), evidence=_evidence(packet, submission, now),
        usage=list(submission.usage))
    event = new_event(state["run_id"], now, "interaction.answered", submission.actor.kind.value,
                      work_item_id=item.id, interaction_id=packet.id)
    return {"results": {result.invocation_id: result}, "interaction_queue": queue[1:],
            "events": [event]}


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:30 [python-coder]: `await_interaction` is not wrapped by sequential_node: its
#   tracer span must open only after resume (nothing before interrupt, design risk 6).
#   (#KernelBootstrapV0/P4)
# - 2026-09-30 22:30 [python-coder]: `open_interactions` is not wrapped either: it runs beside
#   the Send workers and the wrapper writes `budgets` (replace reducer); its time is negligible.
#   (#KernelBootstrapV0/P4)
# ====================================================================
