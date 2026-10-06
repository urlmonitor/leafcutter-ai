"""
MODULE: kernel.contracts.payloads
GOAL: Payload models for the twelve registered schema ids (Rev 3 section 7.11 plus the goal,
    human-question and human-answer payloads the kernel needs).
BUSINESS CONTEXT: Named payloads must be validated, not free-form dicts; these models are the
    single definition exported as JSON Schema for clients and checked against fixtures.
ARCHITECTURE: One model per schema id; schema_catalog maps id -> model. Structural checks live
    here, reference checks (cited ids exist) in schema_catalog.validate_semantics.
"""

from __future__ import annotations

from kernel.contracts.verbatim import VerbatimJson, VerbatimString

from typing import Literal

from pydantic import Field, JsonValue, model_validator

from kernel.contracts.base import KernelModel, StableId, fail
from kernel.contracts.decision import CriterionAssessment, Criterion, Option, Rationale
from kernel.contracts.enums import ApprovalStatus, DecisionStatus, Priority, ProposalStatus
from kernel.contracts.evidence import EvidenceBundlePayload, EvidenceNeed, Finding
from kernel.contracts.interaction import Choice
from kernel.contracts.run import TraceRefs


def _unique(ids: list[str], what: str) -> None:
    """Fail if ids contains duplicates."""
    if len(ids) != len(set(ids)):
        fail(f"duplicate {what} ids")


class GoalRequestPayload(KernelModel):
    """leafcutter.goal_request.v1: a free-form goal for the root capability request."""

    goal: VerbatimString = Field(min_length=1, max_length=16000)
    clarifications: list[VerbatimString] = Field(default_factory=list)
    context_summary: str | None = None


class DecisionRequestPayload(KernelModel):
    """leafcutter.decision_request.v1."""

    question: str = Field(min_length=1)
    options: list[Option] = Field(default_factory=list)
    criteria: list[Criterion] = Field(default_factory=list)
    criteria_missing: bool = False
    evidence_ids: list[str] = Field(default_factory=list)
    constraint_ids: list[str] = Field(default_factory=list)
    approval_required: bool = False
    decision_scope: str | None = None

    @model_validator(mode="after")
    def _criteria_or_flag(self) -> DecisionRequestPayload:
        """Criteria must be given or explicitly flagged missing; ids must be unique."""
        if not self.criteria and not self.criteria_missing:
            fail("supply criteria or set criteria_missing=true")
        if self.criteria and self.criteria_missing:
            fail("criteria_missing=true contradicts supplied criteria")
        _unique([o.id for o in self.options], "option")
        _unique([c.id for c in self.criteria], "criterion")
        return self


class DecisionReportPayload(KernelModel):
    """leafcutter.decision_report.v1."""

    status: DecisionStatus
    recommendation: str | None = None
    selected_option_id: str | None = None
    criterion_assessments: list[CriterionAssessment] = Field(default_factory=list)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    approval_status: ApprovalStatus = ApprovalStatus.NOT_REQUIRED
    limitations: list[str] = Field(default_factory=list)
    rationale: Rationale | None = None
    trace_refs: TraceRefs | None = None

    @model_validator(mode="after")
    def _resolved_selects(self) -> DecisionReportPayload:
        """Only a resolved report selects an option; an unresolved one lists open questions."""
        resolved = self.status is DecisionStatus.RESOLVED
        if resolved and self.selected_option_id is None:
            fail("a resolved report must select an option")
        if not resolved and self.selected_option_id is not None:
            fail("an unresolved report cannot select an option")
        return self


class OptionContext(KernelModel):
    """One option the decision researches for: what it is and what it already cites."""

    option_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str | None = None
    #: Evidence ids plus any file paths or symbol names the option's text mentions.
    cited_refs: list[str] = Field(default_factory=list)
    #: True for an option a human added: its claims are unverified and research checks them.
    human_added: bool = False


class ResearchRequestPayload(KernelModel):
    """leafcutter.research_request.v1."""

    question: str = Field(min_length=1)
    #: Original answer obligations; the neutral adapter validates their typed contract.
    answer_requirements: dict[str, JsonValue] | None = None
    #: Scoped supplied evidence interpreted conditionally by the neutral retrieval port.
    assessment: dict[str, VerbatimJson] | None = None
    evidence_needs: list[EvidenceNeed] = Field(default_factory=list)
    source_restrictions: list[str] = Field(default_factory=list)
    existing_evidence_ids: list[str] = Field(default_factory=list)
    expected_coverage: Literal["all_required", "best_effort"] = "all_required"
    #: Research exactly the given needs: Jev adds no further evidence categories.
    evidence_needs_only: bool = False
    #: The options the decision has so far (empty before options exist); research reads it.
    option_context: list[OptionContext] = Field(default_factory=list)
    #: The approved criteria's questions, used as query text beside the goal.
    criteria_context: list[str] = Field(default_factory=list)
    #: Open unknowns (synthesis gaps, research unknowns, option-design feasibility facts);
    #: the first research.max_targeted_needs of them become targeted needs.
    gaps: list[str] = Field(default_factory=list)
    #: Jev calls the requester keeps for itself afterwards (its final assessment); research plans
    #: no more needs than the rest of its budget affords and never spends into this reserve.
    jev_reserve: int = Field(default=0, ge=0)


