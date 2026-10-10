"""
MODULE: kernel.memory.builder
GOAL: Build a `DecisionRecord` from a resolved, human-approved kernel `Decision` with its options,
    criteria, evidence and provenance; refuse anything a human did not approve.
BUSINESS CONTEXT: Records never self-authorize (ADR-060). The builder is the single gate between
    a kernel decision and a filable record: it requires status resolved, approval approved, a
    human approver and an approval time, and it copies the model's text only into fields that say
    who wrote it. The record keeps the original evidence and assumptions so a later correction
    appends to it instead of rewriting it.
ARCHITECTURE: Pure functions over contract models. `RecordExtras` carries what the Decision does
    not hold (filters, ranking, per-criterion evidence, precedent notes); every extra is
    optional, and a record with no filter at all is filed `repository_wide` so it stays findable.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import NoReturn

from kernel.contracts.decision import Criterion, Decision, Option, OptionRanking
from kernel.contracts.enums import ApprovalStatus, DecisionStatus
from kernel.contracts.evidence import Evidence
from kernel.memory.models import (
    Approval,
    DecisionRecord,
    FinalOutcome,
    PrecedentNote,
    RankedOption,
    Rationale,
    RecordAssessment,
    RecordCriterion,
    RecordEvidence,
    RecordOption,
    RecordProvenance,
    SourceRevision,
    TaskContext,
)

TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
#: Actor ids that are certainly not people (the interaction layer admits only a human actor to a
#: human question; this is defence in depth against a host or service id reaching an approval).
_MACHINE_PREFIXES = ("host", "jev", "service", "kernel", "model", "llm", "system")
#: Title and description stay on one line when dumped (the stdlib knowledge-map parser reads one).
TITLE_FALLBACK_CHARS = 90
DESCRIPTION_CHARS = 90


class NotApproved(ValueError):
    """The decision cannot be filed: a human did not approve a resolved decision."""

    def __init__(self, reason: str) -> None:
        """Keep the reason (also the message)."""
        super().__init__(reason)
        self.reason = reason


def _refuse(reason: str) -> NoReturn:
    """Raise NotApproved with the reason (the single raise site, TRY003)."""
    raise NotApproved(reason)


@dataclass(frozen=True)
class RecordFilters:
    """The classification filters of a record (existing vocabularies only; see `validate`)."""

    components: Sequence[str] = ()
    change_target: Sequence[str] = ()
    risk_surface: Sequence[str] = ()
    roadmap_phase: Sequence[str] = ()
    file_globs: Sequence[str] = ()
    repository_wide: bool = False


@dataclass(frozen=True)
class RecordExtras:
    """What a Decision does not carry but a record does; every field is optional."""

    decision_type: str | None = None
    task_context: TaskContext | None = None
    filters: RecordFilters = field(default_factory=RecordFilters)
    ranking: Sequence[OptionRanking] = ()
    basis: str = "kernel_ranking"
    criterion_evidence: Mapping[str, Sequence[str]] = field(default_factory=dict)
    """Evidence ids relevant to each criterion (defect e: not every id for every criterion)."""
    precedents: Sequence[PrecedentNote] = ()
    related: Sequence[str] = ()
    supersedes: Sequence[str] = ()
    approval_note: str = ""
    description: str | None = None
    """One line for the knowledge map; default: the question cut at a word boundary."""


def human_actor(actor: str | None) -> str | None:
    """Return the actor as a record approver (`human` or `human:<id>`), or None if not a human.

    The interaction layer lets only a human actor answer a human question, so an actor id that
    reaches an approval is a human's; an id without the `human:` prefix (a bare `user`) gets it,
    while an id that names a host, Jev, a service or a model is never treated as a human.
    """
    if not actor:
        return None
    name = actor.strip()
    if name == "human" or name.startswith("human:"):
        return name
    if name.lower().startswith(_MACHINE_PREFIXES):
        return None
    return f"human:{name}"


def one_line(text: str, limit: int) -> str:
    """Return the text on one line, cut at a word boundary with an ellipsis when over `limit`."""
    flat = " ".join(text.split())
    if len(flat) <= limit:
        return flat
    return flat[:limit].rsplit(" ", 1)[0].rstrip(",;:") + " ..."


def utc_timestamp(value: datetime) -> str:
    """Format a timezone-aware datetime as the record's `YYYY-MM-DDTHH:MM:SSZ` string."""
    return value.astimezone(UTC).strftime(TIMESTAMP_FORMAT)


def evidence_ref(item: Evidence | RecordEvidence) -> RecordEvidence:
    """Return the record's evidence reference for an evidence item (no text is copied)."""
    if isinstance(item, RecordEvidence):
        return item
    version = item.source.source_version
    return RecordEvidence(
        id=item.id, locator=item.source.locator, category=item.category.value,
        content_hash=item.content_hash, verification=item.verification.value,
        relevance=item.provenance.relevance,
        source_version=SourceRevision(commit=version.commit, dirty=version.dirty)
        if version else None)


