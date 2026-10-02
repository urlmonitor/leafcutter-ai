"""Bounded Jev selection and ordinary child proposals for query growth."""
from __future__ import annotations

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import Any
    from collections.abc import Sequence
    from kernel.capabilities.base import ExecutionContext
    from kernel.contracts import CapabilityInvocation, CapabilityResult, RequestProposal, Usage
import hashlib
import json
from kernel.capabilities.decision.jev_support import ask_jev, choice_question, make_batch
from kernel.contracts import CapabilityResult, RequestKind, RequestProposal, ResultStatus, schema_ids
from kernel.contracts.payloads import HumanQuestionRequestPayload
from kernel.contracts.query import QueryBuildRequest
from knowledge.errors import KnowledgeError

async def choose(ctx: ExecutionContext, invocation: CapabilityInvocation, purpose: str, question_id: str, state: dict[str, Any], options: dict[str, str]) -> tuple[str, list[Usage]]:
    """Select only a supplied option through existing reserve-before-use Jev.


    Args:
        ctx: Trusted runtime scope, budgets and services.
        invocation: Current registered invocation and persisted continuation.
        purpose: Versioned purpose of the bounded judgment.
        question_id: Stable judgment identifier.
        state: Persisted query plan and bounded progress.
        options: Explicit eligible choices offered to Jev.

    Returns:
        tuple: Selected option (or clarify) and measured usage.
    """
    answer = await ask_jev(ctx, invocation, make_batch(ctx,purpose,state,[choice_question(
        question_id,purpose+".v1","Select only a supported option; missing facts require clarification.",options)]))
    pick = answer.choice(question_id)
    if pick.choice not in options:
        raise KnowledgeError("invalid_request","Jev selected an unoffered query option")
    certain = (pick.probabilities.get(pick.choice,0)>=ctx.config.routing.min_selected_probability
               and pick.confidence is not None and pick.confidence>=ctx.config.routing.min_confidence)
    return (pick.choice if certain else "clarify"), [answer.usage]

def waiting(invocation: CapabilityInvocation, state: dict[str, Any], child: Any, usage: Sequence[Usage]=()) -> CapabilityResult:
    """Persist a query continuation and yield one normal scheduler child.


    Args:
        invocation: Current registered invocation and persisted continuation.
        state: Persisted query plan and bounded progress.
        child: Input to the documented operation.
        usage: Already measured provider usage for this invocation.

    Returns:
        CapabilityResult: Waiting result whose state survives a process restart.
    """
    return CapabilityResult(invocation_id=invocation.id,work_item_id=invocation.work_item_id,
        status=ResultStatus.WAITING,requests=[child],continuation_state=state,usage=list(usage))

def clarification(invocation: CapabilityInvocation,ctx: ExecutionContext,state: dict[str, Any],usage: Sequence[Usage]=()) -> CapabilityResult:
    """Ask a bounded existing human question without repeating answered questions.


    Args:
        invocation: Current registered invocation and persisted continuation.
        ctx: Trusted runtime scope, budgets and services.
        state: Persisted query plan and bounded progress.
        usage: Already measured provider usage for this invocation.

    Returns:
        CapabilityResult: Ordinary human wait or explicit exhausted failure.
    """
    from kernel.capabilities.decision.jev_support import blocked_result
    count=state.get("clarifications",0)
    if count>=ctx.config.intent.max_clarifications:
        return blocked_result(invocation,"clarification_exhausted","Query scope remains unclear")
    state.update(phase="clarify",clarifications=count+1)
    pending=state.get("pending_descriptor",{}).get("parameters",{})
    known=state.get("arguments",{})
    missing=[name for name,spec in pending.items() if spec.get("required",False)
             and name not in known and name not in {"component_ids","entity_ids","component_id"}]
    if missing:
        field=missing[0]
        state.update(clarification_kind="argument",awaiting_parameter=field)
        question=f"What {field.replace('_',' ')} should I use for this research?"
        if pending[field]["type"]=="string_list":
            question+=" You can give several values separated by commas."
    elif not state["component_ids"]:
        state["clarification_kind"]="scope"
        question="Which project component should I research? Give its component ID, or several IDs separated by commas."
    else:
        state["clarification_kind"]="question"
        question="What specifically should I find out about the selected component?"
    question+=" Current question: "+state["question"]
    payload=HumanQuestionRequestPayload(question=question,free_text_allowed=True,
        why_research_cannot_settle="The intended component scope or question is not clear.",
        subject_ids=[state["need_id"]])
    child=RequestProposal(kind=RequestKind.HUMAN,question=question,
        payload_schema=schema_ids.HUMAN_QUESTION_REQUEST,payload=payload.model_dump(mode="json"),
        requested_output_schema=schema_ids.HUMAN_ANSWER)
    return waiting(invocation,state,child,usage)

