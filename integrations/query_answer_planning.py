"""Bounded semantic planning of original repository question obligations.

MODULE: query_answer_planning
GOAL: Derive requested facts and population choices through the existing Jev owner.
BUSINESS CONTEXT: Query availability must not rewrite what the caller wanted answered.
ARCHITECTURE: One budgeted batch over supplied field meanings and literal ID candidates.
"""
from __future__ import annotations

from typing import Any

import re
from kernel.capabilities.decision.jev_support import ask_jev, choice_question, make_batch, noul_question
from pydantic import JsonValue
from knowledge.answer_models import AnswerRequirements, AnswerScope

FIELDS = {
    "canonical_id": "The stable identities of the requested entities, such as which tests or ACs.",
    "kind": "The canonical entity type of each returned item.",
    "title": "The source-backed human-readable name of each returned item.",
    "source_sha": "The immutable source revision supporting each entity.",
    "source_locator": "The exact source location supporting each entity.",
    "priority": "Declared source priority, not an inferred business ranking or dependency count.",
    "level": "The canonical requirement hierarchy level.",
    "test_required": "The explicit source test requirement, not evidence of execution.",
    "work_status": "Implementation progress, such as done or todo; distinct from lifecycle status.",
    "status": "Canonical lifecycle status, such as active; not delivery completion.",
    "criteria": "Exact source acceptance clauses.",
    "req_status": "Requirement governance state.",
    "readiness": "Planning approval readiness, not implementation proof.",
    "covered_by": "Declared test references, not evidence of a test run.",
    "implemented_by": "Declared implementation references, not a complete call graph.",
    "depends_on": "Declared requirement dependencies, not inferred code impact.",
}
POPULATIONS = {"returned_entities": "Facts about the selected returned entities, without a global count.",
    "ac_descendants": "Requirements in a caller-defined canonical parent hierarchy.",
    "declared_dependents": "Requirements directly declaring dependency on the selected root.",
    "clarify": "The required population is unclear."}
INCLUSIONS = {"root_excluded": "Exclude only the selected family root, including nonterminal descendants.",
    "terminal_leaves": "Exclude every requirement with children.",
    "include_root": "Include the selected root as well as descendants.",
    "clarify": "The caller has not resolved these materially different choices."}


def _certain_choice(answer: Any, options: dict, ctx: Any) -> str | None:
    """Accept only offered sufficiently confident choices; ambiguity stays explicit.

    Args:
        answer: Actual choice distribution.
        options: Supplied finite choices.
        ctx: Configured confidence thresholds.

    Returns:
        Offered choice or None.
    """
    if (answer.choice not in options or answer.choice == "clarify"
            or answer.confidence is None or answer.confidence < ctx.config.routing.min_confidence
            or answer.probabilities.get(answer.choice, 0) < ctx.config.routing.min_selected_probability):
        return None
    return answer.choice


async def plan_answer(ctx: Any, invocation: Any, state: dict) -> tuple[dict, list]:
    """Derive an additive answer contract without inventing identifiers or source facts.

    Args:
        ctx: Existing budgeted Jev execution context.
        invocation: Current registered retrieval invocation.
        state: Pinned original question and source generation.

    Returns:
        Updated continuation and measured provider usage.
    """
    if state.get("answer_requirements") is not None:
        return state, []
    question = state["original_question"]
    candidates = sorted(set(re.findall(r"\b[A-Z][A-Z0-9]*(?:-[A-Z]+)*-\d+[a-z]?(?:-\d+)?(?:-[ivx]+)?\b", question)))[:20]
    roots = {identifier: "Literal caller-supplied candidate root " + identifier for identifier in candidates}
    roots["clarify"] = "No caller-supplied root can be selected with confidence."
    questions = [noul_question("field." + key, "knowledge.answer_contract.v1",
        "Does answering the original question require this fact? " + meaning) for key, meaning in FIELDS.items()]
    questions += [choice_question("population", "knowledge.answer_contract.v1", "Which population does the caller require?", POPULATIONS),
        choice_question("inclusion", "knowledge.answer_contract.v1", "Which explicit inclusion rule did the caller establish?", INCLUSIONS),
        choice_question("root", "knowledge.answer_contract.v1", "Which literal supplied ID is the intended population root?", roots)]
    questions += [noul_question("level." + level, "knowledge.answer_contract.v1",
        "Does the caller explicitly include hierarchy level " + level + "?") for level in ("L0", "L1", "L2", "L3")]
    field_meanings: dict[str, JsonValue] = dict(FIELDS)
    answer = await ask_jev(ctx, invocation, make_batch(ctx, "knowledge.answer_contract",
        {"original_question": question, "source_sha": state["source_sha"], "field_meanings": field_meanings}, questions))
    fields = [name for name in FIELDS if answer.noul("field." + name).probability >= ctx.config.research.need_required_threshold]
    population = _certain_choice(answer.choice("population"), POPULATIONS, ctx)
    scope = {"population": population or "returned_entities",
        "root_id": _certain_choice(answer.choice("root"), roots, ctx),
        "inclusion": _certain_choice(answer.choice("inclusion"), INCLUSIONS, ctx),
        "levels": [level for level in ("L0", "L1", "L2", "L3")
            if answer.noul("level." + level).probability >= ctx.config.research.need_required_threshold] or None}
    need = AnswerRequirements(original_question=question, required_fields=fields, scope=AnswerScope.model_validate(scope))
    requirements = need.model_dump(mode="json")
    if population is None:
        requirements["scope"]["population"] = None
    return {**state, "answer_requirements": requirements,
            "answer_planning_missing": (["population"] if population is None else []) + (["required_fields"] if not fields else [])}, [answer.usage]

# DECISION HISTORY
# - 2026-10-01 [python-coder]: Preserve scoped answer obligations and honest observation through existing runtime owners. (#KM-500/KM-500e-1)
