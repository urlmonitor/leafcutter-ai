"""MODULE: kernel.capabilities.research.needs
GOAL: Interpret a research question through the existing durable host interaction.
BUSINESS CONTEXT: Retrieval must preserve requested facts before selecting an operation.
ARCHITECTURE: Generic LangGraph node support; a composition-injected port owns domain offers.
"""
from __future__ import annotations

import logging
from typing import Protocol
from pydantic import Field

from kernel.capabilities.base import ExecutionContext
from kernel.capabilities.decision.jev_support import load_output_payload
from kernel.capabilities.host.retrieval_needs import RetrievalNeeds
from kernel.capabilities.research.state import Collected, Plan, ResearchContinuation
from kernel.contracts import NeedStatus, RequestKind, RequestProposal, ResultStatus, schema_ids
from kernel.contracts.base import KernelModel, fail
from kernel.contracts.capability import CapabilityResult
from kernel.contracts.evidence import EvidenceBundlePayload
from kernel.contracts.payloads import HumanQuestionRequestPayload
from kernel.contracts.retrieval_needs import LITERAL_ID, RetrievalNeedsOutput, RetrievalNeedsRequest, prepare_request
from kernel.contracts.work import CapabilityInvocation


class NeedsInterpreter(Protocol):
    """Application-owned finite meanings and deterministic projection, never an LLM client."""

    def prepare(self, ctx: ExecutionContext, plan: Plan) -> RetrievalNeedsRequest | None:
        """Return a bounded request only when this research requires interpretation."""

    def apply(self, plan: Plan, output: RetrievalNeedsOutput) -> Plan:
        """Preserve the accepted interpretation in the plan and downstream contracts."""


class NeedsContinuation(KernelModel):
    """One durable interpretation or clarification wait, separate from retrieval state."""

    phase: str = "interpreting_needs"
    request: RetrievalNeedsRequest
    clarifications: list[str] = Field(default_factory=list)


def guard_answerability(cont: ResearchContinuation, out: Collected, answers: dict[str, float]) -> None:
    """An interpreted request stays partial when its semantic answerability check did not run.

    Args:
        cont: Durable research or interpretation continuation.
        out: Collected evidence and coverage updated in place.
        answers: Per-need answerability judgments actually obtained.
    """
    if cont.retrieval_needs is None:
        return
    for need in cont.needs:
        if out.coverage.get(need.id) is NeedStatus.SATISFIED and need.id not in answers:
            out.coverage[need.id] = NeedStatus.PARTIAL
            out.limitations.append(f"need {need.id}: retrieval facts are present but answerability was not judged")


def unresolved(invocation: CapabilityInvocation, question: str, reasons: list[str]) -> CapabilityResult:
    """Return an explicit unresolved evidence result without claiming a search happened.

    Args:
        invocation: Current capability invocation and durable child outcomes.
        question: Original question or finite selector question identity.
        reasons: Explicit unmet obligations or unavailable mechanism reasons.

    Returns:
        Partial result exposing unresolved interpretation needs.
    """
    bundle = EvidenceBundlePayload(request_id=invocation.id, limitations=reasons,
        assessments={"retrieval_needs": {"kind": "retrieval_needs", "status": "unresolved",
            "original_question": question, "limitations": [*reasons]}}, unknowns=reasons)
    return CapabilityResult(invocation_id=invocation.id, work_item_id=invocation.work_item_id,
        status=ResultStatus.PARTIAL, output_schema_id=schema_ids.EVIDENCE_BUNDLE,
        output_payload=bundle.model_dump(mode="json"), limitations=reasons,
        diagnostics={"retrieval_needs_status": "unresolved"})


def _wait(invocation: CapabilityInvocation, cont: NeedsContinuation, child: RequestProposal) -> dict:
    """Yield one normal scheduler child while retaining the original request."""
    return {"result": CapabilityResult(invocation_id=invocation.id,
        work_item_id=invocation.work_item_id, status=ResultStatus.WAITING,
        requests=[child], continuation_state=cont.model_dump(mode="json"))}


def _host(invocation: CapabilityInvocation, cont: NeedsContinuation) -> dict:
    """Dispatch all dimensions in one operation through the registered host transport.

    Args:
        invocation: Current capability invocation and durable child outcomes.
        cont: Durable research or interpretation continuation.

    Returns:
        Scheduler wait containing one typed host request.
    """
    request = cont.request
    child = RequestProposal(kind=RequestKind.CAPABILITY,
        question=request.original_question, operation="interpret_retrieval_needs",
        payload_schema=schema_ids.RETRIEVAL_NEEDS_REQUEST, payload=request.model_dump(mode="json"),
        requested_output_schema=schema_ids.RETRIEVAL_NEEDS_OUTPUT)
    return _wait(invocation, cont.model_copy(update={"phase": "interpreting_needs"}), child)


def _child(invocation: CapabilityInvocation, ctx: ExecutionContext, schema: str) -> dict:
    """Consume exactly one completed current child, never an earlier accepted response.

    Args:
        invocation: Current capability invocation and durable child outcomes.
        ctx: Trusted execution scope, configuration and services.
        schema: Required typed child output schema.

    Returns:
        The current completed child output payload.
    """
    children = [c for c in invocation.child_outcomes if c.current_wait and c.output_schema_id == schema]
    if len(children) != 1 or children[0].status is not ResultStatus.COMPLETED:
        fail("Required retrieval-needs child did not complete")
    output = load_output_payload(ctx, children[0])
    if output is None:
        fail("Required retrieval-needs child output is unavailable")
    return output