def build_request(invocation: CapabilityInvocation,state: dict[str, Any]) -> RequestProposal:
    """Route a genuinely missing query through canonical gap detection and host fallback.


    Args:
        invocation: Current registered invocation and persisted continuation.
        state: Persisted query plan and bounded progress.

    Returns:
        RequestProposal: Unsupported capability request with typed coding output.
    """
    attempt=hashlib.sha256((state["question"]+state["source_sha"]).encode()).hexdigest()[:20]
    payload=QueryBuildRequest(question=state["question"],repository_id=state["repository_id"],
        source_sha=state["source_sha"],generation_id=state["generation_id"],
        component_ids=state["component_ids"],need_id=state["need_id"],attempt_id=attempt,
        available_queries=state.get("available_queries",[]),remaining_budget=state.get("remaining_budget",{}),
        expected_result="Canonical "+state.get("target_kind","entity")+" results with source provenance for: "+state["question"])
    return RequestProposal(kind=RequestKind.CAPABILITY,question=state["question"],
        operation="missing_query."+attempt,payload_schema=schema_ids.QUERY_BUILD_REQUEST,
        payload=payload.model_dump(mode="json"),requested_output_schema=schema_ids.QUERY_CANDIDATE)

def _answer_scope(state: dict, value: dict) -> dict | None:
    """Recognize a pending answer-contract clarification.

    Args:
        state: Original checkpointed clarification.
        value: Literal human JSON response.

    Returns:
        Updated scope continuation or None for ordinary component clarification.
    """
    if state.get("clarification_kind") != "answer_scope":
        return None
    from integrations.query_answer_scope import merge_scope
    return merge_scope(state, value)

def _validate_components(ids: list, ctx: ExecutionContext) -> None:
    """Enforce established task component scope on literal human clarification.

    Args:
        ids: Proposed literal component IDs.
        ctx: Trusted task scope.

    Raises:
        KnowledgeError: Missing, malformed or broadened scope.
    """
    if not isinstance(ids,list) or not 1<=len(ids)<=20 or any(not isinstance(x,str) or not x for x in ids):
        raise KnowledgeError("invalid_request","Clarification requires one to twenty component IDs")
    if ctx.scope.component_ids and not set(ids)<=set(ctx.scope.component_ids):
        raise KnowledgeError("scope_mismatch","Clarification cannot broaden task component scope")

def human_scope(answer: dict,ctx: ExecutionContext,state: dict[str, Any]) -> dict[str, Any]:
    """Decode literal human scope without treating supplied text as query syntax.


    Args:
        answer: Validated human clarification payload.
        ctx: Trusted runtime scope, budgets and services.
        state: Persisted query plan and bounded progress.

    Returns:
        dict: Updated continuation with bounded IDs within the task's component scope.
    """
    text=answer.get("free_text","").strip()
    if text.startswith("{"):
        value=json.loads(text)
        scoped = _answer_scope(state, value)
        if scoped is not None:
            return scoped
    elif state.get("clarification_kind")=="argument":
        field=state["awaiting_parameter"]
        spec=state["pending_descriptor"]["parameters"][field]
        answer=[x.strip() for x in text.split(",") if x.strip()] if spec["type"]=="string_list" else text
        value={"arguments":{**state.get("arguments",{}),field:answer}}
    elif state.get("clarification_kind")=="question":
        value={"question":text}
    else:
        value={"component_ids":text.replace(","," ").split()}
    ids=value.get("component_ids",state.get("component_ids"))
    _validate_components(ids, ctx)
    question=value.get("question",state["question"])
    if not isinstance(question,str) or not 1<=len(question)<=8000:
        raise KnowledgeError("invalid_request","Clarified question is invalid")
    arguments=value.get("arguments",state.get("arguments",{}))
    if not isinstance(arguments,dict):
        raise KnowledgeError("invalid_request","Clarified arguments must be a JSON object")
    return {**state,"component_ids":ids,"question":question,"arguments":arguments,"phase":"select"}
