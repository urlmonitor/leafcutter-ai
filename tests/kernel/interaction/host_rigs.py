"""
MODULE: tests.kernel.interaction.host_rigs
GOAL: Shared rigs for the host-operation graph tests: one rig per host capability whose root
    waits on a single host child, the canned request payloads and the valid host answers.
BUSINESS CONTEXT: The end-to-end and security tests must drive the same four operations through
    the same graph, so the rigs live in one place and a new host capability is added once.
ARCHITECTURE: Builds on the scheduler Rig; `host_rig` binds a scripted root (waits, then
    completes) and the host capability (answered only through the interaction protocol).
"""

from __future__ import annotations

from typing import Any

from kernel.contracts import RequestKind, RequestProposal
from tests.kernel.capabilities.host_support import (
    NEED,
    REQUESTS,
    SCHEMAS,
    criterion,
    evidence_json,
    finding_json,
    option,
)
from tests.kernel.scheduler.support import Rig, completed, descriptor, two_phase, waiting

__all__ = ["KINDS", "OPERATIONS", "PAYLOADS", "RESPONSES", "host_result", "host_rig"]

KINDS = {"host.generate_options": RequestKind.OPTIONS, "host.synthesize": RequestKind.SYNTHESIS,
         "host.research": RequestKind.EVIDENCE, "host.formulate_question": RequestKind.CAPABILITY,
         "host.query_build": RequestKind.CAPABILITY, "host.retrieval_needs": RequestKind.CAPABILITY}
OPERATIONS = {"host.generate_options": "generate_options",
              "host.synthesize": "synthesize_evidence", "host.research": "bounded_research",
              "host.formulate_question": "formulate_question", "host.query_build": "build_query",
              "host.retrieval_needs": "interpret_retrieval_needs"}
PAYLOADS: dict[str, dict[str, Any]] = {
    "host.query_build": REQUESTS["host.query_build"],
    "host.retrieval_needs": REQUESTS["host.retrieval_needs"],
    "host.generate_options": {"problem": "Where should the cache live?", "max_options": 2,
                              "propose_criteria": True},
    "host.synthesize": {"operation": "synthesize_evidence", "question": "What must it do?"},
    "host.research": {"need": NEED},
    "host.formulate_question": {"question": "Which store?", "free_text_allowed": False,
                                "choices": [{"id": "sqlite", "label": "SQLite"},
                                            {"id": "files", "label": "Plain files"}]}}
RESPONSES: dict[str, dict[str, Any]] = {
    "host.retrieval_needs": {
        "original_question": REQUESTS["host.retrieval_needs"]["original_question"],
        "source_scope": {},
        "selections": {"entity_types": ["test"], "target_ids": ["CMP-1"],
                       "required_fields": ["name"], "document_types": ["source"],
                       "relationships": []},
        "uncertain": {name: [] for name in REQUESTS["host.retrieval_needs"]["catalog"]},
        "detail_mode": "fields", "completeness": "single_entity",
        "hierarchy_scope": "not_applicable", "scope_resolution": "sufficient",
        "unresolved": [], "rationale": "Fixture answer.", "engine": "host_llm",
        "status": "decided", "model_id": None},
    "host.query_build": {"candidate": {"query_id": "fixture.tests", "status": "proposed"}},
    "host.generate_options": {"options": [option("opt-a"), option("opt-b"), option("opt-c")],
                              "proposed_criteria": [criterion()]},
    "host.synthesize": {"findings": [finding_json(kind="inference")], "agreements": ["x"]},
    "host.research": {"evidence": [evidence_json("docs/cache.md#L1", "It lives in sqlite.")]},
    "host.formulate_question": {"question": "Where should the cache be stored?",
                                "free_text_allowed": False,
                                "choices": [{"id": "sqlite", "label": "SQLite file"},
                                            {"id": "files", "label": "Plain files"}]}}


def host_rig(capability_id: str) -> Rig:
    """Return a rig whose root waits on one host child of the capability."""
    request_schema, out_schema = SCHEMAS[capability_id]
    child = RequestProposal(
        kind=KINDS[capability_id], goal="Answer the host task", payload_schema=request_schema,
        payload=PAYLOADS[capability_id], requested_output_schema=out_schema)
    rig = Rig([descriptor("decide.root"),
               descriptor(capability_id, kinds=(KINDS[capability_id],), mode="host_handoff",
                          accepts=request_schema, produces=out_schema,
                          operations=(OPERATIONS[capability_id],))])
    rig.bind("decide.root", factory=two_phase(lambda inv: waiting(inv, child), completed))
    rig.bind(capability_id)
    return rig


def host_result(state: dict[str, Any], capability_id: str) -> Any:
    """Return the integrated result of the host invocation of the capability."""
    (inv,) = [i for i in state["invocations"].values() if i.capability_id == capability_id]
    return state["results"][inv.id]


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 12:30 [python-coder]: `host.formulate_question` is driven as a `capability` request
#   carrying a human_question_request payload, so the operation itself (packet, conversion,
#   security) is exercised end to end. (#KernelBootstrapV0/P8)
# - 2026-10-01 17:50 [python-coder]: Routing now wires the operation: with
#   `host.formulate_questions` on, a human request first spawns a `host.formulate_question` child
#   (integration/test_formulate_routing.py, INT2). This rig still drives the operation directly
#   because it tests the operation, not the routing. (#KernelBootstrapV0/P10)
# ====================================================================
