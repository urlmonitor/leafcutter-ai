"""
MODULE: kernel.capabilities.decision.loading
GOAL: The decision graph's `load` node: merge the request payload, the persisted continuation
    and the outcomes of finished children into one Working state.
BUSINESS CONTEXT: The decision basis is loaded as evidence with explicit scope and revision
    checks; an existing implementation is a pattern, not proof (Rev 3 section 10.1). Proposals
    from children stay proposals until a human approves them.
ARCHITECTURE: Child outputs are read through the artifact store (jev_support.load_output_payload)
    and validated with the schema catalog. A failed options or human child blocks the decision
    (the same request is never silently retried); other failures become limitations.
"""

from __future__ import annotations

from typing import Any, cast

from kernel.capabilities.base import ExecutionContext
from kernel.capabilities.decision.approvals import apply_human_answer
from kernel.capabilities.decision.jev_support import (
    StopCapability,
    blocked_result,
    load_output_payload,
)
from kernel.capabilities.decision.state import (
    DecisionContinuation,
    Working,
    derive_decision_id,
)
from kernel.contracts import schema_ids
from kernel.contracts.decision import Criterion, Option
from kernel.contracts.enums import EvidenceCategory, RequestKind, ResultStatus
from kernel.contracts.evidence import Evidence, EvidenceBundlePayload
from kernel.contracts.payloads import (
    DecisionRequestPayload,
    FindingsPayload,
    GoalRequestPayload,
    HumanAnswerPayload,
    OptionsPayload,
)
from kernel.contracts.schema_catalog import validate_payload
from kernel.contracts.work import CapabilityInvocation, ChildOutcome

MAX_FINDINGS_KEPT = 20
MAX_GAPS_KEPT = 6
ACTOR_LOOKUP_LIMIT = 50


def _merge_by_id(base: list, overlay: list) -> list:
    """Return base with overlay items replacing same-id items and new ones appended."""
    merged = {item.id: item for item in base}
    for item in overlay:
        merged[item.id] = item
    return list(merged.values())


def _payload_inputs(invocation: CapabilityInvocation, cont: DecisionContinuation) -> Working:
    """Build Working from the request payload overlaid with the continuation."""
    model = validate_payload(invocation.input_payload_schema, invocation.input_payload)
    if isinstance(model, GoalRequestPayload):
        options: list[Option] = []
        criteria: list[Criterion] = []
        base: dict[str, Any] = {"question": model.goal, "approval_required": False,
                                "constraint_ids": [], "evidence_ids": []}
    else:
        model = cast(DecisionRequestPayload, model)
        options, criteria = list(model.options), list(model.criteria)
        base = {"question": model.question, "approval_required": model.approval_required,
                "constraint_ids": model.constraint_ids, "evidence_ids": model.evidence_ids}
    merged_ids = list(dict.fromkeys([*base["evidence_ids"], *cont.evidence_ids]))
    cont = cont.model_copy(update={"evidence_ids": merged_ids})
    return Working(question=base["question"], cont=cont,
                   options=_merge_by_id(options, cont.options),
                   criteria=_merge_by_id(criteria, cont.criteria),
                   approval_required=base["approval_required"],
                   constraint_ids=base["constraint_ids"],
                   decision_id=derive_decision_id(invocation.work_item_id))


def _absorb_options(work: Working, payload: dict) -> None:
    """Add proposed options and criteria from an options.v1 child (never overwriting ids)."""
    model = cast(OptionsPayload, validate_payload(schema_ids.OPTIONS, payload))
    known_o = {o.id for o in work.options}
    known_c = {c.id for c in work.criteria}
    work.options += [o for o in [*model.named_options, *model.options] if o.id not in known_o]
    work.criteria += [c for c in model.proposed_criteria if c.id not in known_c]
    work.limitations += [f"unresolved feasibility: {u}" for u in model.unresolved_feasibility]


