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

from pydantic import Field, model_validator

from kernel.memory.record_sections import (  # noqa: F401
    Approval,
    Correction,
    DECISION_ID_PATTERN,
    FinalOutcome,
    HEX_PATTERN,
    HUMAN_ACTOR_PATTERN,
    PrecedentAction,
    PrecedentNote,
    PreservedOriginal,
    RankedOption,
    Rationale,
    RecordAssessment,
    RecordCriterion,
    RecordEvidence,
    RecordOption,
    RecordProvenance,
    SCHEMA_VERSION,
    SLUG_PATTERN,
    STABLE_ID_PATTERN,
    SourceRevision,
    TIMESTAMP_PATTERN,
    TaskContext,
    _Model,
)


class DecisionRecord(_Model):
    """One filed decision (`docs/decisions/<id>.yaml`), a plain-YAML subset (see module note)."""

    schema_version: Literal["1.0"] = "1.0"
    """Version of this record format, so a reader can reject a record written for another shape."""
    kind: Literal["decision"] = "decision"
    """Marks the file as a decision record among other documents."""
    id: str = Field(pattern=DECISION_ID_PATTERN)
    """Identifier (`dec-<16 hex>`) that links and precedent lookups refer to this record by."""
    repository_id: str = Field(min_length=1)
    """Repository the decision belongs to; with the id it forms the record's identity key."""
    title: str = Field(min_length=1)
    """Short name shown in the decision index."""
    description: str = ""
    """One-line summary shown in the decision index."""
    decision_type: str = Field(pattern=SLUG_PATTERN)
    """Kind of decision (a slug), so similar decisions can be grouped."""
    question: str = Field(min_length=1)
    """The decision question as asked; precedent lookup matches new questions against it."""
    components: list[str] = Field(default_factory=list)
    """Classification filters, drawn only from the existing vocabularies (see `validate`)."""
    change_target: list[str] = Field(default_factory=list)
    """Kinds of change the decision applies to (a filter drawn from the ticket vocabulary)."""
    risk_surface: list[str] = Field(default_factory=list)
    """Risk surfaces the decision applies to (a filter drawn from the ticket vocabulary)."""
    roadmap_phase: list[str] = Field(default_factory=list)
    """Roadmap phases the decision applies to (a filter)."""
    file_globs: list[str] = Field(default_factory=list)
    """File path patterns the decision applies to (a filter)."""
    repository_wide: bool = False
    """True when the decision applies to the whole repository, so it needs no other filter."""
    selected_option_id: str = Field(pattern=STABLE_ID_PATTERN)
    """Id of the option the human chose; it must be one of the listed options."""
    supersedes: list[str] = Field(default_factory=list)
    """Ids of earlier decisions this one replaces."""
    superseded_by: list[str] = Field(default_factory=list)
    """Ids of later decisions that replace this one."""
    related: list[str] = Field(default_factory=list)
    """Ids of decisions that are linked without replacing each other."""
    task_context: TaskContext
    """What the run was asked and where."""
    rationale: Rationale
    """Why the option was chosen."""
    assumptions: list[str] = Field(default_factory=list)
    """Premises the decision as a whole rests on, kept verbatim for later review."""
    unresolved_risks: list[str] = Field(default_factory=list)
    """Risks that remained open when the decision was made."""
    assessment: RecordAssessment = Field(default_factory=RecordAssessment)
    """How the decision was assessed, including the ranking the human saw."""
    final_outcome: FinalOutcome = Field(default_factory=FinalOutcome)
    """What later happened to the decision."""
    options: list[RecordOption] = Field(min_length=1)
    """The options that were weighed, including the one chosen."""
    criteria: list[RecordCriterion] = Field(default_factory=list)
    """The criteria the options were weighed against."""
    evidence: list[RecordEvidence] = Field(default_factory=list)
    """References to the evidence cited, without the text."""
    precedents_considered: list[PrecedentNote] = Field(default_factory=list)
    """Earlier decisions the kernel considered, and what became of each."""
    approval: Approval
    """Who approved the decision and when."""
    provenance: RecordProvenance
    """Where, when and under which versions the record was made."""
    corrections: list[Correction] = Field(default_factory=list)
    """Append-only corrections made after filing; the original is never edited."""

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
# - 2026-10-09 [python-coder]: The record sections moved to record_sections.py (re-exported here)
#   to fit the file-size limit after field purposes were added; the committed decision_record
#   schema carries them. (#TICKET-20261009-KernelContractFieldDescriptions)
# - 2026-10-01 [python-coder]: Filters are flat top-level fields and the stdlib knowledge-map
#   parser reads id, title, description and the filter lists directly; nested sections are
#   skipped by it. approval_status is the single literal `approved`: a record can only exist
#   for a human-approved decision. (#KernelDecisionStore)
# ====================================================================
