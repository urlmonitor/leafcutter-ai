"""
MODULE: kernel.capabilities.decision.design_ending
GOAL: The human-facing half of the design-decision ending: classify criteria as design judgements,
    turn the kernel ranking into a human question whose choices are the ranked options, and write
    the rationale and per-criterion assessments of the decision the human's choice resolves.
BUSINESS CONTEXT: Retrieval cannot make a property of a proposed design "sufficient", so the
    decision stops researching, shows the ranked options with their scores and evidence in plain
    words, and lets a human choose. The ranking is evidence, never authority (ADR-053).
ARCHITECTURE: Pure functions over Working and the ranking. Followup building lives here, request
    building in requests.py and the result in emit.py, so the modules stay one-way dependent.
"""

from __future__ import annotations

from typing import Literal

from kernel.capabilities.decision.assess import Assessment
from kernel.capabilities.decision.ranking import (
    DESIGN_JUDGEMENT,
    NO_PROGRESS,
    RESEARCH_CAP,
    research_rounds,
)
from kernel.capabilities.decision.requests import Followup, design_choice_request
from kernel.capabilities.decision.state import Working
from kernel.config import DecisionConfig
from kernel.contracts.decision import (
    CriterionAssessment,
    CriterionKind,
    OptionRanking,
    ProviderAnswer,
)
from kernel.contracts.enums import DecisionStatus, MissingKnowledge
from kernel.contracts.interaction import Choice

KIND_SOURCE_JEV = "jev"
DESIGN_PHASE = "awaiting_design_choice"
_WHY = {
    DESIGN_JUDGEMENT: "The required criteria are properties of the proposed options themselves; "
                      "retrieval cannot make them sufficient, so a human judges them.",
    NO_PROGRESS: "Two assessments after new evidence scored (almost) the same; more research "
                 "is not converging, so a human decides.",
    RESEARCH_CAP: "The research-round limit for this decision was reached without a settled "
                  "answer, so a human decides.",
}


def apply_kinds(work: Working, a: Assessment, cfg: DecisionConfig) -> None:
    """Record Jev's classification on every criterion that had none (mutates work.criteria).

    A criterion is a design judgement when Jev's probability reaches design_judgement_threshold;
    an uncertain classification stays evidence_answerable (the behaviour before this ending).
    """
    for index, criterion in enumerate(work.criteria):
        probability = a.design.get(criterion.id)
        if probability is None or criterion.kind_source is not None:
            continue
        kind = (CriterionKind.DESIGN_JUDGEMENT if probability >= cfg.design_judgement_threshold
                else CriterionKind.EVIDENCE_ANSWERABLE)
        work.criteria[index] = criterion.model_copy(update={
            "kind": kind, "kind_source": KIND_SOURCE_JEV})


def band(probability: float, cfg: DecisionConfig) -> str:
    """Return a plain-words reading of a satisfies probability."""
    if probability >= cfg.satisfies_threshold:
        return "likely met"
    if probability <= 1.0 - cfg.satisfies_threshold:
        return "likely not met"
    return "unclear"


def _evidence_words(work: Working, refs: list[str]) -> str:
    """Name the evidence an option cites by where it lives, or say that it cites none."""
    by_id = {e.id: e for e in work.evidence}
    named = [f"{by_id[r].source.title or by_id[r].source.locator} ({r})" if r in by_id else r
             for r in refs]
    return "; ".join(named) if named else "no evidence cited"


def _consequences(work: Working, row: OptionRanking, total: int, cfg: DecisionConfig) -> str:
    """Describe one ranked option: rank, aggregate, per-criterion reading and cited evidence."""
    option = next(o for o in work.options if o.id == row.option_id)
    criteria = "; ".join(
        f"{c.question} {band(row.scores[c.id], cfg)} ({row.scores[c.id]:.2f})"
        for c in work.usable_criteria)
    return (f"Kernel rank {row.rank} of {total}: {row.required_passed} of {row.required_total} "
            f"required criteria likely met, required mean {row.required_mean:.2f}. "
            f"Per criterion: {criteria}. Evidence: {_evidence_words(work, option.source_refs)}.")