def _keep_gaps(work: Working, unknowns: list[str]) -> None:
    """Remember what the newest synthesis could not find (it replaces the earlier gaps)."""
    if unknowns:
        gaps = list(dict.fromkeys(u.strip() for u in unknowns if u.strip()))[:MAX_GAPS_KEPT]
        work.cont = work.cont.model_copy(update={"gaps": gaps})


def _absorb_bundle(work: Working, payload: dict, inline: dict[str, Evidence]) -> None:
    """Add evidence ids and inline evidence from an evidence_bundle.v1 child."""
    model = cast(EvidenceBundlePayload, validate_payload(schema_ids.EVIDENCE_BUNDLE, payload))
    ids = [*model.evidence_ids, *(e.id for e in model.evidence)]
    merged = list(dict.fromkeys([*work.cont.evidence_ids, *ids]))
    work.cont = work.cont.model_copy(update={"evidence_ids": merged})
    inline.update({e.id: e for e in model.evidence})
    work.limitations += model.limitations
    _keep_gaps(work, model.unknowns)


def _absorb_findings(work: Working, payload: dict) -> None:
    """Keep synthesis claims and disagreements as context for the next assessment."""
    model = cast(FindingsPayload, validate_payload(schema_ids.FINDINGS, payload))
    claims = [f.claim for f in model.findings] + [f"disagreement: {d}" for d in model.disagreements]
    kept = [*work.cont.findings, *claims][-MAX_FINDINGS_KEPT:]
    refs = [*work.cont.finding_refs, *(f"[{f.id}] {f.claim}" for f in model.findings)]
    work.cont = work.cont.model_copy(update={
        "findings": kept, "finding_refs": list(dict.fromkeys(refs))[-MAX_FINDINGS_KEPT:]})
    _keep_gaps(work, model.unknowns)


def _answering_actor(ctx: ExecutionContext, invocation: CapabilityInvocation) -> str | None:
    """Return the actor of the newest human_input evidence among the context refs, if any."""
    refs = invocation.context_refs[-ACTOR_LOOKUP_LIMIT:]
    for item in reversed(ctx.evidence(refs)):
        if item.provenance.actor:
            return item.provenance.actor
    return None


def _absorb_outcome(work: Working, outcome: ChildOutcome, payload: dict | None,
                    inline: dict[str, Evidence], actor: str | None) -> None:
    """Dispatch one completed child output by schema id."""
    if payload is None:
        work.limitations.append(f"output of child {outcome.work_item_id} is unavailable")
    elif outcome.output_schema_id == schema_ids.OPTIONS:
        _absorb_options(work, payload)
    elif outcome.output_schema_id == schema_ids.EVIDENCE_BUNDLE:
        _absorb_bundle(work, payload, inline)
    elif outcome.output_schema_id == schema_ids.FINDINGS:
        _absorb_findings(work, payload)
    elif outcome.output_schema_id == schema_ids.HUMAN_ANSWER:
        if not outcome.current_wait:
            return  # an answer to an earlier question (e.g. the router's clarification)
        answer = cast(HumanAnswerPayload, validate_payload(schema_ids.HUMAN_ANSWER, payload))
        apply_human_answer(work, answer, outcome.actor_id or actor)


def _check_failures(invocation: CapabilityInvocation, outcomes: list[ChildOutcome],
                    work: Working) -> None:
    """Block on a failed options or human child; record other failures as limitations."""
    for outcome in outcomes:
        if outcome.status in (ResultStatus.FAILED, ResultStatus.BLOCKED):
            message = f"{outcome.request_kind.value} child {outcome.work_item_id} " \
                      f"{outcome.status.value}"
            if outcome.request_kind in (RequestKind.OPTIONS, RequestKind.HUMAN):
                raise StopCapability(blocked_result(invocation, "child_unavailable", message))
            work.limitations.append(message)


