"""
MODULE: kernel.capabilities.decision.assess
GOAL: The `assess` node: one Jev batch of bounded, literal, atomic questions about sufficiency,
    satisfaction, missing knowledge, preference and conflict, parsed into an Assessment.
BUSINESS CONTEXT: Jev is a classifier, not a planner: each question makes one literal judgement
    about a named part of the state, nothing that code can compute is asked, and the raw
    probabilities are kept for the trace (Rev 3 section 9.4, ADR-053 section 5).
ARCHITECTURE: Templates carry an id and version. Evidence, options and criteria enter only as
    quoted state values; evidence text never becomes part of an instruction.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import JsonValue

from kernel.capabilities.base import ExecutionContext
from kernel.capabilities.decision.jev_support import (
    ask_jev,
    choice_question,
    evidence_state,
    make_batch,
    noul_question,
)
from kernel.capabilities.decision.state import Working
from kernel.contracts.enums import EvidenceCategory, MissingKnowledge
from kernel.contracts.work import CapabilityInvocation
from kernel.providers.base import ChoiceAnswer, JevResult, QuestionSpec

PURPOSE = "decision.assess"
NONE_CHOICE = "none"
_PATTERN_CATEGORIES = {EvidenceCategory.EXISTING_PATTERNS}
_MISSING_TEXT = {
    MissingKnowledge.MISSING_TASK_FACT: "a fact about the task itself is missing",
    MissingKnowledge.UNKNOWN_OPTIONS: "the set of options is unknown or incomplete",
    MissingKnowledge.MISSING_DECISION_BASIS: "no earlier recorded decision covers this",
    MissingKnowledge.MISSING_AUTHORITATIVE_GUIDANCE: "official guidance is missing",
    MissingKnowledge.MISSING_INTERNAL_PRINCIPLE: "a project rule or principle is missing",
    MissingKnowledge.CONFLICTING_EVIDENCE: "evidence items contradict each other",
    MissingKnowledge.MISSING_IMPLEMENTATION_FACT: "a fact about the existing implementation "
                                                  "is missing",
    MissingKnowledge.HUMAN_PREFERENCE_OR_AUTHORIZATION: "a human preference or authorization "
                                                        "is missing",
}


@dataclass(frozen=True)
class Assessment:
    """Parsed Jev answers for one assessment round."""

    sufficient: dict[str, float]
    satisfies: dict[tuple[str, str], float]
    sufficient_confidence: dict[str, float | None]
    satisfies_confidence: dict[tuple[str, str], float | None]
    missing: ChoiceAnswer
    preference: float
    conflict: float
    result: JevResult


def _state(ctx: ExecutionContext, work: Working) -> dict[str, JsonValue]:
    """Build the quoted state: question, options, criteria, evidence, constraints, findings."""
    constraints = [e.excerpt or "" for e in ctx.evidence(work.constraint_ids)]
    constraints += work.cont.human_inputs
    evidence = evidence_state(ctx, work.evidence)
    for item in work.evidence:
        role = "pattern_only" if item.category in _PATTERN_CATEGORIES else "decision_basis"
        evidence[item.id]["role"] = role  # type: ignore[index]
        evidence[item.id]["category"] = item.category.value  # type: ignore[index]
    return {
        "question": work.question,
        "options": {o.id: f"{o.title}. {o.description}".strip() for o in work.usable_options},
        "criteria": {c.id: c.question for c in work.usable_criteria},
        "evidence": evidence, "constraints": constraints, "findings": work.cont.findings,
    }


def _questions(work: Working) -> list[QuestionSpec]:
    """Build every question of the batch (ids are addressed by the maps built alongside)."""
    qs: list[QuestionSpec] = []
    for c in work.usable_criteria:
        qs.append(noul_question(
            f"sufficient.{c.id}", "decision.sufficient",
            f"Does `evidence` contain enough information to judge each option in `options` "
            f"against `criteria.{c.id}`? Items with role pattern_only only show how something "
            f"is done, not that it is required."))
        qs += [noul_question(
            f"satisfies.{c.id}.{o.id}", "decision.satisfies",
            f"According to `evidence`, does option `options.{o.id}` satisfy "
            f"`criteria.{c.id}`?") for o in work.usable_options]
    qs.append(choice_question(
        "missing", "decision.missing",
        "Which one kind of knowledge is most missing from `evidence` to answer `question`? "
        "Answer none if nothing is missing.",
        {**{m.value: t for m, t in _MISSING_TEXT.items()}, NONE_CHOICE: "nothing is missing"}))
    qs.append(noul_question(
        "preference", "decision.preference",
        "Does choosing between `options` depend on a user preference, requirement or "
        "authorization that `constraints` do not state?"))
    qs.append(noul_question(
        "conflict", "decision.conflict",
        "Do items in `evidence` contradict each other on a point that affects `question`?"))
    return qs


async def assess(ctx: ExecutionContext, invocation: CapabilityInvocation, work: Working
                 ) -> Assessment:
    """Send the assessment batch and parse the answers.

    Raises:
        StopCapability: Budget refused or the provider failed (see ask_jev).
    """
    batch = make_batch(ctx, PURPOSE, _state(ctx, work), _questions(work))
    result = await ask_jev(ctx, invocation, batch)
    crit, opts = work.usable_criteria, work.usable_options
    suff = {c.id: result.noul(f"sufficient.{c.id}") for c in crit}
    sat = {(c.id, o.id): result.noul(f"satisfies.{c.id}.{o.id}") for c in crit for o in opts}
    return Assessment(
        sufficient={k: v.probability for k, v in suff.items()},
        satisfies={k: v.probability for k, v in sat.items()},
        sufficient_confidence={k: v.confidence for k, v in suff.items()},
        satisfies_confidence={k: v.confidence for k, v in sat.items()},
        missing=result.choice("missing"), preference=result.noul("preference").probability,
        conflict=result.noul("conflict").probability, result=result)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:00 [python-coder]: Evidence carries a `role` (decision_basis or pattern_only)
#   in the quoted state so Jev sees that an existing implementation is a pattern, not proof.
#   (#KernelBootstrapV0/P5)
# ====================================================================
