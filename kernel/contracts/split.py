"""
MODULE: kernel.contracts.split
GOAL: The split record (Decomposition) and the two payloads of the host operation
    `host.decompose_goal`: the request the kernel sends and the parts the host proposes.
BUSINESS CONTEXT: ADR-053 and ADR-067: a request that bundles several separate questions is
    offered as a split. The host proposes the parts (generative), Jev only judges, a person
    approves. The record is checkpointed before the run waits, so a restart never creates a
    second split for the same work item.
ARCHITECTURE: Plain KernelModels (frozen, extra-forbidding). The record carries the fields
    delivered by DK-400a-1; later tickets (DK-400c-1, DK-400d-1, DK-400e-1) fill state, parts and
    the gate fields. Ids are derived from the owning work item, never random.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, JsonValue, model_validator

from kernel.contracts.base import KernelModel, fail


class SubjectKind(StrEnum):
    """What a split's subject is."""

    GOAL = "goal"
    RESEARCH_REQUEST = "research_request"
    DECISION_QUESTION = "decision_question"


class FoundAt(StrEnum):
    """Where the bundled subject was found."""

    ROUTING = "routing"
    MID_RUN = "mid_run"


class SplitTrigger(StrEnum):
    """Which routing outcome the bundle judgement was combined with."""

    JEV_NONE = "jev_none"
    AMBIGUOUS = "ambiguous"
    BUNDLED_ACCEPTED = "bundled_accepted"


class KeptRouting(KernelModel):
    """The routing the item would have taken as one decision (bundled_accepted / mid_run)."""

    capability_id: str
    capability_version: str
    routing_assessment_id: str


class Decomposition(KernelModel):
    """The split record: one per split work item (leafcutter.decomposition.v1, detection part)."""

    id: str = Field(pattern=r"^dcp-[0-9a-f]{16}$")
    run_id: str
    work_item_id: str
    subject_kind: SubjectKind
    subject_text: str = Field(min_length=1)
    found_at: FoundAt
    work_item_depth: int = Field(ge=0)
    trigger: SplitTrigger | None = None
    kept_routing: KeptRouting | None = None
    state: str | None = None
    parts: list[dict[str, JsonValue]] = Field(default_factory=list)
    dropped: list[dict[str, JsonValue]] = Field(default_factory=list)
    not_covered: list[dict[str, JsonValue]] = Field(default_factory=list)
    gate_answer: str | None = None
    gate_by: str | None = None
    gate_at: str | None = None
    gate_note: str | None = None
    whole_decision_id: str | None = None
    capability_gap_recorded: bool = False
    report_lines: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _consistent(self) -> Decomposition:
        """Depth 0 iff found at routing; trigger null iff found mid run."""
        if (self.work_item_depth == 0) != (self.found_at is FoundAt.ROUTING):
            fail("work_item_depth is 0 if and only if the subject was found at routing")
        if (self.trigger is None) != (self.found_at is FoundAt.MID_RUN):
            fail("trigger is null if and only if the subject was found mid run")
        needs_kept = self.trigger is SplitTrigger.BUNDLED_ACCEPTED or self.found_at is FoundAt.MID_RUN
        if needs_kept != (self.kept_routing is not None):
            fail("kept_routing is set if and only if the trigger is bundled_accepted or the "
                 "subject was found mid run")
        return self


class GoalDecompositionRequestPayload(KernelModel):
    """leafcutter.goal_decomposition_request.v1: what the host is asked to split."""

    subject_text: str = Field(min_length=1)
    subject_kind: SubjectKind
    max_parts: int = Field(ge=2)
    min_parts: int = Field(default=2, ge=2)
    split_id: str | None = None
    allowed_capabilities: list[str] = Field(default_factory=list)


class PartProposal(KernelModel):
    """One proposed part: a title, a verbatim quote of the subject and its dependencies."""

    title: str = Field(min_length=1)
    quote: str = Field(min_length=1)
    depends_on: list[str] = Field(default_factory=list)


class GoalDecompositionPayload(KernelModel):
    """leafcutter.goal_decomposition.v1: the parts the host proposes (a proposal, never a fact)."""

    parts: list[PartProposal] = Field(min_length=1)
    schema_kind: Literal["proposal"] = "proposal"


__all__ = ["Decomposition", "FoundAt", "GoalDecompositionPayload",
           "GoalDecompositionRequestPayload", "KeptRouting", "PartProposal", "SplitTrigger",
           "SubjectKind"]

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-06 18:00 [python-coder]: New Decomposition split record and the two decomposition payloads. (#TICKET-20261006-DK-400a-1)
# ====================================================================
