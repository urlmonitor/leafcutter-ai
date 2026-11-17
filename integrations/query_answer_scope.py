"""Preserve explicit population choices across durable human clarification.

MODULE: query_answer_scope
GOAL: Ask only for missing answer scope before exact enumeration.
BUSINESS CONTEXT: Excluding the family root and excluding all parents yield different totals.
ARCHITECTURE: Application adapter using existing human request and continuation contracts.
"""
from __future__ import annotations

from typing import Any

from kernel.contracts import RequestKind, RequestProposal, schema_ids
from kernel.contracts.payloads import HumanQuestionRequestPayload
from knowledge.answer_models import AnswerRequirements
from knowledge.errors import KnowledgeError


def missing_scope(requirements: dict | None) -> list[str]:
    """Return unresolved population choices, without guessing the caller's intent.

    Args:
        requirements: Original caller answer contract or legacy absence.

    Returns:
        Required scope fields that have not been supplied.
    """
    if requirements is None:
        return []
    if requirements.get("scope", {}).get("population") is None:
        return ["population"]
    need = AnswerRequirements.model_validate(requirements)
    if need.scope.population == "returned_entities":
        return []
    return [name for name in ("root_id", "levels", "inclusion")
            if getattr(need.scope, name) is None]


def scope_clarification(invocation: Any, ctx: Any, state: dict, usage: tuple = ()) -> Any:
    """Persist the original contract and ask a bounded existing human child.

    Args:
        invocation: Current registered invocation.
        ctx: Trusted clarification budget owner.
        state: Original pinned query continuation.
        usage: Measured planning usage already consumed.

    Returns:
        Existing waiting or exhausted capability result.
    """
    from integrations.query_planning import waiting
    from kernel.capabilities.decision.jev_support import blocked_result
    count = state.get("clarifications", 0)
    if count >= ctx.config.intent.max_clarifications:
        return blocked_result(invocation, "clarification_exhausted", "Answer population remains unclear")
    fields = [*state.get("answer_planning_missing", []), *missing_scope(state.get("answer_requirements"))]
    state.update(phase="clarify", clarification_kind="answer_scope", clarifications=count + 1)
    question = ("Please supply the missing population choices: " + ", ".join(fields)
                + ". For inclusion choose root_excluded (exclude only the selected root), "
                "terminal_leaves (exclude every parent), or include_root. "
                "Reply with JSON containing scope and, if requested, required_fields. Population may be returned_entities, ac_descendants or declared_dependents; a whole-project enumeration is unsupported and must be scoped explicitly. Original question: "
                + state["answer_requirements"]["original_question"])
    payload = HumanQuestionRequestPayload(question=question, free_text_allowed=True,
        why_research_cannot_settle="Only the caller can define the intended count population.",
        subject_ids=[state["need_id"]])
    child = RequestProposal(kind=RequestKind.HUMAN, question=question,
        payload_schema=schema_ids.HUMAN_QUESTION_REQUEST, payload=payload.model_dump(mode="json"),
        requested_output_schema=schema_ids.HUMAN_ANSWER)
    return waiting(invocation, state, child, usage)


def merge_scope(state: dict, supplied: dict) -> dict:
    """Fill missing choices while rejecting changes to already established obligations.

    Args:
        state: Persisted original research and source pins.
        supplied: Human JSON scope object or object containing scope.

    Returns:
        Continuation retaining the original question and requested fields.

    Raises:
        KnowledgeError: The answer attempts to change established population choices.
    """
    original = state["answer_requirements"]
    patch = supplied.get("scope", {k: v for k, v in supplied.items() if k != "required_fields"})
    if not isinstance(patch, dict):
        raise KnowledgeError("invalid_request", "Clarification scope must be a JSON object")
    scope = dict(original.get("scope", {}))
    for name, value in patch.items():
        if name not in state.get("answer_planning_missing", []) and scope.get(name) is not None and scope[name] != value:
            raise KnowledgeError("scope_mismatch", "Clarification cannot replace established " + name)
        scope[name] = value
    added_fields = supplied.get("required_fields", [])
    if not isinstance(added_fields, list) or any(not isinstance(value, str) for value in added_fields):
        raise KnowledgeError("invalid_request", "Required facts must be a list of field names")
    fields = list(dict.fromkeys([*original.get("required_fields", []), *added_fields]))
    checked_scope = {**scope, "population": scope.get("population") or "returned_entities"}
    need = AnswerRequirements.model_validate({**original, "scope": checked_scope, "required_fields": fields})
    resolved = need.model_dump(mode="json")
    resolved["scope"]["population"] = scope.get("population")
    unresolved = [name for name in state.get("answer_planning_missing", [])
                  if name == "population" and name not in patch or name == "required_fields" and not fields]
    return {**state, "answer_requirements": resolved,
            "answer_planning_missing": unresolved, "phase": "ready"}

# DECISION HISTORY
# - 2026-10-01 [python-coder]: Preserve scoped answer obligations and honest observation through existing runtime owners. (#KM-500/KM-500e-1)