def ranked_choices(work: Working, ranking: list[OptionRanking], cfg: DecisionConfig
                   ) -> list[Choice]:
    """Return the ranked options as human choices, best first, scores in plain words."""
    titles = {o.id: o.title for o in work.options}
    return [Choice(id=r.option_id, label=f"#{r.rank} {titles[r.option_id]}",
                   consequences=_consequences(work, r, len(ranking), cfg)) for r in ranking]


def design_followup(work: Working, reason: str, ranking: list[OptionRanking],
                    cfg: DecisionConfig) -> Followup:
    """Build the needs_human follow-up whose choices are the ranked options."""
    cited = [r for o in work.usable_options for r in o.source_refs if r in work.evidence_ids]
    why = _WHY.get(reason, reason)
    question = (
        f"How should '{work.question}' be decided? The kernel ranked the options by Jev's "
        f"judgement of each criterion; the ranking is evidence, not a decision. {why} "
        f"Choose one option, add an option of your own (added_options: title, description) "
        f"or answer in free text.")
    request = design_choice_request(work, question, why, ranked_choices(work, ranking, cfg),
                                    list(dict.fromkeys(cited)))
    return Followup(
        status=DecisionStatus.NEEDS_HUMAN, key=f"design:{reason}:{work.revision()}",
        phase=DESIGN_PHASE, reason=reason, request=request,
        open_question="A human choice among the ranked options is required.",
        missing=[MissingKnowledge.HUMAN_PREFERENCE_OR_AUTHORIZATION])


def ranking_text(work: Working, ranking: list[OptionRanking]) -> str:
    """Return the ranking as one line of text (rank, id, title, aggregate)."""
    titles = {o.id: o.title for o in work.options}
    return "; ".join(f"{r.rank}. [{r.option_id}] {titles.get(r.option_id, '?')} "
                     f"(required mean {r.required_mean:.2f}, {r.required_passed}/"
                     f"{r.required_total} passed)" for r in ranking)


def choice_rationale(work: Working) -> str:
    """Return the rationale that records the kernel ranking and the human's choice."""
    cont = work.cont
    ranking = cont.design_ranking
    rank = next((r.rank for r in ranking if r.option_id == cont.design_choice_id), None)
    title = next(o.title for o in work.options if o.id == cont.design_choice_id)
    where = f"kernel rank {rank} of {len(ranking)}" if rank else "not in the kernel ranking"
    return (f"Design decision settled by a human. Kernel ranking (Jev's per-criterion "
            f"judgement, evidence not authority; stopped researching because "
            f"{cont.design_reason or DESIGN_JUDGEMENT} after {research_rounds(work)} research "
            f"round(s)): {ranking_text(work, ranking)}. {cont.approved_by or 'human'} chose "
            f"option [{cont.design_choice_id}] {title} ({where}).")


def ranking_assessments(work: Working, cfg: DecisionConfig) -> list[CriterionAssessment]:
    """Return the per-option assessments recorded in the ranking the human was shown."""
    out: list[CriterionAssessment] = []
    for row in work.cont.design_ranking:
        for criterion_id, p in row.scores.items():
            outcome: Literal["pass", "fail", "uncertain"] = "uncertain"
            if p >= cfg.satisfies_threshold:
                outcome = "pass"
            elif p <= 1.0 - cfg.satisfies_threshold:
                outcome = "fail"
            out.append(CriterionAssessment(
                criterion_id=criterion_id, option_id=row.option_id, outcome=outcome,
                evidence_ids=work.evidence_ids,
                provider_answer=ProviderAnswer(probabilities={"satisfies": p})))
    return out


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Criterion kind is classified by Jev (a bounded semantic reading, so
#   ADR-053 gives it to Jev, not to code; a code rule such as "generated options mean design
#   criteria" would misfile criteria that quote a repository fact). The human question's choices
#   are the ranked options; the human's choice is what resolves, the ranking is only recorded.
#   (#KernelV01/A)
# ====================================================================
