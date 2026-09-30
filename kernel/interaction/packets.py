"""
MODULE: kernel.interaction.packets
GOAL: Build the host-work and human-question packets the kernel hands to a client (Rev 3 sections
    7.8, 11.3 and 11.6): bounded task statement, allowed and forbidden operations, input
    artifacts, output schema, trace context, and the redaction applied before a packet leaves.
BUSINESS CONTEXT: The host is cooperative, not sandboxed (section 11.5): the packet is the whole
    contract, so it must say exactly what may be done, name only registered output schemas, and
    never carry a secret. A human question must say why evidence could not answer it.
ARCHITECTURE: Pure builders over plain state mappings (no scheduler imports, so the scheduler
    can import this package). Only the input-artifact write touches a port, and it is
    deterministic per interaction id, so a re-executed node rewrites the same file.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from kernel.contracts import (
    CapabilityInvocation,
    HostWorkRequest,
    HumanQuestion,
    TraceContext,
    WorkItem,
    new_id,
    schema_ids,
)
from kernel.contracts.interaction import ContextLimits, Rejection
from kernel.contracts.payloads import HumanQuestionRequestPayload
from kernel.contracts.schema_catalog import json_schema_for
from kernel.observability.redaction import Redactor
from kernel.persistence.base import ArtifactStorePort

logger = logging.getLogger(__name__)

#: Operations a host may never perform, whatever the capability allows (spec 11.3 and 13.3).
FORBIDDEN_HOST_OPERATIONS = ("edit_repository", "approve_policy", "change_permissions",
                             "choose_next_step", "run_other_leafcutter_commands")
MAX_TASK_STATEMENT_CHARS = 2000
DEFAULT_WHY_HUMAN = "The available evidence and routing could not settle this question."
_TRUNCATED = " ...[truncated]"


def bounded(text: str, limit: int = MAX_TASK_STATEMENT_CHARS) -> str:
    """Return text cut to limit characters, with a marker when it was cut."""
    if len(text) <= limit:
        return text
    return text[:max(0, limit - len(_TRUNCATED))] + _TRUNCATED


def current_invocation(state: Mapping[str, Any], item: WorkItem) -> CapabilityInvocation | None:
    """Return the invocation of the item's current attempt, if any."""
    for invocation in state.get("invocations", {}).values():
        if invocation.work_item_id == item.id and invocation.attempt == item.attempts:
            return invocation
    return None


def input_evidence_ids(state: Mapping[str, Any], request: Any) -> list[str]:
    """Return the known evidence ids a request cites: its context refs and payload references."""
    payload = request.payload if isinstance(request.payload, Mapping) else {}
    cited = [*request.context_refs, *payload.get("evidence_ids", []),
             *payload.get("existing_evidence_ids", [])]
    known = state.get("evidence", {})
    return [i for i in dict.fromkeys(cited) if i in known]


def build_human_question(state: Mapping[str, Any], item: WorkItem, revision: int,
                         now: datetime) -> HumanQuestion:
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
        relevant_evidence_ids=input_evidence_ids(state, request),
        choices=body.choices, free_text_allowed=body.free_text_allowed,
        structured_allowed=body.structured_allowed,
        why_research_cannot_settle=body.why_research_cannot_settle or DEFAULT_WHY_HUMAN,
        state_revision=revision)


_PROPOSED_ONLY = {"type": "object", "required": ["proposal_status", "approval_status"],
                  "properties": {"proposal_status": {"const": "proposed"},
                                 "approval_status": {"const": "proposed"}}}
OPTIONS_REQUIREMENT = ("Every option and every proposed criterion must set proposal_status and "
                       "approval_status to 'proposed'; a human approves them later, so never "
                       "set 'approved' or approved_by.")


def tightened_schema(schema_id: str, schema: dict[str, Any]) -> dict[str, Any]:
    """Return the output JSON Schema with rules pydantic cannot express written into it.

    Generated options and criteria (options.v1) are proposals: the schema pins both status
    fields to `proposed` so an honest host can comply without reading kernel code.
    """
    if schema_id != schema_ids.OPTIONS:
        return schema
    tight = json.loads(json.dumps(schema))
    for name in ("options", "proposed_criteria"):
        prop = tight.get("properties", {}).get(name)
        if prop and "items" in prop:
            prop["items"] = {"allOf": [prop["items"], _PROPOSED_ONLY]}
    return tight


