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

from kernel.enrichment_projection import context_payload

import json
import logging
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any, overload

from kernel.capabilities.host import TaskInputs, compiler_for, parse_compiled_by
from kernel.capabilities.host.spec import MAX_TASK_STATEMENT_CHARS, bounded
from kernel.contracts import (
    CapabilityInvocation,
    HostWorkRequest,
    HumanQuestion,
    TraceContext,
    WorkItem,
    new_id,
    schema_ids,
)
from kernel.contracts.base import fail
from kernel.contracts.interaction import ContextLimits, Rejection
from kernel.contracts.payloads import HumanQuestionRequestPayload
from kernel.contracts.schema_catalog import json_schema_for
from kernel.observability.redaction import Redactor
from kernel.persistence.base import ArtifactStorePort

logger = logging.getLogger(__name__)

#: Operations a host may never perform, whatever the capability allows (spec 11.3 and 13.3).
FORBIDDEN_HOST_OPERATIONS = ("edit_repository", "approve_policy", "change_permissions",
                             "choose_next_step", "run_other_leafcutter_commands")
DEFAULT_WHY_HUMAN = "The available evidence and routing could not settle this question."
__all__ = ["DEFAULT_WHY_HUMAN", "FORBIDDEN_HOST_OPERATIONS", "MAX_TASK_STATEMENT_CHARS",
           "bounded", "build_host_request", "build_human_question", "current_invocation",
           "input_evidence_ids", "redact_packet", "tightened_schema", "write_input_artifact"]


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


#: Fields the kernel computes for host evidence and findings, so a host schema must not require
#: them (the packet tells the host not to invent them).
_KERNEL_COMPUTED = {"Evidence": ("id", "content_hash"), "Finding": ("id",)}


def _without_required(schema: dict[str, Any], fields: dict[str, tuple[str, ...]]
                      ) -> dict[str, Any]:
    """Return a copy of the schema whose named definitions no longer require the given fields."""
    relaxed = json.loads(json.dumps(schema))
    for name, omitted in fields.items():
        definition = relaxed.get("$defs", {}).get(name)
        if definition and "required" in definition:
            definition["required"] = [r for r in definition["required"] if r not in omitted]
    return relaxed


def tightened_schema(schema_id: str, schema: dict[str, Any]) -> dict[str, Any]:
    """Return the output JSON Schema with rules pydantic cannot express written into it.

    Generated options and criteria (options.v1) are proposals: the schema pins both status
    fields to `proposed` so an honest host can comply without reading kernel code. A host
    evidence bundle (evidence_bundle.v1) need not carry the ids and content hashes the kernel
    computes itself, matching the packet's instruction not to invent them.
    """
    if schema_id == schema_ids.EVIDENCE_BUNDLE:
        return _without_required(schema, _KERNEL_COMPUTED)
    if schema_id != schema_ids.OPTIONS:
        return schema
    tight = json.loads(json.dumps(schema))
    for name in ("options", "proposed_criteria"):
        prop = tight.get("properties", {}).get(name)
        if prop and "items" in prop:
            prop["items"] = {"allOf": [prop["items"], _PROPOSED_ONLY]}
    return tight


def build_host_request(state: Mapping[str, Any], item: WorkItem, revision: int, now: datetime,
                       *, max_input_chars: int | None = None,
                       mask: Callable[[str], str] | None = None) -> HostWorkRequest:
    """Build the HostWorkRequest for a host_handoff binding (exactly one operation).

    The task statement and output requirements are compiled by the capability's host operation
    (ADR-052): deterministic text from the request payload, schema, operations, cited evidence
    and limits, redacted with `mask` and fingerprinted; the last requirement records template
    and fingerprint.
    """
    request = state["requests"][item.request_id]
    if item.binding is None:
        fail("a host packet needs a work item with a binding")
    capability_id = item.binding.capability_id
    descriptor = state["registry"].get(capability_id)
    invocation = current_invocation(state, item)
    operations = list(descriptor.operations) if descriptor else []
    evidence_ids = input_evidence_ids(state, request)
    operation = operations[0] if operations else capability_id
    compiled = compiler_for(capability_id).compile(TaskInputs(
        capability_id=capability_id, operation=operation,
        goal=request.goal or request.question or capability_id,
        payload=request.payload if isinstance(request.payload, Mapping) else {},
        allowed_operations=tuple(operations),
        forbidden_operations=tuple(FORBIDDEN_HOST_OPERATIONS),
        output_schema_id=request.requested_output_schema, evidence_ids=tuple(evidence_ids),
        max_input_chars=max_input_chars), mask)
    return HostWorkRequest(
        id=new_id("int"), created_at=now, updated_at=now, work_item_id=item.id,
        invocation_id=invocation.id if invocation else None, operation=operation,
        goal=compiled.statement, input_evidence_ids=evidence_ids,
        allowed_operations=operations, forbidden_operations=list(FORBIDDEN_HOST_OPERATIONS),
        output_schema_id=request.requested_output_schema,
        output_json_schema=tightened_schema(request.requested_output_schema,
                                            json_schema_for(request.requested_output_schema)),
        output_requirements=[*compiled.requirements, compiled.compiled_by_line],
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
    ref = parse_compiled_by(packet.output_requirements)
    body = redactor.mask({
        "interaction_id": packet.id, "operation": packet.operation,
        "task_template": f"{ref.template_id}@{ref.template_version}" if ref else None,
        "prompt_fingerprint": ref.fingerprint if ref else None,
        "request_schema": invocation.input_payload_schema if invocation else None,
        "request": dict(invocation.input_payload) if invocation else {}, "evidence": evidence,
        "context_enrichment": context_payload(state["context_enrichment"])
        if state.get("context_enrichment") is not None else None})
    try:
        written = artifacts.write_artifact(run_id, f"input-{packet.id}.json",
                                           json.dumps(body, indent=2, sort_keys=True) + "\n")
    except OSError:
        logger.exception("could not write the input artifact of %s", packet.id)
        raise
    return packet.model_copy(update={"input_artifact_refs": [written.path or written.ref]})


@overload
def redact_packet(packet: HostWorkRequest, redactor: Redactor) -> HostWorkRequest: ...


@overload
def redact_packet(packet: HumanQuestion, redactor: Redactor) -> HumanQuestion: ...


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
# - 2026-10-02 [python-coder]: mypy: redact_packet is overloaded so a host packet stays a host packet; a binding-less item fails clearly (#KernelBootstrapV0/GROUND)
# - 2026-10-01 23:00 [python-coder]: The host evidence schema no longer requires `id` and
#   `content_hash`: the instructions say not to invent them and the kernel computes both, so the
#   schema and the instructions must agree. (#KernelBootstrapV0/GROUND)
# - 2026-09-30 23:40 [python-coder]: Host input travels as a redacted artifact referenced by
#   absolute path (design part 5), because a packet carrying only evidence ids gives the host
#   nothing to read. (#KernelBootstrapV0/P6)
# - 2026-10-01 11:00 [python-coder]: The packet goal and requirements are now compiled by the
#   capability's host operation (kernel.capabilities.host) instead of being copied from the
#   request; `bounded` and the statement cap moved there and are re-exported here.
#   (#KernelBootstrapV0/P8)
# - 2026-09-30 23:40 [python-coder]: Only free-text fields are masked: masking ids, the JSON
#   schema or patterns would corrupt them, and the entropy rule would hit the schema patterns.
#   (#KernelBootstrapV0/P6)
# ====================================================================
