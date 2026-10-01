"""
MODULE: kernel.memory.models
GOAL: The decision record: the model of one reviewable `docs/decisions/<dec-id>.yaml` file, with
    the sub-models for options, criteria, evidence references, assessment, approval, provenance,
    precedents and append-only corrections.
BUSINESS CONTEXT: The record format was decided by the kernel itself (decision
    dec-ef8ddcb79d668a67, "Kernel-contract YAML per decision", approved by the user): its fields
    mirror the kernel `Decision` contract and the colony concept section 15 decision fields, and
    carry concept section 12 provenance. A record exists only because a human approved a
    decision; nothing in it can self-authorize (ADR-060).
ARCHITECTURE: Frozen, extra-forbidding Pydantic models; no kernel contract imports beyond
    pattern constants, so the package stays a leaf. Filters are flat top-level fields (not a
    nested block) because the stdlib knowledge-map parser reads only top-level scalars and block
    lists. Vocabulary membership of the filters is checked in `validate`, not here, because the
    vocabularies live in files that change independently of the model.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class SourceRevision(_Model):
    """Repository revision a fact was read at (commit plus dirty flag)."""

    commit: str | None = None
    dirty: bool = False


class TaskContext(_Model):
    """What the run was asked and where (concept section 15 `task_context`)."""

    goal: str = Field(min_length=1)
    component_ids: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)


class RecordOption(_Model):
    """One option that was weighed; assumptions are kept verbatim (never edited later)."""

    id: str = Field(pattern=STABLE_ID_PATTERN)
    title: str = Field(min_length=1)
    description: str = ""
    assumptions: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    proposed_by: str | None = None
    approved_by: str | None = None


class RecordCriterion(_Model):
    """One criterion the options were weighed against."""

    id: str = Field(pattern=STABLE_ID_PATTERN)
    question: str = Field(min_length=1)
    priority: Literal["required", "supporting"] = "required"
    kind: Literal["evidence_answerable", "design_judgement"] = "evidence_answerable"
    evidence_ids: list[str] = Field(default_factory=list)


class RecordEvidence(_Model):
    """A reference to one evidence item: where it was read, its hash and the revision (no text)."""

    id: str = Field(pattern=STABLE_ID_PATTERN)
    locator: str = Field(min_length=1)
    category: str = Field(min_length=1)
    content_hash: str = Field(pattern=HEX_PATTERN)
    verification: str = "unverified"
    relevance: float | None = Field(default=None, ge=0.0, le=1.0)
    source_version: SourceRevision | None = None


class RankedOption(_Model):
    """One option's place in the kernel ranking shown to the human (evidence, never authority)."""

    option_id: str = Field(pattern=STABLE_ID_PATTERN)
    rank: int = Field(ge=1)
    required_passed: int | None = Field(default=None, ge=0)
    required_total: int | None = Field(default=None, ge=0)
    required_mean: float | None = Field(default=None, ge=0.0, le=1.0)
    scores: dict[str, float] = Field(default_factory=dict)


class RecordAssessment(_Model):
    """How the decision was assessed: the ranking a human saw, and the model's confidence."""

    basis: Literal["kernel_ranking", "resolved_gate", "precedent_reuse"] = "kernel_ranking"
    design_reason: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    selected_rank: int | None = Field(default=None, ge=1)
    ranking: list[RankedOption] = Field(default_factory=list)


class Rationale(_Model):
    """Why the option was chosen; `origin` says who wrote it (a template, never hidden Jev)."""

    text: str = Field(min_length=1)
    origin: Literal["template", "host"] = "template"


class FinalOutcome(_Model):
    """What later happened to the decision (concept section 15 `final_outcome`)."""

    status: Literal["pending", "confirmed", "corrected", "abandoned"] = "pending"
    observed_at: str | None = Field(default=None, pattern=TIMESTAMP_PATTERN)
    note: str = ""


class Approval(_Model):
    """Who approved the decision and when; `approved` is the only status a record can have."""

    approval_status: Literal["approved"]
    approved_by: str = Field(pattern=HUMAN_ACTOR_PATTERN)
    approved_at: str = Field(pattern=TIMESTAMP_PATTERN)
    note: str = ""


class RecordProvenance(_Model):
    """Concept section 12 provenance: where, when and under which versions it was made."""

    origin: Literal["learned"] = "learned"
    created_by_capability: str = "decision"
    created_at: str = Field(pattern=TIMESTAMP_PATTERN)
    run_id: str = Field(min_length=1)
    root_task_id: str | None = None
    langfuse_trace_id: str | None = Field(default=None, pattern=HEX_PATTERN)
    langfuse_trace_url: str | None = None
    repository_revision: SourceRevision = Field(default_factory=SourceRevision)
    policy_version: str | None = None
    template_version: str | None = None
    model_version: str | None = None
    kernel_version: str | None = None
    decision_versions: dict[str, str] = Field(default_factory=dict)


class PrecedentNote(_Model):
    """An earlier decision the kernel considered for this one, and what became of it."""

    id: str = Field(pattern=DECISION_ID_PATTERN)
    applicability: float | None = Field(default=None, ge=0.0, le=1.0)
    action: PrecedentAction = "used_as_evidence"
    note: str = ""


