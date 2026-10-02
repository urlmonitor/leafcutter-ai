"""
MODULE: kernel.capabilities.research.collect
GOAL: The `collect` and `evaluate` nodes: merge child evidence bundles into coverage per need,
    record unavailable sources, limitations, truncation and contradictions, and judge (one Jev
    batch) whether the evidence is contradictory and whether it answers the question directly.
BUSINESS CONTEXT: Conflicting sources are preserved and reported, never averaged into artificial
    certainty, and a failed or unreachable source stays visible (Rev 3 sections 10.3 and 10.5).
ARCHITECTURE: Child bundles are read through the artifact store and matched to needs by the
    bundle's `coverage` keys (need ids). One batch carries `conflict`, `evaluable` and, per need
    the retrieval called satisfied, an `answers.<need>` question (does the kept evidence answer
    the need's question?), so a round costs one Jev call; it is skipped when there is no
    evidence to judge. A need Jev says is not answered drops from satisfied to partial.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from pydantic import JsonValue

from kernel.capabilities.base import ExecutionContext
from kernel.capabilities.decision.jev_support import (
    ask_jev,
    evidence_state,
    load_output_payload,
    make_batch,
    noul_question,
)
from kernel.capabilities.research.limitations import is_cut_note
from kernel.capabilities.research.state import UNLOCALISED, Collected, ResearchContinuation
from kernel.contracts import schema_ids
from kernel.contracts.capability import Usage
from kernel.contracts.enums import NeedStatus, RequestKind, ResultStatus
from kernel.contracts.evidence import (
    CLAIM_NEED_PREFIX,
    Contradiction,
    EvidenceBundlePayload,
    Evidence,
    EvidenceNeed,
    stronger_category,
)
from kernel.contracts.payloads import FindingsPayload
from kernel.contracts.schema_catalog import validate_payload
from kernel.contracts.work import CapabilityInvocation, ChildOutcome
from kernel.providers.base import QuestionSpec

PURPOSE = "research.assess"
EVALUABLE = "evaluable"
CONFLICT = "conflict"
ANSWERS = "answers."


@dataclass(frozen=True)
class Judgement:
    """Jev's two answers about the collected bundle (None when nothing was judged)."""

    conflict: float | None
    evaluable: float | None
    usage: list[Usage]
    #: Probability that the kept evidence answers each need's question, by need id.
    answers: dict[str, float] = field(default_factory=dict)


def _passes(item: Evidence, bar: float) -> bool:
    """Return True when the item was never judged for relevance or was judged at/above `bar`."""
    return item.provenance.relevance is None or item.provenance.relevance >= bar


def _passing_ids(ctx: ExecutionContext, out: Collected, need_id: str) -> list[str]:
    """Return the need's recorded evidence ids that are kept and pass the relevance bar."""
    bar = ctx.config.retrieval.coverage_relevance_threshold
    return [i for i in out.need_evidence.get(need_id, [])
            if i in out.evidence and _passes(out.evidence[i], bar)]