def build_host_request(state: Mapping[str, Any], item: WorkItem, revision: int, now: datetime,
                       *, max_input_chars: int | None = None) -> HostWorkRequest:
    """Build the HostWorkRequest for a host_handoff binding (exactly one operation)."""
    request = state["requests"][item.request_id]
    descriptor = state["registry"].get(item.binding.capability_id)
    invocation = current_invocation(state, item)
    operations = list(descriptor.operations) if descriptor else []
    return HostWorkRequest(
        id=new_id("int"), created_at=now, updated_at=now, work_item_id=item.id,
        invocation_id=invocation.id if invocation else None,
        operation=operations[0] if operations else item.binding.capability_id,
        goal=bounded(request.goal or request.question or item.binding.capability_id),
        input_evidence_ids=input_evidence_ids(state, request),
        allowed_operations=operations, forbidden_operations=list(FORBIDDEN_HOST_OPERATIONS),
        output_schema_id=request.requested_output_schema,
        output_json_schema=tightened_schema(request.requested_output_schema,
                                            json_schema_for(request.requested_output_schema)),
        output_requirements=([OPTIONS_REQUIREMENT]
                             if request.requested_output_schema == schema_ids.OPTIONS else []),
        context_limits=ContextLimits(max_input_chars=max_input_chars),
        trace_context=invocation.trace if invocation else TraceContext(),
        state_revision=revision, attempt=item.attempts)


def write_input_artifact(artifacts: ArtifactStorePort, redactor: Redactor, run_id: str,
                         state: Mapping[str, Any], packet: HostWorkRequest) -> HostWorkRequest:
    """Write the redacted input the host may read and return the packet referencing it.

    The artifact holds the invocation's request payload and the cited evidence excerpts; it is
    named after the interaction id, so a re-executed node rewrites identical content.
    """
    invocation = current_invocation(state, state["work_items"][packet.work_item_id])
    evidence = [{"id": e.id, "category": e.category.value, "locator": e.source.locator,
                 "source": e.source.id, "excerpt": e.excerpt}
                for i in packet.input_evidence_ids if (e := state["evidence"].get(i))]
    body = redactor.mask({
        "interaction_id": packet.id, "operation": packet.operation,
        "request_schema": invocation.input_payload_schema if invocation else None,
        "request": dict(invocation.input_payload) if invocation else {}, "evidence": evidence})
    try:
        ref = artifacts.write_artifact(run_id, f"input-{packet.id}.json",
                                       json.dumps(body, indent=2, sort_keys=True) + "\n")
    except OSError:
        logger.exception("could not write the input artifact of %s", packet.id)
        raise
    return packet.model_copy(update={"input_artifact_refs": [ref.path or ref.ref]})


def redact_packet(packet: HostWorkRequest | HumanQuestion, redactor: Redactor
                  ) -> HostWorkRequest | HumanQuestion:
    """Return the packet with every free-text field masked (ids and schemas stay untouched)."""
    mask = redactor.mask_text
    if isinstance(packet, HumanQuestion):
        choices = [c.model_copy(update={"label": mask(c.label),
                                        "consequences": mask(c.consequences)})
                   for c in packet.choices]
        return packet.model_copy(update={
            "question": mask(packet.question), "choices": choices,
            "why_research_cannot_settle": mask(packet.why_research_cannot_settle)})
    rejections = [Rejection(code=r.code, message=mask(r.message)) for r in packet.rejections]
    return packet.model_copy(update={"goal": mask(packet.goal), "rejections": rejections})


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:40 [python-coder]: Host input travels as a redacted artifact referenced by
#   absolute path (design part 5), because a packet carrying only evidence ids gives the host
#   nothing to read. (#KernelBootstrapV0/P6)
# - 2026-09-30 23:40 [python-coder]: Only free-text fields are masked: masking ids, the JSON
#   schema or patterns would corrupt them, and the entropy rule would hit the schema patterns.
#   (#KernelBootstrapV0/P6)
# ====================================================================