class PreservedOriginal(_Model):
    """What a correction preserves of the original record (never edited, only kept)."""

    selected_option_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class Correction(_Model):
    """One append-only correction: why the decision was corrected, by whom, and what it kept."""

    reason: str = Field(min_length=1)
    corrected_at: str = Field(pattern=TIMESTAMP_PATTERN)
    corrected_by: str = Field(pattern=HUMAN_ACTOR_PATTERN)
    superseded_by: str | None = Field(default=None, pattern=DECISION_ID_PATTERN)
    new_selected_option_id: str | None = None
    preserved: PreservedOriginal = Field(default_factory=PreservedOriginal)


class DecisionRecord(_Model):
    """One filed decision (`docs/decisions/<id>.yaml`), a plain-YAML subset (see module note)."""

    schema_version: Literal["1.0"] = "1.0"
    kind: Literal["decision"] = "decision"
    id: str = Field(pattern=DECISION_ID_PATTERN)
    repository_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = ""
    decision_type: str = Field(pattern=SLUG_PATTERN)
    question: str = Field(min_length=1)
    #: Classification filters, drawn only from the existing vocabularies (see `validate`).
    components: list[str] = Field(default_factory=list)
    change_target: list[str] = Field(default_factory=list)
    risk_surface: list[str] = Field(default_factory=list)
    roadmap_phase: list[str] = Field(default_factory=list)
    file_globs: list[str] = Field(default_factory=list)
    repository_wide: bool = False
    selected_option_id: str = Field(pattern=STABLE_ID_PATTERN)
    supersedes: list[str] = Field(default_factory=list)
    superseded_by: list[str] = Field(default_factory=list)
    related: list[str] = Field(default_factory=list)
    task_context: TaskContext
    rationale: Rationale
    assumptions: list[str] = Field(default_factory=list)
    unresolved_risks: list[str] = Field(default_factory=list)
    assessment: RecordAssessment = Field(default_factory=RecordAssessment)
    final_outcome: FinalOutcome = Field(default_factory=FinalOutcome)
    options: list[RecordOption] = Field(min_length=1)
    criteria: list[RecordCriterion] = Field(default_factory=list)
    evidence: list[RecordEvidence] = Field(default_factory=list)
    precedents_considered: list[PrecedentNote] = Field(default_factory=list)
    approval: Approval
    provenance: RecordProvenance
    corrections: list[Correction] = Field(default_factory=list)

    @model_validator(mode="after")
    def _internally_consistent(self) -> DecisionRecord:
        """Ids are unique, references resolve inside the record, and the record is findable."""
        problems = _inconsistencies(self)
        if problems:
            raise ValueError("; ".join(problems))
        return self

    @property
    def selected_option(self) -> RecordOption:
        """The option the human chose."""
        return next(o for o in self.options if o.id == self.selected_option_id)

    @property
    def filters_empty(self) -> bool:
        """True if no classification filter is set (and the record is not repository-wide)."""
        return not (self.repository_wide or self.components or self.change_target
                    or self.risk_surface or self.roadmap_phase or self.file_globs)


def _duplicates(values: list[str]) -> list[str]:
    """Return the values that occur more than once, sorted."""
    return sorted({v for v in values if values.count(v) > 1})


def _inconsistencies(record: DecisionRecord) -> list[str]:
    """Return every internal inconsistency of a record (empty when it is consistent)."""
    problems = [f"duplicate {what} id {dup}" for what, ids in (
        ("option", [o.id for o in record.options]), ("criterion", [c.id for c in record.criteria]),
        ("evidence", [e.id for e in record.evidence])) for dup in _duplicates(ids)]
    if record.selected_option_id not in {o.id for o in record.options}:
        problems.append(f"selected_option_id {record.selected_option_id} is not an option")
    known = {e.id for e in record.evidence}
    cited = [*(r for o in record.options for r in o.evidence_ids),
             *(r for c in record.criteria for r in c.evidence_ids)]
    problems += [f"cited evidence {r} is not listed under evidence" for r in sorted(set(cited) - known)]
    links = [record.id] if record.id in {*record.supersedes, *record.superseded_by,
                                          *record.related} else []
    problems += [f"record {i} links to itself" for i in links]
    for field, values in (("supersedes", record.supersedes), ("superseded_by", record.superseded_by),
                          ("related", record.related)):
        bad = [v for v in values if not _is_decision_id(v)]
        problems += [f"{field} entry {v!r} is not a dec-<16hex> id" for v in bad]
    if record.filters_empty:
        problems.append("the record has no filter: set a component, change_target, risk_surface, "
                        "roadmap_phase or file_globs entry, or repository_wide")
    return problems


def _is_decision_id(value: str) -> bool:
    """True if value looks like a kernel-minted decision id."""
    return bool(re.fullmatch(DECISION_ID_PATTERN, value))


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Filters are flat top-level fields and the stdlib knowledge-map
#   parser reads id, title, description and the filter lists directly; nested sections are
#   skipped by it. approval_status is the single literal `approved`: a record can only exist
#   for a human-approved decision. (#KernelDecisionStore)
# ====================================================================