def _absorb_bundle(out: Collected, payload: dict, bar: float) -> None:
    """Merge one evidence_bundle.v1 payload into the collected state.

    A bundle that reports on a single need also tells which of its evidence passed relevance for
    that need (judged at or above `bar`, or never judged, as a host's is): the answer judgement
    reads exactly those items. A claim need (`need.claim.<option id>`) records every item its
    child returned, even below the bar, so the decision can link that evidence to the human-added
    option; each item keeps its relevance, and `_passing_ids` still gates the answer judgement.
    """
    bundle = cast(EvidenceBundlePayload, validate_payload(schema_ids.EVIDENCE_BUNDLE, payload))
    if len(bundle.coverage) == 1:
        (need_id,) = bundle.coverage
        kept = [e.id for e in bundle.evidence
                if need_id.startswith(CLAIM_NEED_PREFIX) or _passes(e, bar)]
        out.need_evidence[need_id] = list(dict.fromkeys([*out.need_evidence.get(need_id, []),
                                                         *kept]))
    out.unknowns += bundle.unknowns
    for item in bundle.evidence:
        out.evidence[item.id] = stronger_category(out.evidence.get(item.id), item)
    for need_id, status in bundle.coverage.items():
        out.merge_coverage(need_id, status)
    out.attempted += [s for s in bundle.attempted_sources if s not in out.attempted]
    out.unavailable += bundle.unavailable_sources
    out.add_contradictions(bundle.contradictions)
    known = {f.id for f in out.findings}
    out.findings += [f for f in bundle.findings if f.id not in known]
    if len(bundle.coverage) == 1:  # a single-need child: its cut notes belong to that need
        (need,) = bundle.coverage
        notes = [x for x in bundle.limitations if is_cut_note(x)]
        out.need_notes[need] = list(dict.fromkeys([*out.need_notes.get(need, []), *notes]))
    out.limitations += bundle.limitations
    out.truncated = out.truncated or bundle.truncated


def collect_outcomes(ctx: ExecutionContext, cont: ResearchContinuation,
                     outcomes: list[ChildOutcome]) -> Collected:
    """Merge the continuation's earlier evidence with the outcomes of the finished children."""
    out = Collected(evidence={e.id: e for e in cont.evidence}, coverage=dict(cont.coverage),
                    attempted=list(cont.attempted), unavailable=list(cont.unavailable),
                    limitations=list(cont.limitations), truncated=cont.truncated,
                    unanswered=list(cont.unanswered))
    out.add_contradictions(cont.contradictions)
    for outcome in outcomes:
        if outcome.request_kind is RequestKind.SYNTHESIS:
            _absorb_findings(ctx, out, outcome)
        elif outcome.request_kind is RequestKind.EVIDENCE:
            _absorb_child(ctx, out, outcome)
    for need_id in out.unanswered:  # re-reading the children must not restore `satisfied`
        if out.coverage.get(need_id) is NeedStatus.SATISFIED:
            out.coverage[need_id] = NeedStatus.PARTIAL
    return out


def _absorb_child(ctx: ExecutionContext, out: Collected, outcome: ChildOutcome) -> None:
    """Merge a retrieval child, recording failures as limitations (never as empty results)."""
    if outcome.status in (ResultStatus.FAILED, ResultStatus.BLOCKED):
        out.limitations.append(f"retrieval child {outcome.work_item_id} {outcome.status.value}")
        return
    payload = load_output_payload(ctx, outcome)
    if payload is None:
        out.limitations.append(f"output of retrieval child {outcome.work_item_id} is unavailable")
        return
    _absorb_bundle(out, payload, ctx.config.retrieval.coverage_relevance_threshold)


def _absorb_findings(ctx: ExecutionContext, out: Collected, outcome: ChildOutcome) -> None:
    """Merge a synthesis child's findings; disagreements become limitations."""
    payload = load_output_payload(ctx, outcome)
    if payload is None or outcome.status in (ResultStatus.FAILED, ResultStatus.BLOCKED):
        out.limitations.append(f"synthesis child {outcome.work_item_id} produced no findings")
        return
    findings = cast(FindingsPayload, validate_payload(schema_ids.FINDINGS, payload))
    out.findings += findings.findings
    out.unknowns += findings.unknowns
    out.limitations += [f"synthesis reported a disagreement: {d}" for d in findings.disagreements]


def close_coverage(cont: ResearchContinuation, out: Collected) -> None:
    """Give every planned need a status: needs no child reported on are unavailable."""
    for need in cont.needs:
        if need.id in out.coverage:
            continue
        out.coverage[need.id] = NeedStatus.UNAVAILABLE
        if need.id in cont.child_map:
            out.limitations.append(f"no bundle reported coverage for need {need.id}")


