"""
MODULE: tests.kernel.capabilities.host_support
GOAL: Builders for the host-operation tests: a compiled packet, an accepted submission and the
    HostConversion a capability converts, plus request and host-output payload builders (including
    outputs that lie about verification, hashes and approval).
BUSINESS CONTEXT: Conversion rules are about what a host may claim; each test states the claim as
    the raw JSON a host would send and asserts what the kernel kept, so no test reads source.
ARCHITECTURE: Real contract models only. Packets come from the real compiler, so the fingerprint
    and template line a conversion reads are the ones a graph run would produce.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from kernel.capabilities.host import HostConversion, TaskInputs, compiler_for, host_operation
from kernel.contracts import (
    Actor,
    ActorKind,
    CapabilityResult,
    HostWorkRequest,
    InteractionSubmission,
    Usage,
    content_hash,
    evidence_id,
    new_id,
    schema_ids,
    utc_now,
)
from kernel.contracts.evidence import EvidenceInput
from kernel.interaction.packets import FORBIDDEN_HOST_OPERATIONS
from kernel.interaction.results import evidence_from_submission
from tests.kernel.capabilities.support import invocation

NEED = {"id": "need-1", "category": "prior_decisions",
        "question": "Which store does the cache use?"}
OPTIONS_REQUEST = {"problem": "Where should the cache live?", "max_options": 2,
                   "propose_criteria": True}
SYNTHESIS_REQUEST = {"operation": "synthesize_evidence", "question": "What must the cache do?",
                     "evidence_ids": [], "limits": {"max_findings": 2}}
RESEARCH_REQUEST = {"need": NEED}
QUESTION_REQUEST = {"question": "Which store?", "free_text_allowed": False,
                    "choices": [{"id": "sqlite", "label": "SQLite", "consequences": "One file."},
                                {"id": "files", "label": "Plain files"}]}
REQUESTS: dict[str, dict[str, Any]] = {"host.generate_options": OPTIONS_REQUEST, "host.synthesize": SYNTHESIS_REQUEST,
            "host.research": RESEARCH_REQUEST, "host.formulate_question": QUESTION_REQUEST}
REQUESTS["host.query_build"] = {"question":"Which tests cover a component?",
    "repository_id":"repo","source_sha":"a"*40,"generation_id":"g1",
    "component_ids":["component"],"need_id":"need.tests","attempt_id":"attempt1"}
REQUESTS["host.retrieval_needs"] = {"original_question": "Which tests cover CMP-1?",
    "catalog": {"entity_types": {"test": "A test case."}, "target_ids": {"CMP-1": "A component."},
                "required_fields": {"name": "The test name."},
                "document_types": {"source": "A source file."},
                "relationships": {"covers": "A test covers a component."}}}
# Operations the code table binds but config/capability_registry.json deliberately omits: the
# retrieval-needs interpreter is exposed only by explicitly supplied experiment registries.
EXPERIMENT_ONLY = frozenset({"host.retrieval_needs"})
FAKE_HASH = "f" * 64
ANSWER_AFTER = timedelta(milliseconds=1500)
SCHEMAS = {
    "host.retrieval_needs": (schema_ids.RETRIEVAL_NEEDS_REQUEST,
                             schema_ids.RETRIEVAL_NEEDS_OUTPUT),
    "host.query_build": (schema_ids.QUERY_BUILD_REQUEST,schema_ids.QUERY_CANDIDATE),
    "host.generate_options": (schema_ids.OPTIONS_REQUEST, schema_ids.OPTIONS),
    "host.synthesize": (schema_ids.SYNTHESIS_REQUEST, schema_ids.FINDINGS),
    "host.research": (schema_ids.RETRIEVAL_REQUEST, schema_ids.EVIDENCE_BUNDLE),
    "host.formulate_question": (schema_ids.HUMAN_QUESTION_REQUEST,
                                schema_ids.HUMAN_QUESTION_REQUEST),
}


def option(option_id: str = "opt-a", **over: Any) -> dict[str, Any]:
    """Return a proposed option as JSON (overrides replace fields)."""
    return {"id": option_id, "title": f"Option {option_id}", "proposal_status": "proposed",
            "approval_status": "proposed", **over}


def criterion(criterion_id: str = "crit-a", **over: Any) -> dict[str, Any]:
    """Return a proposed criterion as JSON (overrides replace fields)."""
    return {"id": criterion_id, "question": "Does it survive restarts?",
            "proposal_status": "proposed", "approval_status": "proposed", **over}


def evidence_json(locator: str, excerpt: str, *, digest: str | None = None, **over: Any
                  ) -> dict[str, Any]:
    """Return inline bundle evidence as a host could send it, claiming to be source verified."""
    digest = digest or content_hash(excerpt)
    body = {"id": evidence_id(locator, digest), "category": "task_context",
            "semantic_type": "repository_fact", "excerpt": excerpt,
            "source": {"id": "repo.decisions", "kind": "repository_file", "locator": locator,
                       "source_version": {"commit": "deadbeef1", "dirty": False}},
            "content_hash": digest, "provenance": {"producer": "host"},
            "verification": "source_verified"}
    return {**body, **over}


def finding_json(claim: str = "The cache must survive restarts.", **over: Any) -> dict[str, Any]:
    """Return a finding as JSON claiming to be a source fact."""
    return {"id": new_id("find"), "claim": claim, "kind": "source_fact", "producer": "host",
            "supporting_evidence_ids": [], **over}


def make_packet(capability_id: str, inv: Any, out_schema: str, created: Any) -> HostWorkRequest:
    """Return the packet the real compiler builds for the invocation."""
    op = compiler_for(capability_id)
    compiled = op.compile(TaskInputs(
        capability_id=capability_id, operation=op.operation, goal="goal",
        payload=inv.input_payload, allowed_operations=(op.operation,),
        forbidden_operations=tuple(FORBIDDEN_HOST_OPERATIONS), output_schema_id=out_schema))
    return HostWorkRequest(
        id=new_id("int"), created_at=created, updated_at=created, work_item_id=inv.work_item_id,
        invocation_id=inv.id, operation=op.operation, goal=compiled.statement,
        allowed_operations=[op.operation], forbidden_operations=list(FORBIDDEN_HOST_OPERATIONS),
        output_schema_id=out_schema,
        output_requirements=[*compiled.requirements, compiled.compiled_by_line], state_revision=1)


def conversion(capability_id: str, request: dict[str, Any], response: dict[str, Any], *,
               usage: list[Usage] | None = None, known: set[str] | None = None,
               new_evidence: list[dict[str, Any]] | None = None) -> HostConversion:
    """Return the HostConversion of an accepted host submission answering `request`."""
    request_schema, out_schema = SCHEMAS[capability_id]
    inv = invocation(capability_id, request_schema, request)
    created = utc_now()
    packet = make_packet(capability_id, inv, out_schema, created)
    submission = InteractionSubmission(
        run_id=new_id("run"), interaction_id=packet.id, expected_state_revision=1,
        actor=Actor(id="host-1", kind=ActorKind.HOST), response_schema_id=out_schema,
        response=response, usage=usage or [],
        new_evidence=[EvidenceInput.model_validate(e) for e in new_evidence or []])
    return HostConversion(
        packet=packet, submission=submission, invocation=inv, now=created + ANSWER_AFTER,
        extra_evidence=tuple(evidence_from_submission(packet, submission, created + ANSWER_AFTER)),
        known_evidence_ids=None if known is None else frozenset(known))


def convert(capability_id: str, request: dict[str, Any], response: dict[str, Any], **kwargs: Any
            ) -> CapabilityResult:
    """Convert a host answer with the capability's operation."""
    op = host_operation(capability_id)
    assert op is not None
    return op.convert(conversion(capability_id, request, response, **kwargs))
