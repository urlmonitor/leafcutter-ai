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

from typing import Literal

from pydantic import Field, model_validator

from kernel.contracts.base import KernelModel, fail
from kernel.contracts.decision import CriterionAssessment, Criterion, Option, Rationale
from kernel.contracts.enums import ApprovalStatus, DecisionStatus, ProposalStatus
from kernel.contracts.evidence import EvidenceBundlePayload, EvidenceNeed, Finding
from kernel.contracts.interaction import Choice
from kernel.contracts.run import TraceRefs


def _unique(ids: list[str], what: str) -> None:
    """Fail if ids contains duplicates."""
    if len(ids) != len(set(ids)):
        fail(f"duplicate {what} ids")


class GoalRequestPayload(KernelModel):
    """leafcutter.goal_request.v1: a free-form goal for the root capability request."""

    goal: str = Field(min_length=1, max_length=4000)
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


class ResearchRequestPayload(KernelModel):
    """leafcutter.research_request.v1."""

    question: str = Field(min_length=1)
    evidence_needs: list[EvidenceNeed] = Field(default_factory=list)
    source_restrictions: list[str] = Field(default_factory=list)
    existing_evidence_ids: list[str] = Field(default_factory=list)
    expected_coverage: Literal["all_required", "best_effort"] = "all_required"


class RetrievalLimits(KernelModel):
    """Result limits for one retrieval request."""

    top_k: int | None = Field(default=None, ge=1)
    max_chars: int | None = Field(default=None, ge=1)


class RetrievalRequestPayload(KernelModel):
    """leafcutter.retrieval_request.v1."""

    need: EvidenceNeed
    source_ids: list[str] = Field(default_factory=list)
    detail: Literal["excerpt", "summary", "locator"] = "excerpt"
    limits: RetrievalLimits = Field(default_factory=RetrievalLimits)


class OptionsRequestPayload(KernelModel):
    """leafcutter.options_request.v1."""

    problem: str = Field(min_length=1)
    constraint_ids: list[str] = Field(default_factory=list)
    existing_option_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    max_options: int = Field(default=5, ge=0)
    propose_criteria: bool = False


class OptionsPayload(KernelModel):
    """leafcutter.options.v1: every option is a proposal, never pre-approved."""

    options: list[Option] = Field(default_factory=list)
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
        _unique([o.id for o in self.options], "option")
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
    why_research_cannot_settle: str = ""
    decision_id: str | None = None
    subject_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _answerable(self) -> HumanQuestionRequestPayload:
        """Offer choices or allow free text; choice ids must be unique."""
        if not self.choices and not self.free_text_allowed:
            fail("offer choices or allow free text")
        _unique([c.id for c in self.choices], "choice")
        return self


class HumanAnswerPayload(KernelModel):
    """leafcutter.human_answer.v1: exactly one of choice_id or free_text."""

    choice_id: str | None = None
    free_text: str | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> HumanAnswerPayload:
        """Exactly one of choice_id and non-empty free_text must be set."""
        has_text = bool(self.free_text and self.free_text.strip())
        if (self.choice_id is not None) == has_text:
            fail("set exactly one of choice_id and free_text")
        return self


__all__ = [
    "DecisionReportPayload", "DecisionRequestPayload", "EvidenceBundlePayload",
    "FindingsPayload", "GoalRequestPayload", "HumanAnswerPayload",
    "HumanQuestionRequestPayload", "OptionsPayload", "OptionsRequestPayload",
    "ResearchRequestPayload", "RetrievalLimits", "RetrievalRequestPayload",
    "SynthesisLimits", "SynthesisRequestPayload",
]

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:00 [python-coder]: goal_request, human_question_request and human_answer are
#   added to the nine Rev 3 section 7.11 schemas because the root request, human interaction
#   and human answer need registered payloads (design part 2). (#KernelBootstrapV0/P1)
# ====================================================================
