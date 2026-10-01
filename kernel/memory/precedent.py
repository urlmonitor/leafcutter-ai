"""
MODULE: kernel.memory.precedent
GOAL: Everything a decision needs to use earlier approved decisions as precedent: the lookup query,
    the literal Jev question per precedent, the verdict (which apply, which to offer for reuse),
    the evidence a precedent becomes, the confirm question wording and the option a reuse resolves
    with.
BUSINESS CONTEXT: Precedent is evidence, never authority (ADR-060). Jev judges whether an earlier
    decision applies to the current question in its context; an applicable one is shown to the
    decision as `prior_decisions` evidence with its approver and date; a strongly applicable one
    is offered to the human, who alone decides to reuse it. Nothing here resolves a decision or
    changes a routing score or threshold.
ARCHITECTURE: Pure functions (the lookup calls the ColonyMemory port) with no dependency on the
    decision capability's internals, so the decision graph imports this module and not the other
    way round. Jev questions are built from `QuestionSpec` directly; the state quotes each
    precedent as one short text, and evidence text is never part of an instruction.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime

from pydantic import JsonValue

from kernel.config_memory import MemoryConfig
from kernel.contracts.base import content_hash, evidence_id
from kernel.contracts.decision import Option
from kernel.contracts.enums import (
    ApprovalStatus,
    EvidenceCategory,
    ProposalStatus,
    SemanticType,
    SourceKind,
    Verification,
)
from kernel.contracts.evidence import Evidence, EvidenceSource, Provenance, SourceVersion
from kernel.contracts.interaction import Choice
from kernel.contracts.task import Scope
from kernel.memory.models import DecisionRecord, PrecedentAction, PrecedentNote
from kernel.memory.port import ColonyMemory, DecisionHit, DecisionQuery
from kernel.providers.base import JevResult, QuestionSpec

logger = logging.getLogger(__name__)

PURPOSE = "decision.precedent"
TEMPLATE_ID = "decision.precedent"
TEMPLATE_VERSION = "1"
QUESTION_PREFIX = "precedent."
REUSE = "reuse"
DECIDE_ANEW = "decide_anew"
SOURCE_ID = "memory.decisions"
PRODUCER = "memory.file"
SUMMARY_CHARS = 900
EXCERPT_CHARS = 2000
INSTRUCTIONS = ("Does the previous decision in `precedents.{id}` apply to the current `question` "
                "in its context?")
CRITERIA = {
    "true": "It answers the same kind of question about the same things, and nothing in the "
            "current `question` or `constraints` contradicts the reasons it was decided.",
    "false": "It is about a different question or a different thing, or the situation it assumed "
             "no longer holds."}
_CONSTRAINT_PHASE = re.compile(r"^\[\w+\]\s+roadmap_phase:\s*(\S+)")


@dataclass(frozen=True)
class PrecedentVerdict:
    """What Jev's judgements mean for a decision: notes, applicable precedents, a reuse offer."""

    notes: list[PrecedentNote] = field(default_factory=list)
    applicable: list[tuple[DecisionHit, float]] = field(default_factory=list)
    offer: DecisionHit | None = None


def phases_from_constraints(constraints: Sequence[str]) -> list[str]:
    """Return the roadmap phases the task's constraints name (`[severity] roadmap_phase: id`)."""
    return [m[1] for text in constraints if (m := _CONSTRAINT_PHASE.match(text))]


def precedent_query(question: str, scope: Scope, constraints: Sequence[str],
                    cfg: MemoryConfig) -> DecisionQuery:
    """Return the lookup query: the question, the task's components and phase where known."""
    return DecisionQuery(
        text=question, components=list(scope.component_ids),
        roadmap_phase=phases_from_constraints(constraints), limit=max(1, cfg.max_precedents),
        min_score=cfg.min_candidate_score)


def find_precedents(memory: ColonyMemory, question: str, scope: Scope,
                    constraints: Sequence[str], cfg: MemoryConfig) -> list[DecisionHit]:
    """Return the precedent candidates for a question (none when memory is off or unreadable)."""
    if cfg.max_precedents < 1:
        return []
    try:
        return memory.find_decisions(precedent_query(question, scope, constraints, cfg))
    except OSError:
        logger.warning("precedent lookup failed; deciding without precedent", exc_info=True)
        return []


def _date(stamp: str) -> str:
    """Return the date part of a record timestamp."""
    return stamp.split("T", 1)[0]


