"""
MODULE: kernel.capabilities.decision.combine
GOAL: The deterministic `combine` node: the resolved-gate over Jev's answers and the
    classification of whatever is missing when the gate does not open.
BUSINESS CONTEXT: A decision is resolved only when the runtime independently establishes all six
    conditions of Rev 3 section 9.4; a weak probability is never coerced into a decision, there is
    no single readiness number, and a conflict escalates instead of being averaged away.
ARCHITECTURE: Pure function of (Working, Assessment, DecisionConfig). Thresholds come from
    config.decision only. Precedence of needs_*: unknown options, insufficient evidence,
    synthesis (uncertain or conflicting), human (preference, tie, approval).
"""

from __future__ import annotations

from typing import Literal

from dataclasses import dataclass, field, replace

from kernel.capabilities.decision.assess import NONE_CHOICE, Assessment
from kernel.capabilities.decision.ranking import (
    DESIGN_ROUND,
    DESIGN_ROUND_DONE,
    NO_RESEARCH_TARGETS,
    design_reason,
    design_round_done,
    design_round_due,
    loop_reason,
    rank_options,
    required_by_kind,
)
from kernel.capabilities.decision.state import Working
from kernel.config import DecisionConfig
from kernel.contracts.decision import CriterionAssessment, OptionRanking, ProviderAnswer
from kernel.contracts.enums import (
    DecisionStatus,
    EvidenceCategory,
    MissingKnowledge,
    Priority,
)

EVIDENCE_CATEGORY_FOR = {
    MissingKnowledge.MISSING_DECISION_BASIS: EvidenceCategory.PRIOR_DECISIONS,
    MissingKnowledge.MISSING_AUTHORITATIVE_GUIDANCE: EvidenceCategory.AUTHORITATIVE_GUIDANCE,
    MissingKnowledge.MISSING_INTERNAL_PRINCIPLE: EvidenceCategory.INTERNAL_PRINCIPLES,
    MissingKnowledge.MISSING_IMPLEMENTATION_FACT: EvidenceCategory.EXISTING_PATTERNS,
    MissingKnowledge.MISSING_TASK_FACT: EvidenceCategory.TASK_CONTEXT,
}


@dataclass(frozen=True)
class Verdict:
    """Outcome of combine: resolved with an option, or a needs_* status with its reasons."""

    status: DecisionStatus
    selected_option_id: str | None = None
    reason: str = ""
    missing: list[MissingKnowledge] = field(default_factory=list)
    categories: list[EvidenceCategory] = field(default_factory=list)
    tied: list[str] = field(default_factory=list)
    candidate_option_id: str | None = None
    assessments: list[CriterionAssessment] = field(default_factory=list)
    #: Set when the decision stops researching and hands the ranked options to a human.
    ranking: list[OptionRanking] = field(default_factory=list)


def _outcome(p: float, cfg: DecisionConfig) -> Literal["pass", "fail", "uncertain"]:
    """Map a satisfies probability to pass, fail or uncertain using the configured threshold."""
    if p >= cfg.satisfies_threshold:
        return "pass"
    return "fail" if p <= 1.0 - cfg.satisfies_threshold else "uncertain"


def build_assessments(work: Working, a: Assessment, cfg: DecisionConfig
                      ) -> list[CriterionAssessment]:
    """Return the explicit per-criterion assessments (sufficiency and per-option), with raw p."""
    out: list[CriterionAssessment] = []
    for c in work.usable_criteria:
        p = a.sufficient[c.id]
        out.append(CriterionAssessment(
            criterion_id=c.id, outcome="pass" if p >= cfg.sufficiency_threshold else "uncertain",
            evidence_ids=work.evidence_for(c), provider_answer=ProviderAnswer(
                probabilities={"sufficient": p}, confidence=a.sufficient_confidence[c.id])))
        for o in work.usable_options:
            q = a.satisfies[(c.id, o.id)]
            out.append(CriterionAssessment(
                criterion_id=c.id, option_id=o.id, outcome=_outcome(q, cfg),
                evidence_ids=work.evidence_for(c, o),
                provider_answer=ProviderAnswer(
                    probabilities={"satisfies": q},
                    confidence=a.satisfies_confidence[(c.id, o.id)])))
    return out


