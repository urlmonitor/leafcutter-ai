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

from dataclasses import dataclass, field

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
from kernel.contracts.decision import Criterion
from kernel.contracts.enums import EvidenceCategory, MissingKnowledge
from kernel.contracts.work import CapabilityInvocation
from kernel.memory.precedent import (
    precedent_questions,
    precedent_state,
    read_scores,
)
from kernel.providers.base import ChoiceAnswer, JevResult, QuestionSpec, json_strings

PURPOSE = "decision.assess"
NONE_CHOICE = "none"
#: Version of the criterion-kind question (2: literal, atomic, boundary cases stated).
KIND_TEMPLATE_VERSION = "2"
KIND_INSTRUCTIONS = (
    "`criteria.{id}` asks about a property that each proposed option in `options` would have "
    "(how the design would behave, look or be used if it were built), not about a fact that "
    "`evidence` or the repository already states today. True or false?")
KIND_CRITERIA = {
    "true": "The criterion is about the designs themselves and can only be judged by imagining "
            "each option built. Example: whether changes would show up as small, reviewable "
            "diffs, or whether an existing parser could read a format the option would produce.",
    "false": "The criterion asks what `evidence` or the repository already states today and can "
             "be looked up. Example: whether the project already uses YAML for its "
             "configuration, or whether a recorded decision already says how a thing is "
             "handled."}
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


#: Prefix that labels a constraint as stated by a human (not found by the kernel).
HUMAN_STATED = "human-stated: "


@dataclass(frozen=True)
class Assessment:
    """Parsed Jev answers for one assessment round."""

    sufficient: dict[str, float]
    satisfies: dict[tuple[str, str], float]
    sufficient_confidence: dict[str, float | None]
    satisfies_confidence: dict[tuple[str, str], float | None]
    missing: ChoiceAnswer
    #: Probability that a criterion is a design judgement, for criteria not classified yet.
    design: dict[str, float]
    preference: float
    conflict: float
    result: JevResult
    #: Jev's probability that each precedent (by record id) applies; empty when none was judged.
    precedents: dict[str, float] = field(default_factory=dict)


def _state(ctx: ExecutionContext, work: Working) -> dict[str, JsonValue]:
    """Build the quoted state: question, options, criteria, evidence, constraints, findings."""
    constraints = [*ctx.constraints, *(e.excerpt or "" for e in ctx.evidence(work.constraint_ids))]
    constraints += [f"{HUMAN_STATED}{t}"
                    for t in (*work.cont.human_inputs, *work.cont.conditions)]
    evidence = evidence_state(ctx, work.evidence)
    for item in work.evidence:
        role = "pattern_only" if item.category in _PATTERN_CATEGORIES else "decision_basis"
        entry = evidence[item.id]
        if isinstance(entry, dict):
            entry["role"] = role
            entry["category"] = item.category.value
    state: dict[str, JsonValue] = {
        "question": work.question,
        "options": {o.id: f"{o.title}. {o.description}".strip() for o in work.usable_options},
        "criteria": {c.id: c.question for c in work.usable_criteria},
        "evidence": evidence, "constraints": json_strings(constraints),
        "findings": json_strings(work.cont.findings),
    }
    if work.precedent_hits:  # earlier approved decisions to judge in this same batch
        state["precedents"] = precedent_state(work.precedent_hits)
    return state


def unclassified(work: Working) -> list[Criterion]:
    """Return the usable criteria whose kind nobody has set yet (Jev classifies them once)."""
    return [c for c in work.usable_criteria if c.kind_source is None]


def kind_question(criterion_id: str) -> QuestionSpec:
    """Return the literal criterion-kind question: one atomic judgement with both readings named.

    It follows the TypeSafe guidance (ADR-053 section 5): one literal true/false judgement, the
    state part named in backticks, and a boundary example for each answer.
    """
    return noul_question(
        f"kind.{criterion_id}", "decision.kind", KIND_INSTRUCTIONS.format(id=criterion_id),
        criteria=dict(KIND_CRITERIA), version=KIND_TEMPLATE_VERSION)


def _questions(work: Working) -> list[QuestionSpec]:
    """Build every question of the batch (ids are addressed by the maps built alongside)."""
    qs: list[QuestionSpec] = [kind_question(c.id) for c in unclassified(work)]
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
    return [*qs, *precedent_questions(work.precedent_hits)]


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
    design = {c.id: result.noul(f"kind.{c.id}").probability for c in unclassified(work)}
    return Assessment(
        design=design,
        sufficient={k: v.probability for k, v in suff.items()},
        satisfies={k: v.probability for k, v in sat.items()},
        sufficient_confidence={k: v.confidence for k, v in suff.items()},
        satisfies_confidence={k: v.confidence for k, v in sat.items()},
        missing=result.choice("missing"), preference=result.noul("preference").probability,
        conflict=result.noul("conflict").probability, result=result,
        precedents=read_scores(result, work.precedent_hits))


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-02 [python-coder]: human-stated text and conditions reach Jev's constraints labelled.
#   (#KernelChoiceWithCondition)
# - 2026-10-01 [python-coder]: One `precedent.<decision id>` noul per precedent candidate rides the
#   assessment batch (no extra Jev call) while the decision has an assessment to send; Jev only
#   judges whether the earlier decision applies. (#KernelDecisionStore)
# - 2026-10-01 [python-coder]: The criterion-kind question is rewritten literally (template v2):
#   round 6 gave P(design_judgement) 0.12 to 0.54 for criteria that plainly describe the proposed
#   designs, because the old wording asked for a vague weighing ("simplicity, fit"). It now names
#   the two readings with a boundary example each. (#KernelV01/E)
# - 2026-10-01 [python-coder]: The batch also classifies each not-yet-classified criterion (one
#   `kind.<id>` question, no extra Jev call): a design judgement is a property of the options
#   that retrieval cannot settle. (#KernelV01/A)
# - 2026-10-02 [python-coder]: mypy: the quoted Jev state is built with JSON-typed values (#KernelBootstrapV0/GROUND)
# - 2026-09-30 23:00 [python-coder]: Evidence carries a `role` (decision_basis or pattern_only)
#   in the quoted state so Jev sees that an existing implementation is a pattern, not proof.
#   (#KernelBootstrapV0/P5)
# ====================================================================
