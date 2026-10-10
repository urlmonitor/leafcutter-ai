"""
MODULE: kernel.memory.record_sections
GOAL: The pattern constants and the sub-models of a decision record: task context, options,
    criteria, evidence references, assessment, approval, provenance, precedents and corrections.
BUSINESS CONTEXT: A record is filed only for a decision a human approved (ADR-060); each section
    says what a later reader needs to trust, review or correct that decision.
ARCHITECTURE: Frozen, extra-forbidding Pydantic models with no kernel imports (the package stays
    a leaf). Split out of `kernel.memory.models`, which re-exports every name, to stay under the
    file-size limit; `DecisionRecord` composes these sections there.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0"
DECISION_ID_PATTERN = r"^dec-[0-9a-f]{16}$"
STABLE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
#: A human actor: the bare `human` or `human:<id>`. Anything else (host, jev, service) is refused.
HUMAN_ACTOR_PATTERN = r"^human(:[A-Za-z0-9][A-Za-z0-9._@-]{0,127})?$"
TIMESTAMP_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$"
SLUG_PATTERN = r"^[a-z][a-z0-9_]{0,63}$"
HEX_PATTERN = r"^[0-9a-f]{8,128}$"
PrecedentAction = Literal["used_as_evidence", "offered_for_reuse", "reused", "set_aside",
                          "not_applicable"]


class _Model(BaseModel):
    """Frozen, extra-forbidding base of every record section."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True,
                              use_attribute_docstrings=True)


class SourceRevision(_Model):
    """Repository revision a fact was read at (commit plus dirty flag)."""

    commit: str | None = None
    (
        "Commit the fact was read at, so a later reader can tell whether the repository has "
        "moved on."
    )
    dirty: bool = False
    """True when the working tree differed from that commit."""


class TaskContext(_Model):
    """What the run was asked and where (concept section 15 `task_context`)."""

    goal: str = Field(min_length=1)
    """What the run was asked, in the caller's words."""
    component_ids: list[str] = Field(default_factory=list)
    """Components the task concerned, to find the record again by component."""
    technologies: list[str] = Field(default_factory=list)
    """Technologies the task involved, as context for judging whether the decision still applies."""
    constraints: list[str] = Field(default_factory=list)
    """Constraints the task stated, which the chosen option had to respect."""


class RecordOption(_Model):
    """One option that was weighed; assumptions are kept verbatim (never edited later)."""

    id: str = Field(pattern=STABLE_ID_PATTERN)
    """Stable id the selection and the criteria evidence refer to."""
    title: str = Field(min_length=1)
    """Short name of the option."""
    description: str = ""
    """What the option meant in practice."""
    assumptions: list[str] = Field(default_factory=list)
    (
        "Premises the option relied on, kept verbatim so a later reader can check whether they "
        "still hold."
    )
    evidence_ids: list[str] = Field(default_factory=list)
    """Evidence the option cites, resolved in the record's evidence list."""
    proposed_by: str | None = None
    """Actor that proposed the option."""
    approved_by: str | None = None
    """Actor that approved the option."""


class RecordCriterion(_Model):
    """One criterion the options were weighed against."""

    id: str = Field(pattern=STABLE_ID_PATTERN)
    """Stable id of the criterion within this record."""
    question: str = Field(min_length=1)
    """The question each option was weighed against."""
    priority: Literal["required", "supporting"] = "required"
    """Whether the criterion was required for a decision or only supporting."""
    kind: Literal["evidence_answerable", "design_judgement"] = "evidence_answerable"
    (
        "Whether evidence could settle the criterion or it was a judgement of the designs "
        "themselves."
    )
    evidence_ids: list[str] = Field(default_factory=list)
    """Evidence cited for the criterion, resolved in the record's evidence list."""


class RecordEvidence(_Model):
    """A reference to one evidence item: where it was read, its hash and the revision (no text)."""

    id: str = Field(pattern=STABLE_ID_PATTERN)
    """Evidence id the options and criteria cite."""
    locator: str = Field(min_length=1)
    """Where the evidence was read, so it can be found again; the text itself is not stored."""
    category: str = Field(min_length=1)
    """Kind of evidence (guidance, prior decision, existing pattern, ...)."""
    content_hash: str = Field(pattern=HEX_PATTERN)
    """Hash of the text at the time, so a later reader can tell whether the source changed."""
    verification: str = "unverified"
    """How far the text was checked against its source."""
    relevance: float | None = Field(default=None, ge=0.0, le=1.0)
    """Judged relevance to the question (0 to 1)."""
    source_version: SourceRevision | None = None
    """Repository revision the evidence was read at."""


class RankedOption(_Model):
    """One option's place in the kernel ranking shown to the human (evidence, never authority)."""

    option_id: str = Field(pattern=STABLE_ID_PATTERN)
    """The option this ranking entry describes."""
    rank: int = Field(ge=1)
    """Position in the kernel ranking shown to the human (1 is best); evidence, never authority."""
    required_passed: int | None = Field(default=None, ge=0)
    """How many required criteria the option met at the satisfies threshold."""
    required_total: int | None = Field(default=None, ge=0)
    """How many required criteria were assessed."""
    required_mean: float | None = Field(default=None, ge=0.0, le=1.0)
    """Mean satisfies probability over the required criteria."""
    scores: dict[str, float] = Field(default_factory=dict)
    """Satisfies probability per criterion id behind the ranking."""