class RetrievalLimits(KernelModel):
    """Result limits for one retrieval request."""

    top_k: int | None = Field(default=None, ge=1)
    max_chars: int | None = Field(default=None, ge=1)


class RetrievalRequestPayload(KernelModel):
    """leafcutter.retrieval_request.v1."""

    #: Neutral knowledge request fields, fully validated by the capability adapter.
    knowledge: dict[str, VerbatimJson] | None = None
    #: Preserved across research, clarification and progressive source disclosure.
    answer_requirements: dict[str, JsonValue] | None = None
    #: Scoped supplied evidence interpreted conditionally by the neutral retrieval port.
    assessment: dict[str, VerbatimJson] | None = None
    need: EvidenceNeed
    source_ids: list[str] = Field(default_factory=list)
    detail: Literal["excerpt", "summary", "locator"] = "excerpt"
    limits: RetrievalLimits = Field(default_factory=RetrievalLimits)
    #: Exact places to fetch before ranking: `path`, `path#Lx-Ly`, `path#heading`, `path::Symbol`.
    explicit_locators: list[str] = Field(default_factory=list)
    #: Texts to search for before the need's own wording: the goal first, then criteria, options.
    query_hints: list[str] = Field(default_factory=list)
    #: Most rerank batches this request may judge (the requester's Jev budget affords no more
    #: than this beside its reserve); null means the configured `retrieval.rerank_max_batches`.
    max_rerank_batches: int | None = Field(default=None, ge=1)
    #: Jev calls retained for the requester; graph planning must not spend this reserve.
    jev_reserve: int = Field(default=0, ge=0)


class OptionsRequestPayload(KernelModel):
    """leafcutter.options_request.v1."""

    problem: VerbatimString = Field(min_length=1)
    clarifications: list[VerbatimString] = Field(default_factory=list)
    constraint_ids: list[str] = Field(default_factory=list)
    existing_option_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    max_options: int = Field(default=5, ge=0)
    propose_criteria: bool = False
    #: Every proposed option must cite, in `source_refs`, evidence ids from `evidence_ids`.
    require_grounding: bool = False
    #: Accepted synthesis findings as `[id] claim`, so the host does not re-derive them.
    findings: list[str] = Field(default_factory=list)


class OptionsPayload(KernelModel):
    """leafcutter.options.v1: every option is a proposal, never pre-approved."""

    options: list[Option] = Field(default_factory=list)
    #: Options the goal names, verified by the kernel (supplied, never proposals). Kernel-set only.
    named_options: list[Option] = Field(default_factory=list)
    proposed_criteria: list[Criterion] = Field(default_factory=list)
    unresolved_feasibility: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _all_proposed(self) -> OptionsPayload:
        """Generated options must carry proposal_status=proposed and unique ids."""
        if any(o.proposal_status is not ProposalStatus.PROPOSED for o in self.options):
            fail("every generated option must have proposal_status=proposed")
        if any(c.proposal_status is not ProposalStatus.PROPOSED
               for c in self.proposed_criteria):
            fail("every generated criterion must have proposal_status=proposed")
        _unique([o.id for o in [*self.options, *self.named_options]], "option")
        _unique([c.id for c in self.proposed_criteria], "criterion")
        return self


class SynthesisLimits(KernelModel):
    """Analysis limits for a synthesis request."""

    max_findings: int | None = Field(default=None, ge=1)
    max_chars: int | None = Field(default=None, ge=1)


class SynthesisRequestPayload(KernelModel):
    """leafcutter.synthesis_request.v1."""

    operation: str = Field(min_length=1)
    question: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)
    output_requirements: list[str] = Field(default_factory=list)
    limits: SynthesisLimits = Field(default_factory=SynthesisLimits)


class FindingsPayload(KernelModel):
    """leafcutter.findings.v1."""

    findings: list[Finding] = Field(default_factory=list)
    agreements: list[str] = Field(default_factory=list)
    disagreements: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


class HumanQuestionRequestPayload(KernelModel):
    """leafcutter.human_question_request.v1."""

    question: str = Field(min_length=1)
    choices: list[Choice] = Field(default_factory=list)
    free_text_allowed: bool = False
    structured_allowed: bool = False
    why_research_cannot_settle: str = ""
    decision_id: str | None = None
    subject_ids: list[str] = Field(default_factory=list)
    #: Evidence the question rests on (shown to the human as relevant evidence).
    evidence_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _answerable(self) -> HumanQuestionRequestPayload:
        """Offer choices, free text or a structured answer; choice ids must be unique."""
        if not self.choices and not self.free_text_allowed and not self.structured_allowed:
            fail("offer choices or allow free text or a structured answer")
        _unique([c.id for c in self.choices], "choice")
        return self