def _attach_evidence(ctx: ExecutionContext, work: Working, inline: dict[str, Evidence]) -> None:
    """Resolve evidence ids through the kernel lookup, falling back to inline bundle items."""
    ids = work.cont.evidence_ids
    found = {e.id: e for e in ctx.evidence(ids)}
    for ev_id in ids:
        item = found.get(ev_id) or inline.get(ev_id)
        if item is None:
            work.missing_evidence_ids.append(ev_id)
        else:
            work.evidence.append(item)
    if work.missing_evidence_ids:
        work.limitations.append(f"evidence not found: {sorted(work.missing_evidence_ids)}")


def _check_basis_scope(ctx: ExecutionContext, work: Working) -> None:
    """Record limitations when decision-basis evidence may not apply to the current revision."""
    current = ctx.scope.revision.commit if ctx.scope.revision else None
    work.revision_commit = current
    for item in work.evidence:
        if item.category is not EvidenceCategory.PRIOR_DECISIONS:
            continue
        version = item.source.source_version
        if version is None or version.commit is None:
            work.limitations.append(f"decision basis {item.id} has no recorded revision")
        elif current and version.commit != current:
            work.limitations.append(
                f"decision basis {item.id} was read at {version.commit[:10]}, "
                f"scope is at {current[:10]}")


def load_working(invocation: CapabilityInvocation, ctx: ExecutionContext) -> Working:
    """Build the working state for one invocation (the graph's `load` node).

    Args:
        invocation: The validated invocation (payload, continuation, child outcomes).
        ctx: The execution context (evidence lookup, artifacts, scope).

    Returns:
        Working: Merged inputs, with `cont.attempt` already incremented.

    Raises:
        StopCapability: An options or human child failed, so the same request cannot be retried.
    """
    cont = (DecisionContinuation.model_validate(invocation.continuation.state)
            if invocation.continuation else DecisionContinuation())
    cont = cont.model_copy(update={"attempt": cont.attempt + 1})
    work = _payload_inputs(invocation, cont)
    work.require_grounding = ctx.config.decision.require_option_grounding
    work.evidence_cap = ctx.config.decision.max_grounding_evidence
    _check_failures(invocation, invocation.child_outcomes, work)
    inline: dict[str, Evidence] = {}
    actor = _answering_actor(ctx, invocation)
    for outcome in invocation.child_outcomes:
        if outcome.status in (ResultStatus.COMPLETED, ResultStatus.PARTIAL):
            _absorb_outcome(work, outcome, load_output_payload(ctx, outcome), inline, actor)
    _attach_evidence(ctx, work, inline)
    _check_basis_scope(ctx, work)
    return work


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: The unknowns of a synthesis (in a bundle or findings) are kept as
#   the decision's gaps for the next research request. (#KernelV01/D)
# - 2026-10-02 [python-coder]: mypy: the payload base values are dict[str, Any] (#KernelBootstrapV0/GROUND)
# - 2026-10-02 [python-coder]: Kernel-verified named options join the decision as supplied
#   (usable) options. (#KernelBootstrapV0/GROUND)
# - 2026-10-02 [python-coder]: Accepted findings are kept with their ids for the options packet.
#   (#KernelBootstrapV0/GROUND)
# - 2026-10-01 23:00 [python-coder]: The decision id is derived from the work item id: it used
#   to be a fresh random id per invocation, so one decision produced several records.
#   (#KernelBootstrapV0/GROUND)
# - 2026-09-30 23:30 [python-coder]: Only human answers of the latest wait are applied; every
#   finished child is handed to a resumed parent, and the router's clarification answer once
#   became an approved criterion of a later phase. (#KernelBootstrapV0/P6)
# - 2026-09-30 23:00 [python-coder]: Evidence provenance.actor from the context refs names the
#   approver; without it approvals are recorded as "human" because the human_answer payload
#   carries no actor. (#KernelBootstrapV0/P5)
# ====================================================================