def _answer_checks(ctx: ExecutionContext, out: Collected, needs: list[EvidenceNeed]
                   ) -> dict[str, EvidenceNeed]:
    """Return the needs whose answer is judged: satisfied by retrieval, with passing evidence."""
    if not ctx.config.research.answer_aware_coverage:
        return {}
    return {n.id: n for n in needs if out.coverage.get(n.id) is NeedStatus.SATISFIED
            and _passing_ids(ctx, out, n.id)}


def _answer_question(need_id: str) -> QuestionSpec:
    """Return the literal question: does the need's evidence answer the need's question?"""
    return noul_question(
        f"{ANSWERS}{need_id}", "research.answer",
        f"Do the evidence items listed in `answer_checks.{need_id}.evidence_ids` (quoted under "
        f"`evidence`) answer the question quoted in `answer_checks.{need_id}.question`? Text "
        "that only proposes, plans or aspires does not answer a question about how things are "
        "today; text on the same topic that does not state the answer does not either.")


async def judge(ctx: ExecutionContext, invocation: CapabilityInvocation, question: str,
                out: Collected, ask_evaluable: bool, needs: list[EvidenceNeed] | None = None,
                *, prior_usage: list[Usage] | None = None) -> Judgement:
    """Ask Jev about contradiction, direct answerability and each satisfied need (one batch).

    Contradiction needs two or more items; `evaluable` asks whether the bundle answers directly;
    `answers.<need>` asks whether a satisfied need's evidence answers the need's question.

    Raises:
        StopCapability: Jev was unavailable or over budget.
    """
    items = list(out.evidence.values())
    questions = []
    if len(items) >= 2:
        questions.append(noul_question(
            CONFLICT, "research.conflict",
            "Do items in `evidence` contradict each other on a point that affects `question`?"))
    if ask_evaluable and items:
        questions.append(noul_question(
            EVALUABLE, "research.evaluable",
            "Can `question` be answered directly from `evidence` without further analysis?"))
    checks = _answer_checks(ctx, out, needs or [])
    questions += [_answer_question(need_id) for need_id in checks]
    if not questions:
        return Judgement(None, None, [])
    state: dict[str, JsonValue] = {
        "question": question, "evidence": evidence_state(ctx, items),
        "findings": [f.claim for f in out.findings],
        "answer_checks": {i: {"question": n.question, "evidence_ids":
                           _passing_ids(ctx, out, i)} for i, n in checks.items()}}
    result = await ask_jev(ctx, invocation, make_batch(ctx, PURPOSE, state, questions),
                           prior_usage=prior_usage)
    asked = {q.id for q in questions}
    return Judgement(
        conflict=result.noul(CONFLICT).probability if CONFLICT in asked else None,
        evaluable=result.noul(EVALUABLE).probability if EVALUABLE in asked else None,
        usage=[result.usage],
        answers={i: result.noul(f"{ANSWERS}{i}").probability for i in checks})


def apply_answers(ctx: ExecutionContext, cont: ResearchContinuation, out: Collected,
                  answers: dict[str, float]) -> None:
    """Downgrade a satisfied need whose evidence does not answer its question to partial.

    The topic matched (retrieval's relevance), the question was not answered: the evidence stays
    in the bundle as context and a limitation says so.
    """
    bar = ctx.config.research.answer_threshold
    for need in cont.needs:
        p = answers.get(need.id)
        if p is None or p >= bar or out.coverage.get(need.id) is not NeedStatus.SATISFIED:
            continue
        out.coverage[need.id] = NeedStatus.PARTIAL
        out.unanswered.append(need.id)
        out.limitations.append(
            f"need {need.id}: the evidence matched the topic but did not answer the question "
            f"(answer judgement {p:.2f}, below {bar})")