def classify_missing(a: Assessment, cfg: DecisionConfig, work: Working) -> Verdict:
    """Map Jev's missing-knowledge distribution to a needs_* verdict (application-owned map)."""
    probs = {k: v for k, v in a.missing.probabilities.items() if k != NONE_CHOICE}
    picked = {a.missing.choice} if a.missing.choice != NONE_CHOICE else set()
    picked |= {k for k, v in probs.items() if v >= cfg.missing_min_probability}
    kinds = [m for m in MissingKnowledge if m.value in picked]
    categories = [EVIDENCE_CATEGORY_FOR[m] for m in kinds if m in EVIDENCE_CATEGORY_FOR]
    if not work.has_decision_basis and EvidenceCategory.PRIOR_DECISIONS not in categories:
        categories.append(EvidenceCategory.PRIOR_DECISIONS)
        kinds.append(MissingKnowledge.MISSING_DECISION_BASIS)
    kinds = list(dict.fromkeys(kinds))
    if categories:
        return Verdict(DecisionStatus.NEEDS_EVIDENCE, reason="insufficient_evidence",
                       missing=kinds, categories=categories)
    if MissingKnowledge.CONFLICTING_EVIDENCE in kinds:
        return Verdict(DecisionStatus.NEEDS_SYNTHESIS, reason="conflict", missing=kinds)
    if MissingKnowledge.UNKNOWN_OPTIONS in kinds:
        return Verdict(DecisionStatus.NEEDS_OPTIONS, reason="unknown_options", missing=kinds)
    return Verdict(DecisionStatus.NEEDS_HUMAN, reason="unidentified_gap",
                   missing=kinds or [MissingKnowledge.HUMAN_PREFERENCE_OR_AUTHORIZATION])


def _passing(work: Working, a: Assessment, cfg: DecisionConfig) -> tuple[list[str], list[str]]:
    """Return (options passing every required criterion, options still uncertain)."""
    required = [c for c in work.usable_criteria if c.priority is Priority.REQUIRED]
    passing, uncertain = [], []
    for o in work.usable_options:
        outs = [_outcome(a.satisfies[(c.id, o.id)], cfg) for c in required]
        if all(x == "pass" for x in outs):
            passing.append(o.id)
        elif "fail" not in outs:
            uncertain.append(o.id)
    return passing, uncertain


def _tie_break(work: Working, a: Assessment, cfg: DecisionConfig, passing: list[str]
               ) -> list[str]:
    """Narrow passing options by a human-preferred option, then by supporting criteria passes."""
    preferred = work.cont.preferred_option_id
    if preferred in passing:
        return [preferred]
    supporting = [c for c in work.usable_criteria if c.priority is Priority.SUPPORTING]
    score = {o: sum(_outcome(a.satisfies[(c.id, o)], cfg) == "pass" for c in supporting)
             for o in passing}
    best = max(score.values(), default=0)
    return [o for o in passing if score[o] == best]


def _synthesis_ran(work: Working) -> bool:
    """True if a synthesis request was already emitted for this decision."""
    return any(k.startswith("synthesis:") for k in work.cont.requested)


def _unsettled(work: Working, a: Assessment, cfg: DecisionConfig) -> Verdict | None:
    """Handle conflict and the no-passing-option cases; None when one option passes cleanly."""
    kind, missing = DecisionStatus, MissingKnowledge
    if a.conflict >= cfg.conflict_threshold and not work.cont.conflict_resolved:
        if _synthesis_ran(work):
            return Verdict(kind.NEEDS_HUMAN, reason="conflict",
                           missing=[missing.CONFLICTING_EVIDENCE])
        return Verdict(kind.NEEDS_SYNTHESIS, reason="conflict",
                       missing=[missing.CONFLICTING_EVIDENCE])
    passing, uncertain = _passing(work, a, cfg)
    if passing:
        return None
    if not uncertain:
        return Verdict(kind.NEEDS_OPTIONS, reason="no_option_satisfies",
                       missing=[missing.UNKNOWN_OPTIONS])
    if _synthesis_ran(work):
        return Verdict(kind.NEEDS_HUMAN, reason="uncertain",
                       missing=[missing.HUMAN_PREFERENCE_OR_AUTHORIZATION])
    return Verdict(kind.NEEDS_SYNTHESIS, reason="uncertain",
                   missing=[missing.CONFLICTING_EVIDENCE])


def _approved_for(work: Working, winner: str) -> bool:
    """True only if the human approved this very option at the current evidence revision."""
    cont = work.cont
    return (cont.decision_approved and cont.candidate_option_id == winner
            and cont.approved_revision == work.revision())


def _select(work: Working, a: Assessment, cfg: DecisionConfig) -> Verdict:
    """Pick the single passing option, or escalate a tie, a preference or a missing approval."""
    human = [MissingKnowledge.HUMAN_PREFERENCE_OR_AUTHORIZATION]
    passing, _ = _passing(work, a, cfg)
    winners = _tie_break(work, a, cfg, passing)
    if len(winners) > 1:
        return Verdict(DecisionStatus.NEEDS_HUMAN, reason="tie", tied=winners, missing=human)
    if a.preference >= cfg.preference_threshold and not work.cont.preference_answered:
        return Verdict(DecisionStatus.NEEDS_HUMAN, reason="preference", tied=passing,
                       missing=human)
    if work.approval_required and not _approved_for(work, winners[0]):
        return Verdict(DecisionStatus.NEEDS_HUMAN, reason="decision_approval",
                       candidate_option_id=winners[0], missing=human)
    return Verdict(DecisionStatus.RESOLVED, selected_option_id=winners[0])