def summary(hit: DecisionHit) -> str:
    """Return the short text Jev sees for one precedent (never evidence text, bounded)."""
    r = hit.record
    option = r.selected_option
    context = "; ".join(filter(None, [
        f"components {', '.join(r.components)}" if r.components else "",
        f"phase {', '.join(r.roadmap_phase)}" if r.roadmap_phase else "",
        "repository-wide" if r.repository_wide else ""]))
    status = f" Superseded by {', '.join(hit.superseded_by or tuple(r.superseded_by))}." \
        if hit.superseded else ""
    corrections = f" Corrections: {len(r.corrections)}." if r.corrections else ""
    text = (f"Question: {r.question} Chosen: {option.title}. {option.description} "
            f"Type: {r.decision_type}. Context: {context or 'unspecified'}. Rationale: "
            f"{r.rationale.text} Approved by {r.approval.approved_by} on "
            f"{_date(r.approval.approved_at)}.{status}{corrections}")
    return " ".join(text.split())[:SUMMARY_CHARS]


def precedent_state(hits: Sequence[DecisionHit]) -> dict[str, JsonValue]:
    """Return the quoted `precedents` state value: record id to its short text."""
    return {h.record.id: summary(h) for h in hits}


def precedent_questions(hits: Sequence[DecisionHit]) -> list[QuestionSpec]:
    """Return one literal noul question per precedent."""
    return [_question(h) for h in hits]


def _question(hit: DecisionHit) -> QuestionSpec:
    """Return the literal noul question for one precedent (its id names the quoted state part)."""
    record_id = hit.record.id
    return QuestionSpec.model_validate({
        "id": f"{QUESTION_PREFIX}{record_id}", "kind": "noul", "template_id": TEMPLATE_ID,
        "template_version": TEMPLATE_VERSION, "instructions": INSTRUCTIONS.format(id=record_id),
        "criteria": dict(CRITERIA)})


def read_scores(result: JevResult, hits: Sequence[DecisionHit]) -> dict[str, float]:
    """Return Jev's applicability probability per precedent id."""
    return {h.record.id: result.noul(f"{QUESTION_PREFIX}{h.record.id}").probability
            for h in hits}


def judge(hits: Sequence[DecisionHit], scores: Mapping[str, float], cfg: MemoryConfig, *,
          can_reuse: bool) -> PrecedentVerdict:
    """Decide what each judgement means: applicable (evidence), not applicable, offered for reuse.

    A precedent is offered for reuse only when `can_reuse` (the decision has no options of its
    own yet), it applies at `reuse_threshold` or more, and no later record superseded it; the
    highest-scoring one is offered.
    """
    applicable = [(h, scores[h.record.id]) for h in hits
                  if scores.get(h.record.id, 0.0) >= cfg.applies_threshold]
    offerable = [(h, p) for h, p in applicable
                 if can_reuse and p >= cfg.reuse_threshold and not h.superseded]
    offer = max(offerable, key=lambda pair: pair[1])[0] if offerable else None
    notes = []
    for hit in hits:
        p = scores.get(hit.record.id)
        if p is None:
            continue
        action: PrecedentAction
        if offer is not None and hit.record.id == offer.record.id:
            action = "offered_for_reuse"
        else:
            action = "used_as_evidence" if p >= cfg.applies_threshold else "not_applicable"
        notes.append(PrecedentNote(id=hit.record.id, applicability=round(p, 4), action=action,
                                   note=_note(hit, action)))
    return PrecedentVerdict(notes=notes, applicable=applicable, offer=offer)


def _note(hit: DecisionHit, action: PrecedentAction) -> str:
    """Return the short note kept next to a precedent in the new record."""
    r = hit.record
    base = f"{r.approval.approved_by} approved [{r.selected_option_id}] on {_date(r.approval.approved_at)}"
    if action == "not_applicable":
        return f"judged not to apply to this question; {base}"
    flag = "; superseded by a later record" if hit.superseded else ""
    return f"{base}{flag}"


def final_links(notes: Sequence[PrecedentNote], *, offer_id: str | None, offer_title: str | None,
                choice: str | None, selected_title: str
                ) -> tuple[list[str], list[str], list[PrecedentNote]]:
    """Return (supersedes, related, final notes) for the record a decision stages.

    Every precedent judged applicable is `related`. The offered precedent's note records the
    human's answer: reused, or set aside (decided anew). A decision that decided anew and chose a
    different option than the precedent did `supersedes` it; the older record is not edited by
    the kernel (an explicit `decisions publish --correct` applies the correction).
    """
    supersedes: list[str] = []
    final: list[PrecedentNote] = []
    for note in notes:
        action, text = note.action, note.note
        if note.id == offer_id and choice == REUSE:
            action, text = "reused", f"reused after the human confirmed it applies; {text}"
        elif note.id == offer_id and choice == DECIDE_ANEW:
            action, text = "set_aside", f"the human decided anew; kept as evidence; {text}"
            if (offer_title or "").strip().lower() != selected_title.strip().lower():
                supersedes.append(note.id)
                text = f"the human decided anew and chose a different option; {text}"
        final.append(note.model_copy(update={"action": action, "note": text}))
    related = [n.id for n in final if n.action != "not_applicable"]
    return supersedes, related, final


