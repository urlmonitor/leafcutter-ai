"""
MODULE: kernel.contracts.decision
GOAL: Options, criteria, assessments, decisions and routing assessments (Rev 3 section 7.7).
BUSINESS CONTEXT: An assessed recommendation is not an approved decision; provider confidence,
    per-option probabilities, evidence coverage and approval status stay separate fields.
ARCHITECTURE: Pure data contracts. Decision and RoutingAssessment carry status invariants so
    an inconsistent record cannot be constructed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

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


class CriterionKind(StrEnum):
    """What can settle a criterion: facts about the world, or a judgement of the designs."""

    #: Settled by facts about the world or the repository; research can make it sufficient.
    EVIDENCE_ANSWERABLE = "evidence_answerable"
    #: A property of the proposed options themselves; retrieval cannot settle it, a human can.
    DESIGN_JUDGEMENT = "design_judgement"


class Option(KernelModel):
    """A candidate answer to a decision question."""

    id: StableId
    """Stable id that criterion assessments and the final selection use to refer to this option."""
    title: str = Field(min_length=1)
    """Short name shown to people choosing between options."""
    description: str = ""
    """What choosing this option means in practice, so it can be judged against the criteria."""
    assumptions: list[str] = Field(default_factory=list)
    (
        "Premises that must hold for this option to be right, kept verbatim so a reader can "
        "challenge them."
    )
    source_refs: list[str] = Field(default_factory=list)
    (
        "Evidence ids or references this option rests on; grounding checks that generated "
        "options cite real evidence."
    )
    proposal_status: ProposalStatus = ProposalStatus.SUPPLIED
    (
        "Whether the caller supplied the option or a generator proposed it, which decides if "
        "approval is needed."
    )
    approval_status: ApprovalStatus = ApprovalStatus.NOT_REQUIRED
    """Where the option stands in the human approval track; a generated option must enter it."""
    proposed_by: str | None = None
    """Actor that proposed the option, for accountability."""
    approved_by: str | None = None
    """Human who approved the option; required once it is approved."""
    named_in_goal: bool = False
    """A host's claim that the caller's goal names this option; the kernel verifies the wording."""

    @model_validator(mode="after")
    def _proposal_needs_approval_track(self) -> Option:
        """A generated (proposed) option is never not_required; approved needs an approver."""
        _check_proposal(self.proposal_status, self.approval_status, self.approved_by)
        return self


class Criterion(KernelModel):
    """A question an option must satisfy; required criteria gate resolution."""

    id: StableId
    """Stable id that assessments and rankings use to refer to this criterion."""
    question: str = Field(min_length=1)
    """The question an option must satisfy, answered from evidence or by judgement."""
    priority: Priority = Priority.REQUIRED
    (
        "Whether the criterion blocks resolution (required) or only adds weight to the ranking "
        "(supporting)."
    )
    scope: str | None = None
    (
        "Optional note on what the criterion applies to when narrower than the decision; carried "
        "for readers, not interpreted by the kernel."
    )
    decision_basis: str | None = None
    (
        "Optional note on the principle or source behind the criterion; carried for readers, not "
        "interpreted by the kernel."
    )
    weight_rule: str | None = None
    (
        "Optional note on how the criterion is weighed against others; carried for readers, not "
        "interpreted by the kernel."
    )
    proposal_status: ProposalStatus = ProposalStatus.SUPPLIED
    (
        "Whether the caller supplied the criterion or a generator proposed it, which decides if "
        "approval is needed."
    )
    approval_status: ApprovalStatus = ApprovalStatus.NOT_REQUIRED
    (
        "Where the criterion stands in the human approval track; a generated criterion must "
        "enter it."
    )
    proposed_by: str | None = None
    """Actor that proposed the criterion, for accountability."""
    approved_by: str | None = None
    """Human who approved the criterion; required once it is approved."""
    kind: CriterionKind = CriterionKind.EVIDENCE_ANSWERABLE
    """Whether evidence can settle this criterion; Jev classifies it once (kind_source "jev")."""
    kind_source: str | None = None
    """Who set `kind`: None means not classified yet (the decision asks Jev once)."""

    @model_validator(mode="after")
    def _proposal_needs_approval_track(self) -> Criterion:
        """A generated (proposed) criterion is never not_required; approved needs an approver."""
        _check_proposal(self.proposal_status, self.approval_status, self.approved_by)
        return self


class ProviderAnswer(KernelModel):
    """Raw provider distribution kept next to the derived outcome."""

    probabilities: dict[str, float] = Field(default_factory=dict)
    (
        "The provider's probability for each answer label, kept so the derived outcome can be "
        "audited."
    )
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    (
        "The provider's own confidence in its answer (0 to 1), compared with the routing and "
        "decision thresholds."
    )
    choice: str | None = None
    """The answer label the provider picked."""


class CriterionAssessment(KernelModel):
    """Outcome of assessing one option (or the evidence) against one criterion."""

    criterion_id: str
    """The criterion that was assessed."""
    option_id: str | None = None
    """The option assessed against the criterion; null when the evidence as a whole was assessed."""
    outcome: Literal["pass", "fail", "uncertain"]
    """Verdict for this pair: pass, fail, or uncertain when the evidence does not settle it."""
    evidence_ids: list[str] = Field(default_factory=list)
    """Evidence the verdict rests on, so the reader can check it."""
    provider_answer: ProviderAnswer | None = None
    """The raw provider distribution behind the verdict, kept for audit."""
    limitations: list[str] = Field(default_factory=list)
    """Caveats on this verdict (thin evidence, cut-off retrieval) that the reader should weigh."""


class OptionRanking(KernelModel):
    """One option's place in the kernel's deterministic ranking (evidence, never authority).

    `scores` are Jev's raw satisfies probabilities keyed by criterion id; the means are over the
    required and the supporting criteria and `required_passed` counts required criteria at or
    above the satisfies threshold. Rank 1 is the best.
    """

    option_id: str
    rank: int = Field(ge=1)
    required_passed: int = Field(ge=0)
    required_total: int = Field(ge=0)
    required_mean: float = Field(ge=0.0, le=1.0)
    supporting_mean: float | None = Field(default=None, ge=0.0, le=1.0)
    scores: dict[str, float] = Field(default_factory=dict)


class Rationale(KernelModel):
    """Concise explanation; origin labels who wrote it (never Jev hidden reasoning)."""

    text: str = Field(min_length=1)
    """The explanation of why the option was chosen, short enough to read in a report."""
    origin: Literal["template", "host"]
    """Who wrote the text: a kernel template or the host, never the provider's hidden reasoning."""


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
    approved_by: str | None = None
    """The human who approved the decision, when a human settled it (a design decision)."""
    design_reason: str | None = None
    (
        "Why the kernel stopped researching and ranked the options for a human (design_judgement, "
        "no_progress, research_cap, no_research_targets, design_round_done, budget_reserve), or "
        "human_ruling when a human chose an option at an escalation (awaiting_human) with no "
        "ranking shown; null while the decision is not a design one."
    )
    approved_at: datetime | None = None
    """When the human approved (UTC); set by the kernel at the human answer, never by a model."""
    precedent_ids: list[str] = Field(default_factory=list)
    (
        "Earlier approved decisions (`dec-<16hex>`) the kernel judged to apply and used as "
        "evidence."
    )

    @field_validator("approved_at")
    @classmethod
    def _approved_at_is_utc(cls, value: datetime | None) -> datetime | None:
        """Reject a naive approval time and normalise to UTC."""
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            fail("approved_at must be timezone-aware (UTC)")
        return value.astimezone(UTC) if value is not None else None

    def differs_from(self, other: Decision) -> bool:
        """True if the two records differ in anything but the clock (one decision, two statuses)."""
        return self.model_dump(exclude={"updated_at"}) != other.model_dump(exclude={"updated_at"})

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
# - 2026-10-09 [python-coder]: Field purposes added; the `#:` field comments became attribute
#   docstrings with the same meaning. (#TICKET-20261009-KernelContractFieldDescriptions)
# - 2026-10-06 [python-coder]: design_reason comment lists human_ruling (a human chose at an
#   escalation). (#KernelChoiceWithCondition)
# - 2026-10-01 [python-coder]: Decision.approved_at (when the human approved) and precedent_ids
#   (earlier decisions used as evidence) back the decision store: a record is filed only from a
#   decision a human approved, and says which precedents it used. (#KernelDecisionStore)
# - 2026-10-01 [python-coder]: Decision.design_reason records why the options were ranked for a
#   human; it was only in the continuation state (the record showed null). (#KernelV01/F)
# - 2026-10-01 [python-coder]: Criterion.kind (evidence_answerable by default) with kind_source,
#   OptionRanking and Decision.approved_by support the design-decision ending: a design
#   judgement cannot be settled by research, so a human chooses among ranked options.
#   (#KernelV01/A)
# - 2026-10-02 [python-coder]: Option.named_in_goal is a host claim the kernel verifies against the
#   goal text before treating the option as caller-supplied. (#KernelBootstrapV0/GROUND)
# - 2026-10-01 23:00 [python-coder]: Decision.differs_from lets the merge update one decision
#   record in place instead of keeping a second record. (#KernelBootstrapV0/GROUND)
# - 2026-09-30 22:00 [python-coder]: Criterion.approval_status defaults to not_required (a
#   caller-supplied criterion); a generated one must carry proposal_status proposed plus an
#   approval_status of proposed, approved or rejected, enforced by _check_proposal.
#   (#KernelBootstrapV0/P1)
# ====================================================================
