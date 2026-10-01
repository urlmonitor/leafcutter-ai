"""
MODULE: kernel.capabilities.decision.state
GOAL: The decision capability's continuation model and the per-invocation working state.
BUSINESS CONTEXT: A decision can pause several times (options, criteria approval, research,
    synthesis, a human answer). Everything needed to resume lives in the work item's continuation
    (Rev 3 section 7.4), never on a call stack, so a restarted run re-enters the same phase.
ARCHITECTURE: DecisionContinuation is the JSON-serialisable part (frozen Pydantic model).
    Working is the mutable, in-process merge of payload, continuation and child outcomes that the
    graph nodes read; it is rebuilt on every invocation and never persisted itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import Field

from kernel.contracts.base import KernelModel, canonical_json, sha256_hex
from kernel.contracts.capability import Usage
from kernel.contracts.decision import Criterion, Option
from kernel.contracts.enums import (
    ApprovalStatus,
    EvidenceCategory,
    Priority,
    ProposalStatus,
)
from kernel.contracts.evidence import Evidence


class DecisionContinuation(KernelModel):
    """Persisted decision state (design part 4 fields plus the items an approval needs)."""

    phase: str = "start"
    attempt: int = Field(default=0, ge=0)
    requested: list[str] = Field(default_factory=list)
    options_version: str = ""
    criteria_version: str = ""
    last_assessment_fp: str | None = None
    options: list[Option] = Field(default_factory=list)
    criteria: list[Criterion] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    human_inputs: list[str] = Field(default_factory=list)
    pending_subjects: list[str] = Field(default_factory=list)
    pending_reason: str = ""
    candidate_option_id: str | None = None
    preferred_option_id: str | None = None
    preference_answered: bool = False
    conflict_resolved: bool = False
    decision_approved: bool = False
    approved_by: str | None = None
    approved_revision: str | None = None


def is_pending(item: Option | Criterion) -> bool:
    """True if an option or criterion still awaits approval (and so may not be used)."""
    if item.approval_status is ApprovalStatus.PROPOSED:
        return True
    return (item.proposal_status is ProposalStatus.PROPOSED
            and item.approval_status is not ApprovalStatus.APPROVED
            and item.approval_status is not ApprovalStatus.REJECTED)


def is_usable(item: Option | Criterion) -> bool:
    """True if an option or criterion was supplied or explicitly approved (never rejected)."""
    return item.approval_status is not ApprovalStatus.REJECTED and not is_pending(item)


def version_of(items: list[Option] | list[Criterion]) -> str:
    """Return a short fingerprint of ids and approval state (changes when approval changes)."""
    body = [[i.id, i.proposal_status.value, i.approval_status.value] for i in items]
    return sha256_hex(canonical_json(body))[:12]


@dataclass
class Working:
    """Per-invocation merge of payload, continuation and child outcomes."""

    question: str
    cont: DecisionContinuation
    options: list[Option]
    criteria: list[Criterion]
    approval_required: bool
    constraint_ids: list[str]
    evidence: list[Evidence] = field(default_factory=list)
    missing_evidence_ids: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    usage: list[Usage] = field(default_factory=list)
    approval_rejected: bool = False
    revision_commit: str | None = None

    @property
    def usable_options(self) -> list[Option]:
        """Options that may be selected."""
        return [o for o in self.options if is_usable(o)]

    @property
    def usable_criteria(self) -> list[Criterion]:
        """Criteria that may gate the decision."""
        return [c for c in self.criteria if is_usable(c)]

    @property
    def pending_ids(self) -> list[str]:
        """Ids of options and criteria awaiting approval, options first."""
        return ([o.id for o in self.options if is_pending(o)]
                + [c.id for c in self.criteria if is_pending(c)])

    @property
    def evidence_ids(self) -> list[str]:
        """Ids of the evidence the decision is based on, in order."""
        return [e.id for e in self.evidence]

    @property
    def has_required_criterion(self) -> bool:
        """True if at least one usable criterion is required (only those can gate resolution)."""
        return any(c.priority is Priority.REQUIRED for c in self.usable_criteria)

    @property
    def has_decision_basis(self) -> bool:
        """True if at least one evidence item is more than an existing implementation pattern."""
        return any(e.category is not EvidenceCategory.EXISTING_PATTERNS for e in self.evidence)

    def revision(self) -> str:
        """Return the evidence revision: changes whenever any input to Jev changes."""
        c = self.cont
        body = [sorted(self.evidence_ids), c.findings, c.human_inputs,
                version_of(self.options), version_of(self.criteria)]
        return sha256_hex(canonical_json(body))[:12]


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 02:00 [python-coder]: A decision approval records the evidence revision the human
#   saw (approved_revision); a changed revision or winner voids it. (#KernelBootstrapV0/FIXA)
# - 2026-09-30 23:00 [python-coder]: The continuation stores the option and criterion lists
#   (beyond the design's field list) because approval state changes between invocations and the
#   kernel persists only continuation_state. (#KernelBootstrapV0/P5)
# ====================================================================