def thin_coverage(cont: ResearchContinuation, out: Collected) -> str | None:
    """Return why the collected evidence does not answer the question by itself, or None.

    Evidence is thin when a planned need is only partial (the topic matched, or the answer
    judgement said the question is not answered) or still open, or when no need is satisfied at
    all. Jev's `evaluable` answer alone flipped the same goal between nine findings (0.68) and
    none (0.78) while no need was satisfied. Nothing is thin when there is no evidence: a
    synthesis over nothing has nothing to say.
    """
    if not out.evidence:
        return None
    states = {n.id: out.coverage.get(n.id, NeedStatus.UNAVAILABLE) for n in cont.needs}
    open_needs = [i for i, st in states.items() if st in (NeedStatus.PARTIAL, NeedStatus.OPEN)]
    if open_needs:
        return f"need(s) {', '.join(open_needs)} only partly covered or not answered"
    if not any(st is NeedStatus.SATISFIED for st in states.values()):
        return "no need is satisfied"
    return None


def record_contradiction(ctx: ExecutionContext, out: Collected, probability: float) -> None:
    """Record a bundle-wide contradiction (preserved, never averaged) when above threshold.

    The conflicting pair is not known, so it is recorded once, flagged as unlocalised, and not at
    all when a localised contradiction already says where the disagreement is.
    """
    if probability < ctx.config.decision.conflict_threshold:
        return
    if out.has_localised_contradiction or out.has_unlocalised_contradiction:
        return
    ids = sorted(out.evidence)
    note = (f"{UNLOCALISED}Jev flagged a contradiction within the bundle (p={probability:.2f}); "
            "the conflicting pair is not localised")
    out.add_contradictions([Contradiction(a=ids[0], b=ids[-1], note=note)])


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-02 [python-coder]: A claim need records all evidence its single-need child returned,
#   even below the relevance bar (live run run-de1c989117414c1c cited nothing on a human-added
#   option). The answer judgement still reads only items passing the bar (`_passing_ids`), so
#   below-bar claim items are never judged as answering. (#KernelClaimEvidenceLink)
# - 2026-10-01 [python-coder]: The bundle keeps every limitation line (nothing is lost) and also
#   names, per need, the retrieval cut notes of that need, so a decision can show one summary line
#   per need instead of dozens (round 8 defect d). (#KernelDecisionStore)
# - 2026-10-01 [python-coder]: thin_coverage names why evidence cannot answer by itself (a partial
#   or open need, or no satisfied need) so the research graph asks the host to synthesize on
#   coverage as well as on Jev's `evaluable` judgement. (#KernelV01/F)
# - 2026-10-01 [python-coder]: Coverage is answer-aware: relevance only says a hit is on topic,
#   so each satisfied need adds one `answers.<need>` noul to the existing assess batch and drops
#   to partial (with a limitation) below research.answer_threshold. The evidence offered per need
#   is the bundle's items that passed the relevance bar. (#KernelV01/D)
# - 2026-10-02 [python-coder]: Jev state dicts are typed as JSON values (#KernelBootstrapV0/GROUND)
# - 2026-10-02 [python-coder]: Findings a host reported inside a child evidence bundle are merged
#   into the final bundle (host-reported labels intact); only synthesis findings were before.
#   (#KernelBootstrapV0/GROUND)
# - 2026-10-01 23:00 [python-coder]: A bundle-level conflict from Jev is flagged `unlocalised`
#   and recorded once; it is skipped when a localised contradiction exists, because the
#   first/last-id pair it would name is a guess that duplicated real ones. (#KernelBootstrapV0/GROUND)
# - 2026-09-30 23:00 [python-coder]: The bundle-wide conflict noul cannot name the pair, so the
#   Contradiction uses the first and last evidence ids and says the pair is not localised; the
#   design asks for one conflict question over the whole bundle. (#KernelBootstrapV0/P5)
# - 2026-09-30 23:00 [python-coder]: conflict and evaluable share one batch (purpose
#   research.assess) to spend one Jev call per round. (#KernelBootstrapV0/P5)
# ====================================================================