class CriterionEdit(KernelModel):
    """One criterion the human supplies or edits inside a structured approval answer."""

    id: StableId | None = None
    question: str = Field(min_length=1)
    priority: Priority = Priority.REQUIRED


class AddedOption(KernelModel):
    """One option the human adds inside a structured approval answer."""

    title: str = Field(min_length=1)
    description: str = ""


class HumanAnswerPayload(KernelModel):
    """leafcutter.human_answer.v1: exactly one of choice_id, free_text or a structured answer.

    The structured answer answers an approve-or-edit question about proposed criteria and
    options: `approved_*_ids` approve a subset (the listed ids are approved, every other pending
    proposal of that kind is declined) and `edited_criteria` replaces the pending criteria by the
    human's own (an entry with the id of a proposal edits it, an entry without an id is new).
    """

    choice_id: str | None = None
    free_text: str | None = None
    approved_option_ids: list[str] | None = None
    approved_criterion_ids: list[str] | None = None
    edited_criteria: list[CriterionEdit] | None = Field(default=None, min_length=1)
    #: Options the human adds (they become human-supplied, approved options).
    added_options: list[AddedOption] | None = Field(default=None, min_length=1)

    @property
    def is_structured(self) -> bool:
        """True if any structured approval field is set."""
        return any(v is not None for v in (self.approved_option_ids, self.approved_criterion_ids,
                                           self.edited_criteria, self.added_options))

    @model_validator(mode="after")
    def _exactly_one(self) -> HumanAnswerPayload:
        """Exactly one of choice_id, non-empty free_text and the structured fields must be set."""
        has_text = bool(self.free_text and self.free_text.strip())
        modes = [self.choice_id is not None, has_text, self.is_structured]
        if sum(modes) != 1:
            fail("set exactly one of choice_id, free_text and a structured approval answer")
        if self.approved_criterion_ids is not None and self.edited_criteria is not None:
            fail("approved_criterion_ids and edited_criteria are alternatives")
        _unique(self.approved_option_ids or [], "approved option")
        _unique(self.approved_criterion_ids or [], "approved criterion")
        _unique([e.id for e in self.edited_criteria or [] if e.id], "edited criterion")
        return self


__all__ = [
    "AddedOption", "CriterionEdit", "DecisionReportPayload", "DecisionRequestPayload",
    "EvidenceBundlePayload", "FindingsPayload", "GoalRequestPayload", "HumanAnswerPayload",
    "HumanQuestionRequestPayload", "OptionContext", "OptionsPayload", "OptionsRequestPayload",
    "ResearchRequestPayload", "RetrievalLimits", "RetrievalRequestPayload",
    "SynthesisLimits", "SynthesisRequestPayload",
]

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Research now reads option_context; the request also carries
#   criteria_context and gaps (what a synthesis could not find), OptionContext.human_added marks
#   unverified claims, and retrieval_request.query_hints lets queries lead with the goal.
#   (#KernelV01/D)
# - 2026-10-01 [python-coder]: ResearchRequestPayload.option_context (OptionContext) tells research
#   which options the decision weighs and what they cite; not consumed yet. (#KernelV01/A)
# - 2026-10-02 [python-coder]: OptionsPayload.named_options (kernel-verified, supplied) and
#   HumanAnswerPayload.added_options (human-supplied at approval). (#KernelBootstrapV0/GROUND)
# - 2026-10-02 [python-coder]: HumanQuestionRequestPayload.evidence_ids and
#   OptionsRequestPayload.findings carry cited evidence to the approval question and accepted
#   synthesis findings to the options packet. (#KernelBootstrapV0/GROUND)
# - 2026-10-01 23:00 [python-coder]: OptionsRequestPayload.require_grounding and
#   ResearchRequestPayload.evidence_needs_only support grounded option generation: the first says
#   options must cite the supplied evidence, the second keeps the grounding research to the
#   categories the decision asked for. (#KernelBootstrapV0/GROUND)
# - 2026-09-30 23:30 [python-coder]: human_answer.v1 gains a structured approval answer
#   (approved ids, edited criteria) and the question gains `structured_allowed`; both additive,
#   free text stays as a recorded fallback. (#KernelBootstrapV0/P6)
# - 2026-09-30 22:00 [python-coder]: goal_request, human_question_request and human_answer are
#   added to the nine Rev 3 section 7.11 schemas because the root request, human interaction
#   and human answer need registered payloads (design part 2). (#KernelBootstrapV0/P1)
# - 2026-10-03 15:10 [python-coder]: Preserve verbatim goals and separate meaning, caller and clarification channels. (#DK-300/entity-context)
# ====================================================================

# - 2026-10-01 20:00 [python-coder]: Bind optional knowledge through existing scoped retrieval contracts. (#TICKET-20261001-KM-400e-3)
