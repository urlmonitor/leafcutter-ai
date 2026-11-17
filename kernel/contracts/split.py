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


#: The most parts a proposal may hold; above `split.max_parts` (at most 5) so the cut is visible.
MAX_PROPOSED_PARTS = 12
ChildCapability = Literal["decision", "research"]


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
    """The capability the item would have used had it stayed one decision."""
    capability_version: str
    """Version of that capability, so the kept route can be reproduced."""
    routing_assessment_id: str
    """The routing assessment that chose this route, so the choice can be audited."""


class Decomposition(KernelModel):
    """The split record: one per split work item (leafcutter.decomposition.v1, detection part)."""

    id: str = Field(pattern=r"^dcp-[0-9a-f]{16}$")
    """Identifier of this split, derived from the owning work item so a restart never makes a second one."""
    run_id: str
    """The run this split belongs to."""
    work_item_id: str
    """The work item that was split into parts."""
    subject_kind: SubjectKind
    """What kind of request was split (goal, research request or decision question)."""
    subject_text: str = Field(min_length=1)
    """The exact text that was judged bundled and offered for splitting."""
    found_at: FoundAt
    """Whether the bundle was found at routing or in the middle of a run."""
    work_item_depth: int = Field(ge=0)
    """Depth of the split work item in the run's tree; 0 exactly when found at routing."""
    trigger: SplitTrigger | None = None
    """The routing outcome the bundle judgement was combined with; null when found mid run."""
    kept_routing: KeptRouting | None = None
    """The route the item would have taken whole, used when the person refuses the split."""
    state: str | None = None
    """Where the split stands; null until the host's proposal arrives."""
    parts: list[dict[str, JsonValue]] = Field(default_factory=list)
    """The parts offered to the person, each with its text, quoted words, dependencies and capability."""
    dropped: list[dict[str, JsonValue]] = Field(default_factory=list)
    """Proposed parts the conversion left out, each with the reason it was dropped."""
    not_covered: list[dict[str, JsonValue]] = Field(default_factory=list)
    """Valid parts cut because the part limit was reached, so the person sees what is left over."""
    one_question_rewording: str | None = None
    """The host's suggestion for asking the request as one bounded question; shown as a hint after a jev_none rejection, never run."""
    gate_answer: str | None = None
    """The person's answer at the split gate (approved or rejected); null until answered."""
    gate_by: str | None = None
    """Who gave the gate answer."""
    gate_at: str | None = None
    """When the gate answer was given."""
    gate_note: str | None = None
    """The person's free-text note on the answer."""
    whole_decision_id: str | None = None
    """The staged decision record of the subject when it was decided whole, as one question; null otherwise."""
    capability_gap_recorded: bool = False
    """Whether this split already counted as a capability gap, so the gap is never counted twice."""
    report_lines: list[str] = Field(default_factory=list)
    """Plain-language lines shown to the person about this split in the run report."""

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
    """leafcutter.goal_decomposition_request.v1: what the host is asked to split (ADR-067 4.1)."""

    split_id: str = Field(pattern=r"^dcp-[0-9a-f]{16}$")
    """The split this request belongs to, so the host's reply can be matched to it."""
    subject_kind: SubjectKind
    """What kind of request is to be split, so the host phrases the parts to fit."""
    subject_text: str = Field(min_length=1)
    """The exact text the host must split into separate questions."""
    allowed_capabilities: list[ChildCapability] = Field(
        default_factory=lambda: list[ChildCapability](("decision", "research")), min_length=1)
    """The capabilities a part may use; the host picks one for each part."""
    min_parts: int = Field(default=2, ge=2, le=2)
    """Fewest parts a split may offer; fewer than two is no split."""
    max_parts: int = Field(ge=2, le=5)
    """Most parts the host should offer; the kernel cuts anything above split.max_parts."""


class PartProposal(KernelModel):
    """One proposed part: its id, text, the verbatim span it quotes, dependencies and capability."""

    id: str = Field(min_length=1)
    """Short id other parts cite in depends_on."""
    text: str = Field(min_length=1)
    """The part written as one question that stands alone."""
    covers: str = Field(min_length=1)
    """The words of the request this part quotes verbatim; a part whose quote is not found is dropped."""
    depends_on: list[str] = Field(default_factory=list)
    """Ids of parts that must be settled before this one runs."""
    child_capability: ChildCapability
    """Whether the part is run as a decision or as research."""


class GoalDecompositionPayload(KernelModel):
    """leafcutter.goal_decomposition.v1: the parts the host proposes (a proposal, never a fact).

    Zero parts up to `MAX_PROPOSED_PARTS` are legal: more than `split.max_parts` is cut by the
    conversion, and fewer than two ends the split there (not at the schema).
    """

    parts: list[PartProposal] = Field(max_length=MAX_PROPOSED_PARTS)
    """The parts the host proposes; a proposal the kernel checks, never a fact."""
    one_question_rewording: str | None = None
    """The host's suggestion for asking the request as one bounded question; shown as a hint after a jev_none rejection, never run."""


__all__ = ["MAX_PROPOSED_PARTS", "ChildCapability", "Decomposition", "FoundAt", "GoalDecompositionPayload",
           "GoalDecompositionRequestPayload", "KeptRouting", "PartProposal", "SplitTrigger",
           "SubjectKind"]

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-09 [python-coder]: Replace the placeholder {title, quote} proposal with the ADR-067 4.2 shape {id, text, covers, depends_on, child_capability} plus one_question_rewording, and add the record field one_question_rewording. (#TICKET-20261006-DK-400c-1)
# - 2026-10-06 18:00 [python-coder]: New Decomposition split record and the two decomposition payloads. (#TICKET-20261006-DK-400a-1)
# ====================================================================