def _clarify(invocation: CapabilityInvocation, ctx: ExecutionContext, cont: NeedsContinuation,
             output: RetrievalNeedsOutput) -> dict:
    """Ask only for the unresolved user choice; a changed answer permits another attempt.

    Args:
        invocation: Current capability invocation and durable child outcomes.
        ctx: Trusted execution scope, configuration and services.
        cont: Durable research or interpretation continuation.
        output: Validated needs interpretation from the host.

    Returns:
        Human clarification wait or explicit exhausted-budget result.
    """
    if len(cont.clarifications) >= ctx.config.intent.max_clarifications:
        return {"result": unresolved(invocation, cont.request.original_question,
                                    ["retrieval-needs clarification budget exhausted", *output.unresolved])}
    question = "Please clarify the requested information: " + "; ".join(output.unresolved)
    question += ". Original question: " + cont.request.original_question
    request = HumanQuestionRequestPayload(question=question, free_text_allowed=True,
        why_research_cannot_settle="The interpretation identifies a missing user choice.")
    child = RequestProposal(kind=RequestKind.HUMAN, question=question,
        payload_schema=schema_ids.HUMAN_QUESTION_REQUEST, payload=request.model_dump(mode="json"),
        requested_output_schema=schema_ids.HUMAN_ANSWER)
    return _wait(invocation, cont.model_copy(update={"phase": "clarifying_needs"}), child)


def _clarification_reply(invocation: CapabilityInvocation, ctx: ExecutionContext,
                         cont: NeedsContinuation) -> dict:
    """Keep human candidates unverified while retaining the original question and scope.

    Args:
        invocation: Current capability invocation and durable child outcomes.
        ctx: Trusted execution scope, configuration and services.
        cont: Durable research or interpretation continuation.

    Returns:
        New host wait retaining the original source permissions.
    """
    answer = _child(invocation, ctx, schema_ids.HUMAN_ANSWER).get("free_text")
    if not isinstance(answer, str) or not answer.strip() or answer in cont.clarifications:
        fail("Retrieval-needs clarification must supply new nonempty information")
    supplied_ids = LITERAL_ID.findall(answer)
    updated = cont.request.model_copy(update={
        "context": [*cont.request.context, answer],
        "known_ids": list(dict.fromkeys([*cont.request.known_ids, *supplied_ids]))})
    updated = prepare_request(RetrievalNeedsRequest.model_validate(updated.model_dump(mode="json")))
    return _host(invocation, cont.model_copy(update={"request": updated,
        "clarifications": [*cont.clarifications, answer]}))


def interpret(invocation: CapabilityInvocation, ctx: ExecutionContext, plan: Plan,
              interpreter: NeedsInterpreter | None) -> dict:
    """Run the interpreter boundary once, or resume its exact durable wait.

    Args:
        invocation: Existing research invocation and its current child receipts.
        ctx: Trusted scope, configuration and artifact access.
        plan: Original parsed research request.
        interpreter: Optional application-owned domain adapter.

    Returns:
        The interpreted plan or an ordinary waiting/partial capability result.
    """
    if interpreter is None:
        return {"plan": plan}
    try:
        request = interpreter.prepare(ctx, plan)
        if request is None:
            return {"plan": plan}
        if not ctx.config.host.enabled:
            return {"result": unresolved(invocation, plan.question, ["retrieval-needs host operation is disabled"])}
        if invocation.continuation is None:
            return _host(invocation, NeedsContinuation(request=request))
        cont = NeedsContinuation.model_validate(invocation.continuation.state)
        if cont.request.original_question != request.original_question or cont.request.source_scope != request.source_scope:
            return {"result": unresolved(invocation, plan.question,
                ["Retrieval-needs continuation differs from the original question or trusted scope"])}
        if cont.phase == "clarifying_needs":
            return _clarification_reply(invocation, ctx, cont)
        output = RetrievalNeedsOutput.model_validate(_child(invocation, ctx, schema_ids.RETRIEVAL_NEEDS_OUTPUT))
        violations = RetrievalNeeds().submission_violations(cont.request.model_dump(mode="json"), output)
        if violations:
            return {"result": unresolved(invocation, plan.question, ["; ".join(violations)])}
        if output.status != "decided":
            if output.scope_resolution == "user_choice_missing" and "needs_outside_catalog" not in output.unresolved:
                return _clarify(invocation, ctx, cont, output)
            return {"result": unresolved(invocation, plan.question, output.unresolved or ["retrieval needs remain unresolved"])}
        return {"plan": interpreter.apply(plan, output)}
    except ValueError as exc:
        logging.getLogger(__name__).warning("Retrieval-needs boundary rejected input (%s)", type(exc).__name__)
        return {"result": unresolved(invocation, plan.question, [str(exc)])}


# DECISION HISTORY
# ================================================================================
# - 2026-10-09 15:40 [python-coder]: Reuse scheduler-owned host/human waits before research planning. (#KM-500/KM-500e-1-i)