def _hand_to_human(work: Working, a: Assessment, cfg: DecisionConfig, reason: str) -> Verdict:
    """Stop researching: rank the options so a human can choose (the design-decision ending)."""
    return Verdict(DecisionStatus.NEEDS_HUMAN, reason=reason,
                   missing=[MissingKnowledge.HUMAN_PREFERENCE_OR_AUTHORIZATION],
                   ranking=rank_options(work, a, cfg))


def _design_research() -> Verdict:
    """Ask for the one targeted research round on the options' claims before they are ranked."""
    return Verdict(DecisionStatus.NEEDS_EVIDENCE, reason=DESIGN_ROUND,
                   missing=[MissingKnowledge.MISSING_IMPLEMENTATION_FACT],
                   categories=[EvidenceCategory.EXISTING_PATTERNS])


def _stop_reason(work: Working) -> str:
    """Name why no design round is due: it already ran, or nothing is targeted to research."""
    return DESIGN_ROUND_DONE if design_round_done(work) else NO_RESEARCH_TARGETS


def combine(work: Working, a: Assessment, cfg: DecisionConfig) -> Verdict:
    """Apply the resolved-gate; otherwise classify what is missing.

    Args:
        work: Working state (usable options and criteria, continuation flags).
        a: Parsed Jev answers.
        cfg: Decision thresholds.

    Returns:
        Verdict: `resolved` with the selected option, or a needs_* status with reasons.
    """
    answerable, _ = required_by_kind(work)
    if not work.has_required_criterion:
        verdict = Verdict(DecisionStatus.NEEDS_OPTIONS, reason="missing_criteria",
                          missing=[MissingKnowledge.UNKNOWN_OPTIONS])
    elif reason := design_reason(work, a, cfg):
        verdict = (_design_research() if design_round_due(work, cfg)
                   else _hand_to_human(work, a, cfg, reason))
    elif not work.has_decision_basis or any(
            a.sufficient[c.id] < cfg.sufficiency_threshold for c in answerable):
        verdict = classify_missing(a, cfg, work)
        reason = loop_reason(work, a, cfg)
        if verdict.status is DecisionStatus.NEEDS_EVIDENCE and reason:
            verdict = _hand_to_human(work, a, cfg, reason)
        elif verdict.reason == "unidentified_gap" and work.usable_options:
            verdict = (_design_research() if design_round_due(work, cfg)
                       else _hand_to_human(work, a, cfg, reason or _stop_reason(work)))
    else:
        verdict = _unsettled(work, a, cfg) or _select(work, a, cfg)
    return replace(verdict, assessments=build_assessments(work, a, cfg))


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-02 [python-coder]: No blind unidentified_gap while options are rankable: run the
#   targeted research round if due, else hand the human the ranked question, naming why research
#   stopped (loop_reason, or no_research_targets when no round is due; never a research cap that
#   was not reached). (#KernelResearchFirst)
# - 2026-10-06 [python-coder]: When the one targeted round already ran below the cap the reason is
#   design_round_done, not no_research_targets: the question no longer claims there was nothing
#   to look up. (#KernelResearchFirst)
# - 2026-10-01 [python-coder]: A criterion assessment cites the evidence relevant to that
#   criterion (and option), not every evidence id (round 8 defect e). (#KernelDecisionStore)
# - 2026-10-01 [python-coder]: A design judgement no longer ranks at once: while a targeted
#   research round is due (ranking.design_round_due) combine asks for it (needs_evidence, reason
#   design_round), and the budget gate may still turn that into the ranked question.
#   (#KernelV01/F)
# - 2026-10-01 [python-coder]: Design judgements, a flat no-progress pair of assessments and the
#   research-round cap end in a ranked human choice (needs_human with a ranking) instead of more
#   research; only evidence-answerable required criteria gate sufficiency. (#KernelV01/A)
# - 2026-10-02 [python-coder]: mypy: _outcome returns the Literal the assessment model requires (#KernelBootstrapV0/GROUND)
# - 2026-10-01 02:00 [python-coder]: The gate refuses to open with no required criterion
#   (all([]) is True), and a decision approval counts only for the option and evidence revision
#   the human saw. (#KernelBootstrapV0/FIXA)
# - 2026-09-30 23:00 [python-coder]: Evidence made only of existing-implementation patterns
#   never opens the gate: it forces a prior_decisions need, because a pattern is not proof.
#   (#KernelBootstrapV0/P5)
# ====================================================================
