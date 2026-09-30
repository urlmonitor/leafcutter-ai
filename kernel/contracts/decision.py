"""
MODULE: kernel.contracts.decision
GOAL: Options, criteria, assessments, decisions and routing assessments (Rev 3 section 7.7).
BUSINESS CONTEXT: An assessed recommendation is not an approved decision; provider confidence,
    per-option probabilities, evidence coverage and approval status stay separate fields.
ARCHITECTURE: Pure data contracts. Decision and RoutingAssessment carry status invariants so
    an inconsistent record cannot be constructed.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from kernel.contracts.base import KernelModel, PersistedModel, StableId, fail
from kernel.contracts.enums import (
    ApprovalStatus,
    DecisionStatus,
    MissingKnowledge,
    Priority,
    ProposalStatus,
    RoutingOutcome,
)


def _check_proposal(proposal: ProposalStatus, approval: ApprovalStatus,
                    approved_by: str | None) -> None:
    """Shared invariant for options and criteria (ADR-053 section 2).

    Whatever generated them (an LLM or a human answer), a proposal must enter an approval track
    and an approval must say who approved.
    """
    if proposal is ProposalStatus.PROPOSED and approval is ApprovalStatus.NOT_REQUIRED:
        fail("a proposed item needs approval_status proposed, approved or rejected")
    if approval is ApprovalStatus.APPROVED and not approved_by:
        fail("an approved item must record approved_by")


class Option(KernelModel):
    """A candidate answer to a decision question."""

    id: StableId
    title: str = Field(min_length=1)
    description: str = ""
    assumptions: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    proposal_status: ProposalStatus = ProposalStatus.SUPPLIED
    approval_status: ApprovalStatus = ApprovalStatus.NOT_REQUIRED
    proposed_by: str | None = None
    approved_by: str | None = None

    @model_validator(mode="after")
    def _proposal_needs_approval_track(self) -> Option:
        """A generated (proposed) option is never not_required; approved needs an approver."""
        _check_proposal(self.proposal_status, self.approval_status, self.approved_by)
        return self


class Criterion(KernelModel):
    """A question an option must satisfy; required criteria gate resolution."""

    id: StableId
    question: str = Field(min_length=1)
    priority: Priority = Priority.REQUIRED
    scope: str | None = None
    decision_basis: str | None = None
    weight_rule: str | None = None
    proposal_status: ProposalStatus = ProposalStatus.SUPPLIED
    approval_status: ApprovalStatus = ApprovalStatus.NOT_REQUIRED
    proposed_by: str | None = None
    approved_by: str | None = None

    @model_validator(mode="after")
    def _proposal_needs_approval_track(self) -> Criterion:
        """A generated (proposed) criterion is never not_required; approved needs an approver."""
        _check_proposal(self.proposal_status, self.approval_status, self.approved_by)
        return self


class ProviderAnswer(KernelModel):
    """Raw provider distribution kept next to the derived outcome."""

    probabilities: dict[str, float] = Field(default_factory=dict)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    choice: str | None = None


class CriterionAssessment(KernelModel):
    """Outcome of assessing one option (or the evidence) against one criterion."""

    criterion_id: str
    option_id: str | None = None
    outcome: Literal["pass", "fail", "uncertain"]
    evidence_ids: list[str] = Field(default_factory=list)
    provider_answer: ProviderAnswer | None = None
    limitations: list[str] = Field(default_factory=list)


class Rationale(KernelModel):
    """Concise explanation; origin labels who wrote it (never Jev hidden reasoning)."""

    text: str = Field(min_length=1)
    origin: Literal["template", "host"]


class Decision(PersistedModel):
    """A decision record: status, selected option, evidence, missing knowledge, approval."""

    question: str = Field(min_length=1)
    option_ids: list[str] = Field(default_factory=list)
    criterion_ids: list[str] = Field(default_factory=list)
    selected_option_id: str | None = None
    status: DecisionStatus
    approval_status: ApprovalStatus = ApprovalStatus.NOT_REQUIRED
    evidence_ids: list[str] = Field(default_factory=list)
    missing: list[MissingKnowledge] = Field(default_factory=list)
    rationale: Rationale | None = None
    versions: dict[str, str] = Field(default_factory=dict)
    unresolved_risks: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _status_invariants(self) -> Decision:
        """Only a resolved decision selects an option, and it must be one that was supplied."""
        if self.status is DecisionStatus.RESOLVED:
            if self.selected_option_id is None:
                fail("a resolved decision must select an option")
            if self.selected_option_id not in self.option_ids:
                fail("selected_option_id must be one of option_ids")
            if self.missing:
                fail("a resolved decision cannot have missing knowledge")
        elif self.selected_option_id is not None:
            fail("only a resolved decision may select an option")
        return self


class ExcludedCandidate(KernelModel):
    """A candidate removed by the deterministic eligibility filter."""

    capability_id: str
    reason_code: str


class RoutingAssessment(PersistedModel):
    """Record of one routing decision, including whether Jev was called."""

    work_item_id: str
    eligible_candidate_ids: list[str] = Field(default_factory=list)
    excluded: list[ExcludedCandidate] = Field(default_factory=list)
    selected: str | None = None
    probabilities: dict[str, float] = Field(default_factory=dict)
    provider_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    template_id: str | None = None
    template_version: str | None = None
    model_id: str | None = None
    evidence_revision: str | None = None
    outcome: RoutingOutcome
    reason_codes: list[str] = Field(default_factory=list)
    thresholds: dict[str, float] = Field(default_factory=dict)
    jev_called: bool = False

    @model_validator(mode="after")
    def _selected_is_eligible(self) -> RoutingAssessment:
        """A selected outcome names an eligible candidate; other outcomes select nothing."""
        if self.outcome is RoutingOutcome.SELECTED:
            if self.selected not in self.eligible_candidate_ids:
                fail("selected candidate must be in eligible_candidate_ids")
        elif self.selected is not None:
            fail("only a selected outcome may name a candidate")
        return self


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:00 [python-coder]: Criterion.approval_status defaults to proposed so a
#   criterion is never silently treated as approved; callers mark supplied criteria approved.
#   (#KernelBootstrapV0/P1)
# ====================================================================
