"""
MODULE: kernel.capabilities.decision.requests
GOAL: Build the typed child RequestProposals the decision capability emits (options request with
    criteria proposal, approval question, research, synthesis, other human questions) and the
    Followup record that pairs a proposal with its dedup key and resume phase.
BUSINESS CONTEXT: The application, not Jev, maps each kind of missing knowledge to a known
    request template (Rev 3 section 9.5). Options and criteria that an LLM proposes are routed to
    a human approval question before Jev may decide against them (user decision, ADR-053).
ARCHITECTURE: Pure functions returning RequestProposal objects validated by the schema catalog.
    The dedup key is a capability-local string stored in the continuation's `requested` list.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kernel.capabilities.decision.approvals import APPROVE, REJECT
from kernel.capabilities.decision.option_context import option_context
from kernel.capabilities.decision.state import Working, is_pending
from kernel.contracts import schema_ids
from kernel.contracts.decision import Criterion, Option
from kernel.contracts.enums import (
    DecisionStatus,
    EvidenceCategory,
    MissingKnowledge,
    Priority,
    RequestKind,
)
from kernel.contracts.evidence import EvidenceNeed
from kernel.contracts.interaction import Choice
from kernel.contracts.payloads import (
    HumanQuestionRequestPayload,
    OptionsRequestPayload,
    ResearchRequestPayload,
    SynthesisRequestPayload,
)
from kernel.contracts.work import RequestProposal

DEFAULT_MAX_OPTIONS = 5
NAMED_BY = "caller_goal"
SYNTHESIS_OPERATION = "synthesize_evidence"
#: Categories researched to ground options for an unknown option set: what is in scope, how
#: existing material treats the alternatives, and what was decided or prioritised before.
GROUNDING_CATEGORIES = (EvidenceCategory.TASK_CONTEXT, EvidenceCategory.EXISTING_PATTERNS,
                        EvidenceCategory.PRIOR_DECISIONS)
_GROUNDING_QUESTIONS = {
    EvidenceCategory.TASK_CONTEXT: "Which concrete candidates, items and facts in this project "
                                   "are in scope for: ",
    EvidenceCategory.EXISTING_PATTERNS: "How do existing code or documents already describe or "
                                        "rank the alternatives for: ",
    EvidenceCategory.PRIOR_DECISIONS: "Which earlier decisions, priorities or criteria bear on: ",
}
_NEED_QUESTIONS = {
    EvidenceCategory.AUTHORITATIVE_GUIDANCE: "What do the authoritative sources establish about: ",
    EvidenceCategory.INTERNAL_PRINCIPLES: "Which project rules and principles govern: ",
    EvidenceCategory.PRIOR_DECISIONS: "Has this been decided before, and on which assumptions: ",
    EvidenceCategory.EXISTING_PATTERNS: "How do existing code or documents handle: ",
    EvidenceCategory.TASK_CONTEXT: "Which task-specific facts and requirements apply to: ",
    EvidenceCategory.EXTERNAL_PRACTICES: "Which practices or alternatives merit comparison for: ",
}


@dataclass(frozen=True)
class Followup:
    """A needs_* outcome: the child request to emit and how to resume afterwards."""

    status: DecisionStatus
    key: str
    phase: str
    reason: str
    request: RequestProposal
    open_question: str
    missing: list[MissingKnowledge] = field(default_factory=list)
    candidate_option_id: str | None = None


def options_request(work: Working, max_options: int) -> RequestProposal:
    """Ask the host for options and (always) proposed criteria; 0 options means criteria only."""
    cited = work.evidence_ids[:work.evidence_cap]
    payload = OptionsRequestPayload(
        problem=work.question, constraint_ids=work.constraint_ids,
        existing_option_ids=[o.id for o in work.usable_options],
        evidence_ids=cited, max_options=max_options, propose_criteria=True,
        require_grounding=work.require_grounding and max_options > 0 and bool(cited),
        findings=list(work.cont.finding_refs))
    return RequestProposal(
        kind=RequestKind.OPTIONS, question=work.question,
        payload_schema=schema_ids.OPTIONS_REQUEST, payload=payload.model_dump(mode="json"),
        requested_output_schema=schema_ids.OPTIONS)


def grounding_request(work: Working) -> RequestProposal:
    """Ask research for evidence about the option space (exactly the grounding categories)."""
    needs = [EvidenceNeed(id=f"need.{c.value}", category=c, priority=Priority.REQUIRED,
                          question=_GROUNDING_QUESTIONS[c] + work.question)
             for c in GROUNDING_CATEGORIES]
    payload = ResearchRequestPayload(
        question=work.question, evidence_needs=needs, existing_evidence_ids=work.evidence_ids,
        expected_coverage="best_effort", evidence_needs_only=True)
    return RequestProposal(
        kind=RequestKind.EVIDENCE, question=work.question, evidence_needs=needs,
        payload_schema=schema_ids.RESEARCH_REQUEST, payload=payload.model_dump(mode="json"),
        requested_output_schema=schema_ids.EVIDENCE_BUNDLE)


def research_request(work: Working, categories: list[EvidenceCategory], reserve: int = 0
                     ) -> RequestProposal:
    """Ask research for exactly the given evidence categories (needs are pre-filled and required).

    The decision already named the categories it misses, so research plans no further ones (no
    Jev planning call, and the cost of the round is known before it starts); `reserve` is the Jev
    calls the decision keeps for its own final assessment, which research must leave untouched.
    """
    needs = [EvidenceNeed(id=f"need.{c.value}", category=c, priority=Priority.REQUIRED,
                          question=_NEED_QUESTIONS[c] + work.question) for c in categories]
    payload = ResearchRequestPayload(
        question=work.question, evidence_needs=needs, existing_evidence_ids=work.evidence_ids,
        evidence_needs_only=True, jev_reserve=reserve,
        option_context=option_context(work),
        criteria_context=[c.question for c in work.usable_criteria], gaps=list(work.cont.gaps))
    return RequestProposal(
        kind=RequestKind.EVIDENCE, question=work.question, evidence_needs=needs,
        payload_schema=schema_ids.RESEARCH_REQUEST, payload=payload.model_dump(mode="json"),
        requested_output_schema=schema_ids.EVIDENCE_BUNDLE)


def synthesis_request(work: Working, why: str) -> RequestProposal:
    """Ask the host to synthesize the evidence (it may explain a conflict, never resolve it)."""
    payload = SynthesisRequestPayload(
        operation=SYNTHESIS_OPERATION, question=work.question, evidence_ids=work.evidence_ids,
        output_requirements=[why, "explain disagreements without choosing between them"])
    return RequestProposal(
        kind=RequestKind.SYNTHESIS, question=work.question,
        payload_schema=schema_ids.SYNTHESIS_REQUEST, payload=payload.model_dump(mode="json"),
        requested_output_schema=schema_ids.FINDINGS)


def _human(work: Working, question: str, why: str, choices: list[Choice], free_text: bool,
           subjects: list[str], structured: bool = False, evidence: list[str] | None = None
           ) -> RequestProposal:
    """Build a human_question_request proposal."""
    payload = HumanQuestionRequestPayload(
        question=question, choices=choices, free_text_allowed=free_text,
        structured_allowed=structured, why_research_cannot_settle=why, subject_ids=subjects,
        decision_id=work.decision_id or None, evidence_ids=list(evidence or []))
    return RequestProposal(
        kind=RequestKind.HUMAN, question=question,
        payload_schema=schema_ids.HUMAN_QUESTION_REQUEST,
        payload=payload.model_dump(mode="json"),
        requested_output_schema=schema_ids.HUMAN_ANSWER)


def _describe(item: Option | Criterion) -> str:
    """One line describing an option or criterion for a human reader."""
    if not isinstance(item, Option):
        return f"- [{item.id}] {item.question}"
    grounding = (f"grounded in {', '.join(item.source_refs)}" if item.source_refs
                 else "no cited evidence")
    return f"- [{item.id}] {item.title} ({grounding})"


def _cited(options: list[Option]) -> list[str]:
    """Return the union of the evidence ids the options cite, in first-seen order."""
    return list(dict.fromkeys(ref for o in options for ref in o.source_refs))


def approval_request(work: Working) -> RequestProposal:
    """Ask a human to approve (or edit) the proposed options and criteria."""
    options = [o for o in work.options if is_pending(o)]
    criteria = [c for c in work.criteria if is_pending(c)]
    lines = []
    named = [o for o in work.options if o.proposed_by == NAMED_BY and not is_pending(o)]
    if named:
        lines += ["Options taken from your request (usable as given):", *map(_describe, named)]
    if options:
        lines += ["Proposed options:", *map(_describe, options)]
    if criteria:
        lines += ["Proposed criteria:", *map(_describe, criteria)]
    question = (f"For the decision '{work.question}', approve these generated proposals?\n"
                + "\n".join(lines)
                + "\nAnswer 'approve', approve a subset (approved_criterion_ids, "
                "approved_option_ids), supply edited_criteria or add options of your own "
                "(added_options: title, description); free text is only recorded.")
    choice = Choice(id=APPROVE, label="Approve as proposed",
                    consequences="The proposals become usable for the decision.")
    return _human(work, question,
                  "Generated options and criteria are proposals until a human approves them.",
                  [choice], True, [*(c.id for c in criteria), *(o.id for o in options)],
                  structured=True, evidence=_cited(options))


def decision_approval_request(work: Working, option: Option) -> RequestProposal:
    """Ask a human to approve the recommended option before it counts as resolved."""
    question = (f"Approve recommending option [{option.id}] {option.title} for "
                f"'{work.question}'?")
    choices = [Choice(id=APPROVE, label="Approve", consequences="The decision is resolved."),
               Choice(id=REJECT, label="Reject", consequences="The decision is blocked.")]
    return _human(work, question, "The decision requires explicit human approval.", choices,
                  False, [option.id], evidence=_cited([option]))


def design_choice_request(work: Working, question: str, why: str, choices: list[Choice],
                          evidence: list[str]) -> RequestProposal:
    """Ask a human to choose among the kernel-ranked options (or add one, or answer in words)."""
    return _human(work, question, why, choices, True, [c.id for c in choices],
                  structured=True, evidence=evidence)


def escalation_request(work: Working, reason: str, text: str, tied: list[Option]
                       ) -> RequestProposal:
    """Ask a human about a tie, preference, conflict or unidentified gap."""
    choices = [Choice(id=o.id, label=o.title) for o in tied]
    return _human(work, text, f"Escalated: {reason}; evidence and Jev cannot settle it.",
                  choices, True, [o.id for o in tied])


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Decision-driven research plans exactly the categories the decision
#   named and carries the Jev calls the decision reserves, so a round is affordable and bounded
#   before it starts. (#KernelV01/E)
# - 2026-10-01 [python-coder]: A research request also carries the approved criteria's questions
#   and the gaps the last synthesis named, so research can aim its queries. (#KernelV01/D)
# - 2026-10-01 [python-coder]: A research request made after options exist carries
#   option_context (titles, descriptions, cited refs); the grounding request cannot, no options
#   exist yet. (#KernelV01/A)
# - 2026-10-02 [python-coder]: Approval questions list the evidence the options cite, and the
#   options request carries the accepted findings. (#KernelBootstrapV0/GROUND)
# - 2026-10-01 23:00 [python-coder]: An unknown option set is first grounded by a bounded research
#   request (task_context, existing_patterns, prior_decisions), options are then requested WITH
#   that evidence, and the approval question shows what each option cites; every human question
#   carries the decision id. (#KernelBootstrapV0/GROUND)
# - 2026-09-30 23:30 [python-coder]: The approval question accepts a structured answer (subset
#   or edited criteria); free text stays as a recorded fallback. (#KernelBootstrapV0/P6)
# - 2026-09-30 23:00 [python-coder]: The approval question lists option ids after criterion ids
#   in subject_ids; with criteria only it is exactly the proposed criterion ids, as the user
#   decision requires. (#KernelBootstrapV0/P5)
# ====================================================================
