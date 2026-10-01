"""
MODULE: tests.kernel.capabilities.support
GOAL: Shared builders for the native-capability tests: invocations and resumptions, child-output
    storage, evidence factories and ScriptedJev scripts for the decision and research graphs.
BUSINESS CONTEXT: The decision and research graphs pause and resume through the kernel; tests
    must simulate exactly what the kernel hands back (continuation plus child outcomes read via
    the artifact store) without a scheduler, so the graphs are exercised through their real
    CapabilityExecutor entry point.
ARCHITECTURE: Builds real contract models only. Scripts read a mutable `params` dict so one test
    can change Jev's answers between resumptions.
"""

from __future__ import annotations

import json
import unittest
from collections.abc import Sequence
from typing import Any
from unittest import mock

from kernel.capabilities.base import ExecutionContext
from kernel.capabilities.retrieval import versioning
from kernel.contracts import Priority
from kernel.contracts.base import content_hash, evidence_id, new_id, utc_now
from kernel.contracts.capability import CapabilityResult
from kernel.contracts.decision import Criterion, Option
from kernel.contracts.enums import (
    ApprovalStatus,
    EvidenceCategory,
    ProposalStatus,
    RequestKind,
    ResultStatus,
)
from kernel.contracts.evidence import Evidence
from kernel.contracts.payloads import DecisionRequestPayload
from kernel.contracts.work import CapabilityInvocation, ChildOutcome, Continuation
from kernel.providers.fakes import ScriptedJev, choice_answer, noul_answer


def evidence_item(locator: str, excerpt: str,
                  category: EvidenceCategory = EvidenceCategory.PRIOR_DECISIONS) -> Evidence:
    """Return a valid content-addressed Evidence item of the given category."""
    digest = content_hash(excerpt)
    return Evidence.model_validate({
        "id": evidence_id(locator, digest), "category": category,
        "semantic_type": "repository_fact", "excerpt": excerpt, "content_hash": digest,
        "source": {"id": "repo.decisions", "kind": "repository_file", "locator": locator,
                   "source_version": {"commit": "abc1234567", "dirty": False}},
        "provenance": {"producer": "test"}})


def invocation(capability_id: str, schema: str, payload: dict, *, work_item_id: str | None = None,
               continuation: dict | None = None, outcomes: Sequence[ChildOutcome] = (),
               context_refs: Sequence[str] = ()) -> CapabilityInvocation:
    """Build a CapabilityInvocation, optionally resuming from a continuation."""
    cont = None
    if continuation is not None:
        cont = Continuation(capability_id=capability_id, capability_version="1.0.0",
                            state=continuation, resume_reason="children_done")
    return CapabilityInvocation(
        id=new_id("inv"), work_item_id=work_item_id or new_id("work"),
        capability_id=capability_id, capability_version="1.0.0", input_payload_schema=schema,
        input_payload=payload, input_fingerprint="fp-test", continuation=cont,
        child_outcomes=list(outcomes), context_refs=list(context_refs), created_at=utc_now())


def resume(previous: CapabilityInvocation, result: CapabilityResult,
           outcomes: Sequence[ChildOutcome] = ()) -> CapabilityInvocation:
    """Build the invocation the kernel would hand back after the children of `result` finish."""
    return invocation(previous.capability_id, previous.input_payload_schema,
                      previous.input_payload, work_item_id=previous.work_item_id,
                      continuation=result.continuation_state, outcomes=outcomes)


def child(ctx: ExecutionContext, kind: RequestKind, schema: str, payload: dict | None,
          status: ResultStatus = ResultStatus.COMPLETED) -> ChildOutcome:
    """Store a child's output payload as an artifact and return its ChildOutcome."""
    work_id = new_id("work")
    ref = None
    if payload is not None:
        ref = f"child-{work_id}.json"
        ctx.artifacts.write_artifact(ctx.run_id, ref,
                                     json.dumps({"output_payload": payload}))
    return ChildOutcome(work_item_id=work_id, request_kind=kind, status=status,
                        output_schema_id=schema, result_ref=ref)


def decision_payload(options: bool = True, criteria: bool = True, **extra: Any) -> dict:
    """Return a decision_request.v1 payload (options A/B, criteria c1/c2 by default)."""
    opts = [Option(id="A", title="Use sqlite"), Option(id="B", title="Use files")]
    crit = [Criterion(id="c1", question="Is it safe for concurrent writers?"),
            Criterion(id="c2", question="Is it simple to operate?", priority=Priority("supporting"))]
    body = DecisionRequestPayload(
        question="Where should run state live?", options=opts if options else [],
        criteria=crit if criteria else [], criteria_missing=not criteria, **extra)
    return body.model_dump(mode="json")


def proposed_criteria() -> list[Criterion]:
    """Return two LLM-proposed criteria (proposal_status proposed, approval proposed)."""
    return [Criterion(id=f"p{i}", question=f"Proposed criterion {i}?",
                      proposal_status=ProposalStatus.PROPOSED,
                      approval_status=ApprovalStatus.PROPOSED, proposed_by="host")
            for i in (1, 2)]


def no_git(testcase: unittest.TestCase) -> None:
    """Make revision lookup hermetic: git is reported unusable and the cache is cleared."""
    versioning._CACHE.clear()
    patcher = mock.patch.object(versioning, "_git", return_value=None)
    patcher.start()
    testcase.addCleanup(patcher.stop)
    testcase.addCleanup(versioning._CACHE.clear)


def script_decision(jev: ScriptedJev, params: dict | None = None) -> dict:
    """Script decision.assess answers from a mutable params dict and return it.

    Keys: sufficient, satisfies ({(crit, opt): p}), default_sat, missing, preference, conflict.
    """
    p: dict[str, Any] = {"sufficient": 0.95, "satisfies": {}, "default_sat": 0.05, "missing": "none",
         "preference": 0.05, "conflict": 0.05}
    p.update(params or {})

    def sat(question, batch):  # noqa: ANN001 - ScriptedJev callback signature
        for crit in batch.state["criteria"]:
            for opt in batch.state["options"]:
                if question.id == f"satisfies.{crit}.{opt}":
                    return noul_answer(p["satisfies"].get((crit, opt), p["default_sat"]))
        return noul_answer(p["default_sat"])

    jev.script("decision.assess", "sufficient.*", lambda q, b: noul_answer(p["sufficient"]))
    jev.script("decision.assess", "satisfies.*", sat)
    jev.script("decision.assess", "missing", lambda q, b: choice_answer(p["missing"]))
    jev.script("decision.assess", "preference", lambda q, b: noul_answer(p["preference"]))
    jev.script("decision.assess", "conflict", lambda q, b: noul_answer(p["conflict"]))
    return p


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:00 [python-coder]: Satisfies answers are matched against the ids in the batch
#   state, so criterion ids containing dots (human-edited criteria) resolve unambiguously.
#   (#KernelBootstrapV0/P5)
# ====================================================================
