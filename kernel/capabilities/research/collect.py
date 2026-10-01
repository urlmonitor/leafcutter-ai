"""
MODULE: kernel.capabilities.research.collect
GOAL: The `collect` and `evaluate` nodes: merge child evidence bundles into coverage per need,
    record unavailable sources, limitations, truncation and contradictions, and judge (one Jev
    batch) whether the evidence is contradictory and whether it answers the question directly.
BUSINESS CONTEXT: Conflicting sources are preserved and reported, never averaged into artificial
    certainty, and a failed or unreachable source stays visible (Rev 3 sections 10.3 and 10.5).
ARCHITECTURE: Child bundles are read through the artifact store and matched to needs by the
    bundle's `coverage` keys (need ids). One batch carries `conflict` and `evaluable` so a round
    costs one Jev call; it is skipped when there is no evidence to judge.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from kernel.capabilities.base import ExecutionContext
from kernel.capabilities.decision.jev_support import (
    ask_jev,
    evidence_state,
    load_output_payload,
    make_batch,
    noul_question,
)
from kernel.capabilities.research.state import UNLOCALISED, Collected, ResearchContinuation
from kernel.contracts import schema_ids
from kernel.contracts.capability import Usage
from kernel.contracts.enums import NeedStatus, RequestKind, ResultStatus
from kernel.contracts.evidence import Contradiction, EvidenceBundlePayload, stronger_category
from kernel.contracts.payloads import FindingsPayload
from kernel.contracts.schema_catalog import validate_payload
from kernel.contracts.work import CapabilityInvocation, ChildOutcome

PURPOSE = "research.assess"
EVALUABLE = "evaluable"
CONFLICT = "conflict"


@dataclass(frozen=True)
class Judgement:
    """Jev's two answers about the collected bundle (None when nothing was judged)."""

    conflict: float | None
    evaluable: float | None
    usage: list[Usage]


def _absorb_bundle(out: Collected, payload: dict) -> None:
    """Merge one evidence_bundle.v1 payload into the collected state."""
    bundle = cast(EvidenceBundlePayload, validate_payload(schema_ids.EVIDENCE_BUNDLE, payload))
    for item in bundle.evidence:
        out.evidence[item.id] = stronger_category(out.evidence.get(item.id), item)
    for need_id, status in bundle.coverage.items():
        out.merge_coverage(need_id, status)
    out.attempted += [s for s in bundle.attempted_sources if s not in out.attempted]
    out.unavailable += bundle.unavailable_sources
    out.add_contradictions(bundle.contradictions)
    known = {f.id for f in out.findings}
    out.findings += [f for f in bundle.findings if f.id not in known]
    out.limitations += bundle.limitations
    out.truncated = out.truncated or bundle.truncated


def collect_outcomes(ctx: ExecutionContext, cont: ResearchContinuation,
                     outcomes: list[ChildOutcome]) -> Collected:
    """Merge the continuation's earlier evidence with the outcomes of the finished children."""
    out = Collected(evidence={e.id: e for e in cont.evidence}, coverage=dict(cont.coverage),
                    attempted=list(cont.attempted), unavailable=list(cont.unavailable),
                    limitations=list(cont.limitations), truncated=cont.truncated)
    out.add_contradictions(cont.contradictions)
    for outcome in outcomes:
        if outcome.request_kind is RequestKind.SYNTHESIS:
            _absorb_findings(ctx, out, outcome)
        elif outcome.request_kind is RequestKind.EVIDENCE:
            _absorb_child(ctx, out, outcome)
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
    _absorb_bundle(out, payload)


def _absorb_findings(ctx: ExecutionContext, out: Collected, outcome: ChildOutcome) -> None:
    """Merge a synthesis child's findings; disagreements become limitations."""
    payload = load_output_payload(ctx, outcome)
    if payload is None or outcome.status in (ResultStatus.FAILED, ResultStatus.BLOCKED):
        out.limitations.append(f"synthesis child {outcome.work_item_id} produced no findings")
        return
    findings = cast(FindingsPayload, validate_payload(schema_ids.FINDINGS, payload))
    out.findings += findings.findings
    out.limitations += [f"synthesis reported a disagreement: {d}" for d in findings.disagreements]


def close_coverage(cont: ResearchContinuation, out: Collected) -> None:
    """Give every planned need a status: needs no child reported on are unavailable."""
    for need in cont.needs:
        if need.id in out.coverage:
            continue
        out.coverage[need.id] = NeedStatus.UNAVAILABLE
        if need.id in cont.child_map:
            out.limitations.append(f"no bundle reported coverage for need {need.id}")


async def judge(ctx: ExecutionContext, invocation: CapabilityInvocation, question: str,
                out: Collected, ask_evaluable: bool) -> Judgement:
    """Ask Jev about contradiction (two or more items) and whether the bundle answers directly.

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
    if not questions:
        return Judgement(None, None, [])
    state = {"question": question, "evidence": evidence_state(ctx, items),
             "findings": [f.claim for f in out.findings]}
    result = await ask_jev(ctx, invocation, make_batch(ctx, PURPOSE, state, questions))
    asked = {q.id for q in questions}
    return Judgement(
        conflict=result.noul(CONFLICT).probability if CONFLICT in asked else None,
        evaluable=result.noul(EVALUABLE).probability if EVALUABLE in asked else None,
        usage=[result.usage])


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