class RecordAssessment(_Model):
    """How the decision was assessed: the ranking a human saw, and the model's confidence."""

    basis: Literal["kernel_ranking", "resolved_gate", "precedent_reuse"] = "kernel_ranking"
    (
        "How the outcome came about: from the kernel ranking, a resolved gate, or reuse of a "
        "precedent."
    )
    design_reason: str | None = None
    (
        "Why the kernel stopped researching and handed the ranking to a human; null when it did "
        "not."
    )
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    """The model's confidence in its assessment (0 to 1), when it gave one."""
    selected_rank: int | None = Field(default=None, ge=1)
    (
        "Rank the human's choice held in the ranking shown, so overrides of the ranking are "
        "visible."
    )
    ranking: list[RankedOption] = Field(default_factory=list)
    """The ranking the human saw when choosing."""


class Rationale(_Model):
    """Why the option was chosen; `origin` says who wrote it (a template, never hidden Jev)."""

    text: str = Field(min_length=1)
    """Why the option was chosen."""
    origin: Literal["template", "host"] = "template"
    """Who wrote the text: a kernel template or the host, never hidden model reasoning."""


class FinalOutcome(_Model):
    """What later happened to the decision (concept section 15 `final_outcome`)."""

    status: Literal["pending", "confirmed", "corrected", "abandoned"] = "pending"
    """What later happened to the decision: still pending, confirmed, corrected or abandoned."""
    observed_at: str | None = Field(default=None, pattern=TIMESTAMP_PATTERN)
    """When the outcome was observed (UTC)."""
    note: str = ""
    """What was observed, in a sentence."""


class Approval(_Model):
    """Who approved the decision and when; `approved` is the only status a record can have."""

    approval_status: Literal["approved"]
    """Always approved, because a record is filed only for a decision a human approved."""
    approved_by: str = Field(pattern=HUMAN_ACTOR_PATTERN)
    (
        "The human who approved the decision (`human` or `human:<id>`); a host or service cannot "
        "approve."
    )
    approved_at: str = Field(pattern=TIMESTAMP_PATTERN)
    """When the human approved (UTC)."""
    note: str = ""
    """Anything the approver added, such as a condition."""


class RecordProvenance(_Model):
    """Concept section 12 provenance: where, when and under which versions it was made."""

    origin: Literal["learned"] = "learned"
    """How the record came to exist; learned means the kernel filed it from an approved run."""
    created_by_capability: str = "decision"
    """Capability that produced the decision."""
    created_at: str = Field(pattern=TIMESTAMP_PATTERN)
    """When the record was created (UTC)."""
    run_id: str = Field(min_length=1)
    """Run that produced the decision, to find its trace and artifacts."""
    root_task_id: str | None = None
    """Root task of that run."""
    langfuse_trace_id: str | None = Field(default=None, pattern=HEX_PATTERN)
    """Trace id in Langfuse, for opening the run's trace."""
    langfuse_trace_url: str | None = None
    """Link to the trace in Langfuse."""
    repository_revision: SourceRevision = Field(default_factory=SourceRevision)
    """Repository revision the run read."""
    policy_version: str | None = None
    """Version of the policy under which the decision was made."""
    template_version: str | None = None
    """Version of the prompt templates used."""
    model_version: str | None = None
    """Version of the model that answered."""
    kernel_version: str | None = None
    """Version of the kernel that produced the record."""
    decision_versions: dict[str, str] = Field(default_factory=dict)
    """Versions of the components that took part in the decision, keyed by component."""


class PrecedentNote(_Model):
    """An earlier decision the kernel considered for this one, and what became of it."""

    id: str = Field(pattern=DECISION_ID_PATTERN)
    """Id of the earlier decision that was considered."""
    applicability: float | None = Field(default=None, ge=0.0, le=1.0)
    """Judged probability (0 to 1) that the earlier decision applied."""
    action: PrecedentAction = "used_as_evidence"
    (
        "What became of it: used as evidence, offered for reuse, reused, set aside or not "
        "applicable."
    )
    note: str = ""
    """Why, in a sentence."""


class PreservedOriginal(_Model):
    """What a correction preserves of the original record (never edited, only kept)."""

    selected_option_id: str | None = None
    """Option the record selected before the correction."""
    evidence_ids: list[str] = Field(default_factory=list)
    """Evidence the record cited before the correction."""
    assumptions: list[str] = Field(default_factory=list)
    """Assumptions the record held before the correction."""


class Correction(_Model):
    """One append-only correction: why the decision was corrected, by whom, and what it kept."""

    reason: str = Field(min_length=1)
    """Why the decision was corrected."""
    corrected_at: str = Field(pattern=TIMESTAMP_PATTERN)
    """When the correction was made (UTC)."""
    corrected_by: str = Field(pattern=HUMAN_ACTOR_PATTERN)
    """The human who made the correction."""
    superseded_by: str | None = Field(default=None, pattern=DECISION_ID_PATTERN)
    """Id of the decision that replaces this one, when a new decision was filed."""
    new_selected_option_id: str | None = None
    """Option that now stands, when the correction changes the choice."""
    preserved: PreservedOriginal = Field(default_factory=PreservedOriginal)
    """What the correction keeps of the original record, because records are never edited."""


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-09 [python-coder]: Split out of models.py with a purpose on every record field.
#   (#TICKET-20261009-KernelContractFieldDescriptions)
# ====================================================================