def _approval(decision: Decision, note: str) -> Approval:
    """Return the approval block, refusing anything but a human-approved resolved decision."""
    if decision.status is not DecisionStatus.RESOLVED or not decision.selected_option_id:
        _refuse("only a resolved decision can be filed")
    if decision.approval_status is not ApprovalStatus.APPROVED:
        _refuse("only a decision with approval_status approved can be filed")
    approver = human_actor(decision.approved_by)
    if approver is None:
        _refuse("the decision has no human approver; a record is never self-authorized")
    if decision.approved_at is None:
        _refuse("the decision has no approved_at time")
    return Approval(approval_status="approved", approved_by=approver,
                    approved_at=utc_timestamp(decision.approved_at), note=note)


def _ranking(rows: Sequence[OptionRanking]) -> list[RankedOption]:
    """Convert the kernel ranking to the record's compact form."""
    return [RankedOption(
        option_id=r.option_id, rank=r.rank, required_passed=r.required_passed,
        required_total=r.required_total, required_mean=r.required_mean,
        scores={k: round(v, 4) for k, v in sorted(r.scores.items())}) for r in rows]


def _assessment(decision: Decision, extras: RecordExtras) -> RecordAssessment:
    """Return the assessment block: the ranking the human saw and the selected rank."""
    rows = _ranking(extras.ranking)
    chosen = next((r for r in rows if r.option_id == decision.selected_option_id), None)
    return RecordAssessment(
        basis=extras.basis if extras.basis in ("kernel_ranking", "resolved_gate",  # type: ignore[arg-type]
                                               "precedent_reuse") else "kernel_ranking",
        design_reason=decision.design_reason, confidence=chosen.required_mean if chosen else None,
        selected_rank=chosen.rank if chosen else None, ranking=rows)


def _option(option: Option) -> RecordOption:
    """Convert a kernel option, keeping its assumptions and cited evidence verbatim."""
    return RecordOption(
        id=option.id, title=option.title, description=option.description,
        assumptions=list(option.assumptions), evidence_ids=list(option.source_refs),
        proposed_by=option.proposed_by, approved_by=option.approved_by)


def _criterion(criterion: Criterion, cited: Mapping[str, Sequence[str]]) -> RecordCriterion:
    """Convert a kernel criterion with the evidence relevant to it."""
    return RecordCriterion(
        id=criterion.id, question=criterion.question, priority=criterion.priority.value,
        kind=criterion.kind.value, evidence_ids=list(cited.get(criterion.id, ())))


def build_decision_record(decision: Decision, options: Sequence[Option],
                          criteria: Sequence[Criterion],
                          evidence: Sequence[Evidence | RecordEvidence],
                          provenance: RecordProvenance, *, repository_id: str = "leafcutter-ai",
                          extras: RecordExtras | None = None) -> DecisionRecord:
    """Build the record of a resolved decision a human approved.

    Args:
        decision: The resolved kernel decision (`approved_by` and `approved_at` set by a human).
        options: The options of the decision (the selected one must be among them).
        criteria: The criteria of the decision.
        evidence: Evidence items (or references) the decision rests on; only the ids the decision
            or the extras name are kept.
        provenance: Run, trace, revision and version identity of the run that made it.
        repository_id: The repository key part of the record identity (ADR-061).
        extras: Filters, ranking, per-criterion evidence and precedent notes.

    Returns:
        DecisionRecord: A model-validated record.

    Raises:
        NotApproved: The decision is not resolved, approved, by a human, with an approval time.
    """
    extra = extras or RecordExtras()
    approval = _approval(decision, extra.approval_note)
    wanted = {*decision.evidence_ids, *(i for ids in extra.criterion_evidence.values() for i in ids)}
    refs = [evidence_ref(e) for e in evidence if e.id in wanted]
    option_by_id = {o.id: o for o in options}
    selected = option_by_id[decision.selected_option_id or ""]
    kept = {o.id for o in options if o.id in decision.option_ids} or set(option_by_id)
    f = extra.filters
    wide = f.repository_wide or not (f.components or f.change_target or f.risk_surface
                                     or f.roadmap_phase or f.file_globs)
    return DecisionRecord(
        id=decision.id, repository_id=repository_id, title=one_line(selected.title, TITLE_FALLBACK_CHARS),
        description=extra.description or one_line(decision.question, DESCRIPTION_CHARS),
        decision_type=extra.decision_type or ("design" if decision.design_reason else "selection"),
        question=decision.question, components=list(f.components),
        change_target=list(f.change_target), risk_surface=list(f.risk_surface),
        roadmap_phase=list(f.roadmap_phase), file_globs=list(f.file_globs), repository_wide=wide,
        selected_option_id=selected.id, supersedes=list(extra.supersedes),
        related=list(extra.related),
        task_context=extra.task_context or TaskContext(goal=decision.question),
        rationale=Rationale(text=decision.rationale.text if decision.rationale
                            else f"Option {selected.id} was approved.",
                            origin=decision.rationale.origin if decision.rationale else "template"),
        assumptions=list(selected.assumptions), unresolved_risks=list(decision.unresolved_risks),
        assessment=_assessment(decision, extra), final_outcome=FinalOutcome(),
        options=[_option(o) for o in options if o.id in kept],
        criteria=[_criterion(c, extra.criterion_evidence) for c in criteria
                  if c.id in decision.criterion_ids],
        evidence=refs, precedents_considered=list(extra.precedents), approval=approval,
        provenance=provenance)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: The builder is the self-authorization gate: it refuses a decision
#   that is not resolved, not approved, without a human approver or without approved_at, so no
#   caller can file a record a human did not approve. (#KernelDecisionStore)
# ====================================================================