def precedent_excerpt(hit: DecisionHit) -> str:
    """Return the evidence text of a precedent: what was asked, chosen, why and by whom."""
    r = hit.record
    option = r.selected_option
    commit = r.provenance.repository_revision.commit
    lines = [
        f"Previous decision {r.id}, approved by {r.approval.approved_by} on "
        f"{_date(r.approval.approved_at)}"
        + (f" at repository revision {commit[:10]}." if commit else "."),
        f"Question: {r.question}", f"Chosen option [{option.id}]: {option.title}. "
        f"{option.description}".rstrip(), f"Rationale: {r.rationale.text}"]
    lines += [f"Assumption: {a}" for a in option.assumptions]
    if hit.superseded:
        lines.append(f"Superseded by: {', '.join(hit.superseded_by or tuple(r.superseded_by))}.")
    lines += [f"Correction ({c.corrected_at}): {c.reason}" for c in r.corrections]
    return "\n".join(lines)[:EXCERPT_CHARS]


def precedent_evidence(hit: DecisionHit, score: float, now: datetime) -> Evidence:
    """Return the `prior_decisions` evidence item of an applicable precedent.

    Its locator is the record's path and its title names the approver, so the provenance of the
    precedent (record path and approved_by) is visible wherever the evidence is cited. The item
    carries no actor of its own: it is a file read, never a human answer.
    """
    r = hit.record
    excerpt = precedent_excerpt(hit)
    digest = content_hash(excerpt)
    revision = r.provenance.repository_revision
    return Evidence(
        id=evidence_id(hit.path, digest), category=EvidenceCategory.PRIOR_DECISIONS,
        semantic_type=SemanticType.REPOSITORY_FACT, excerpt=excerpt, content_hash=digest,
        source=EvidenceSource(
            id=SOURCE_ID, kind=SourceKind.REPOSITORY_FILE, locator=hit.path,
            title=f"Precedent {r.id} approved by {r.approval.approved_by} on "
                  f"{_date(r.approval.approved_at)}",
            source_version=SourceVersion(commit=revision.commit, dirty=revision.dirty),
            retrieved_at=now),
        provenance=Provenance(producer=PRODUCER, strategy="precedent",
                              query=f"approved_by={r.approval.approved_by}", relevance=score),
        verification=Verification.SOURCE_VERIFIED)


def confirm_text(record: DecisionRecord) -> str:
    """Return the literal confirm question the human is asked."""
    return (f"Decision {record.id} (approved by {record.approval.approved_by} on "
            f"{_date(record.approval.approved_at)}) chose {record.selected_option.title} for a "
            "matching question. Reuse it, or decide anew?")


def confirm_choices(record: DecisionRecord) -> list[Choice]:
    """Return the two choices: reuse the precedent's option, or decide anew."""
    title = record.selected_option.title
    return [
        Choice(id=REUSE, label=f"Reuse it: {title}",
               consequences=f"This decision resolves with '{title}', approved by you; precedent "
                            f"{record.id} is cited and a new record is staged for review."),
        Choice(id=DECIDE_ANEW, label="Decide anew",
               consequences="The decision continues normally; the precedent stays as evidence "
                            "and the old record is not edited.")]


def reuse_option(record: DecisionRecord, actor: str, evidence_ids: Sequence[str]) -> Option:
    """Return the option a reuse resolves with: the precedent's choice, approved by `actor`."""
    chosen = record.selected_option
    return Option(
        id=chosen.id, title=chosen.title, description=chosen.description,
        assumptions=list(chosen.assumptions), source_refs=list(evidence_ids),
        proposal_status=ProposalStatus.SUPPLIED, approval_status=ApprovalStatus.APPROVED,
        proposed_by=f"precedent:{record.id}", approved_by=actor)


def reuse_rationale(record: DecisionRecord, actor: str) -> str:
    """Return the rationale text of a reuse: it cites the precedent and the confirming human."""
    return (f"Reused the human-approved precedent {record.id} (approved by "
            f"{record.approval.approved_by} on {_date(record.approval.approved_at)}), which chose "
            f"[{record.selected_option_id}] {record.selected_option.title}. {actor} confirmed that "
            f"it applies to this question. Precedent rationale: {record.rationale.text}")


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Precedent evidence carries no `provenance.actor`: the decision reads
#   the newest actor among its context evidence as "the answering human", and a file a person
#   approved earlier must never be mistaken for that answer. The approver is in the title and the
#   query field instead. (#KernelDecisionStore)
# - 2026-10-01 [python-coder]: A reuse is offered only while the decision has no options of its own
#   and never for a superseded record; with caller-supplied options the precedent is evidence
#   only, because its chosen option may not be one of them. (#KernelDecisionStore)
# ====================================================================
