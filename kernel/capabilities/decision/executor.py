"""
MODULE: kernel.capabilities.decision.executor
GOAL: The native `decision` capability: a LangGraph graph (load, precedent, validate_basis, assess,
    combine, emit) wrapped as a CapabilityExecutor.
BUSINESS CONTEXT: Decides a bounded question against known options, approved criteria and
    evidence. Jev judges atomic questions; code applies the resolved-gate; anything missing
    becomes a typed child request, never a guess (Rev 3 sections 9.4, 9.5 and 10.1).
ARCHITECTURE: The graph is compiled once without a checkpointer (the kernel owns durability)
    and run with ainvoke per invocation; the invocation and context travel in the run config,
    not in graph state. Nodes end the run early by returning a `result`; StopCapability from
    deep helpers is converted to that result here.
"""

from __future__ import annotations

from typing import Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from kernel.capabilities.base import ExecutionContext
from kernel.capabilities.decision.publish_command import publish_command, publish_folder
from kernel.capabilities.decision.assess import Assessment, assess
from kernel.capabilities.decision.basis import grounding_gap, validate_basis
from kernel.capabilities.decision.budget_gate import fallback_followup, handover, reserve_for
from kernel.capabilities.decision.combine import Verdict, combine
from kernel.capabilities.decision.design_ending import apply_kinds, design_followup
from kernel.capabilities.decision.emit import (
    design_resolved_result,
    emit_followup,
    followup_for,
    precedent_resolved_result,
    resolved_result,
)
from kernel.capabilities.decision.jev_support import (
    StopCapability,
    ask_jev,
    blocked_result,
    make_batch,
)
from kernel.capabilities.decision.loading import load_working
from kernel.capabilities.decision.ranking import current_scores
from kernel.capabilities.decision.requests import Followup, precedent_request
from kernel.capabilities.decision.state import Working
from kernel.contracts.capability import CapabilityResult
from kernel.contracts.enums import DecisionStatus, MissingKnowledge, ResultStatus
from kernel.contracts.work import CapabilityInvocation
from kernel.memory.precedent import (
    DECIDE_ANEW,
    REUSE,
    confirm_text,
    final_links,
    find_precedents,
    judge,
    precedent_evidence,
    precedent_questions,
    precedent_state,
    read_scores,
)
from kernel.memory.precedent import PURPOSE as PRECEDENT_PURPOSE
from kernel.memory.staging import stage_decision_record

CAPABILITY_ID = "decision"
CAPABILITY_VERSION = "1.0.0"


class DecisionState(TypedDict, total=False):
    """Graph state: working data between nodes and the terminal result."""

    work: Working
    followup: Followup
    assessment: Assessment
    verdict: Verdict
    result: CapabilityResult


def _run(config: RunnableConfig) -> tuple[CapabilityInvocation, ExecutionContext]:
    """Return the invocation and context the graph was started with."""
    conf = config["configurable"]
    return conf["invocation"], conf["ctx"]


async def _load(state: DecisionState, config: RunnableConfig) -> dict[str, Any]:
    """Load payload, continuation and child outcomes; stop early on an approval rejection."""
    invocation, ctx = _run(config)
    work = load_working(invocation, ctx)
    if work.approval_rejected:
        return {"work": work, "result": blocked_result(
            invocation, "approval_rejected", "the human rejected the recommendation",
            usage=work.usage)}
    if work.cont.design_choice_id:  # the human chose among the ranked options: no Jev call
        result = design_resolved_result(invocation, work, ctx.config.decision)
        return {"work": work, "result": _stage(ctx, work, result, basis="kernel_ranking")}
    if work.cont.precedent_choice == REUSE:  # the human confirmed reusing a precedent
        return _reuse_precedent(invocation, ctx, work)
    return {"work": work}


def _reuse_precedent(invocation: CapabilityInvocation, ctx: ExecutionContext, work: Working
                     ) -> dict[str, Any]:
    """Resolve with the confirmed precedent's choice; if the record vanished, decide anew."""
    cont = work.cont
    record = ctx.memory.get_decision(cont.precedent_offer_id or "")
    evidence_id = cont.precedent_offer_evidence
    if record is None or evidence_id is None:
        work.limitations.append(f"precedent {cont.precedent_offer_id} is no longer in the store; "
                                "the decision continues without reusing it")
        work.cont = cont.model_copy(update={"precedent_choice": DECIDE_ANEW})
        return {"work": work}
    result = precedent_resolved_result(invocation, work, record, evidence_id)
    return {"work": work, "result": _stage(ctx, work, result, basis="precedent_reuse")}


def _stage(ctx: ExecutionContext, work: Working, result: CapabilityResult, *, basis: str
           ) -> CapabilityResult:
    """Stage the record of a resolved decision a human approved; return the result to emit.

    The kernel stays read-only toward the repository: the record goes to the run's artifacts and
    `decisions publish` is the only way into docs/decisions (ADR-060). When a record was staged
    the result says so (and how to publish it), so the report and the envelope tell the user;
    nothing is staged, and the result is unchanged, for a decision no human approved.
    """
    if result.status is not ResultStatus.COMPLETED or not result.decisions:
        return result
    decision, cont = result.decisions[0], work.cont
    selected = next((o for o in work.options if o.id == decision.selected_option_id), None)
    supersedes, related, notes = final_links(
        cont.precedents, offer_id=cont.precedent_offer_id, offer_title=cont.precedent_offer_option,
        choice=cont.precedent_choice, selected_title=selected.title if selected else "")
    staged = stage_decision_record(
        ctx, decision, options=work.options, criteria=work.criteria, evidence=work.evidence,
        ranking=cont.design_ranking if basis == "kernel_ranking" else (), precedents=notes,
        basis=basis, criterion_evidence={c.id: work.evidence_for(c) for c in work.usable_criteria},
        supersedes=supersedes, related=related)
    if staged is None:
        return result
    note = (f"decision record staged: {staged.path}; publish writes it into "
            f"{publish_folder()} (the kernel checkout); "
            f"publish it for review with: {publish_command(ctx.run_id)}")
    payload = dict(result.output_payload or {})
    payload["limitations"] = [*result.limitations, note]
    return result.model_copy(update={"limitations": [*result.limitations, note],
                                     "output_payload": payload})


async def _precedent(state: DecisionState, config: RunnableConfig) -> dict[str, Any]:
    """Look up earlier approved decisions once; judge them now or in the assessment batch.

    With a basis still to be built (no options yet) no assessment is coming, so one Jev call
    judges the precedents now and a strongly applicable one becomes the reuse question; otherwise
    the questions ride in the assessment batch (no extra call) and an applicable precedent is
    evidence only.
    """
    invocation, ctx = _run(config)
    work = state["work"]
    if work.cont.precedent_checked:
        return {}
    work.precedent_hits = find_precedents(ctx.memory, work.question, ctx.scope, ctx.constraints,
                                          ctx.config.memory)
    if not work.precedent_hits:
        work.cont = work.cont.model_copy(update={"precedent_checked": True})
        return {}
    if validate_basis(work) is None:
        return {}
    batch = make_batch(ctx, PRECEDENT_PURPOSE,
                       {"question": work.question, "precedents": precedent_state(work.precedent_hits)},
                       precedent_questions(work.precedent_hits))
    try:
        result = await ask_jev(ctx, invocation, batch)
    except StopCapability as stop:
        if stop.result.error is None or stop.result.error.code != "budget_exhausted":
            raise
        work.limitations.append("precedent was not judged: the Jev call budget is exhausted")
        work.cont = work.cont.model_copy(update={"precedent_checked": True})
        return {}
    work.usage.append(result.usage)
    followup = _apply_precedents(ctx, work, read_scores(result, work.precedent_hits))
    return {"followup": followup} if followup else {}


def _apply_precedents(ctx: ExecutionContext, work: Working, scores: dict[str, float]
                      ) -> Followup | None:
    """Turn Jev's judgements into evidence and, for a strong match, the reuse question."""
    hits = work.precedent_hits
    verdict = judge(hits, scores, ctx.config.memory, can_reuse=not work.usable_options)
    items = [precedent_evidence(h, p, ctx.clock()) for h, p in verdict.applicable]
    known = set(work.evidence_ids)
    fresh = [e for e in items if e.id not in known]
    work.evidence += fresh
    work.new_evidence += fresh
    updates: dict[str, Any] = {
        "precedent_checked": True, "precedents": verdict.notes,
        "evidence_ids": list(dict.fromkeys([*work.cont.evidence_ids, *(e.id for e in items)]))}
    ctx.tracer.event("decision.precedent", ctx.corr, payload={
        "candidates": [h.record.id for h in hits],
        "applicable": [h.record.id for h, _ in verdict.applicable],
        "offered": verdict.offer.record.id if verdict.offer else None,
        "scores": {k: round(v, 3) for k, v in scores.items()}})
    followup = None
    if verdict.offer is not None:
        record = verdict.offer.record
        item = next(e for e, (h, _) in zip(items, verdict.applicable, strict=True)
                    if h is verdict.offer)
        updates.update(precedent_offer_id=record.id,
                       precedent_offer_option=record.selected_option.title,
                       precedent_offer_evidence=item.id)
        followup = Followup(
            status=DecisionStatus.NEEDS_HUMAN, key=f"precedent:{record.id}",
            phase="awaiting_precedent", reason="precedent_confirm",
            request=precedent_request(work, record, item.id), open_question=confirm_text(record),
            missing=[MissingKnowledge.HUMAN_PREFERENCE_OR_AUTHORIZATION])
    work.cont = work.cont.model_copy(update=updates)
    work.precedent_hits = []
    return followup


async def _validate_basis(state: DecisionState, config: RunnableConfig) -> dict[str, Any]:
    """Deterministic basis checks; a missing basis becomes a follow-up.

    Raises:
        StopCapability: Grounding research found nothing and grounding is required.
    """
    invocation, ctx = _run(config)
    work = state["work"]
    if grounding_gap(work):
        if ctx.config.decision.require_option_grounding:
            raise StopCapability(blocked_result(
                invocation, "options_ungrounded",
                "research found no evidence about the option space, so options cannot be "
                "grounded", usage=work.usage))
        work.limitations.append("options are requested without grounding evidence: research "
                                "found nothing about the option space")
    followup = validate_basis(work)
    return {"followup": followup} if followup else {}


async def _assess(state: DecisionState, config: RunnableConfig) -> dict[str, Any]:
    """One Jev batch; its usage is recorded on the working state.

    An assessment the budget cannot fund falls back to the last complete one: the ranked human
    question is built from its scores (never a half-scored ranking). With no usable earlier
    assessment the stop stands.

    Raises:
        StopCapability: The assessment failed, or the budget stopped it with nothing to fall back on.
    """
    invocation, ctx = _run(config)
    work = state["work"]
    try:
        assessment = await assess(ctx, invocation, work)
    except StopCapability as stop:
        followup = fallback_followup(ctx, work, stop.result)
        if followup is None:
            raise
        ctx.tracer.event("decision.budget_fallback", ctx.corr, payload={
            "reason": followup.reason, "revision": work.revision(),
            "reserve": reserve_for(work, ctx.config)})
        return {"followup": followup}
    work.usage.append(assessment.result.usage)
    apply_kinds(work, assessment, ctx.config.decision)
    if work.precedent_hits:  # judged in this batch: evidence for what follows, never a resolution
        _apply_precedents(ctx, work, assessment.precedents)
    return {"assessment": assessment}


async def _combine(state: DecisionState, config: RunnableConfig) -> dict[str, Any]:
    """Apply the resolved-gate; resolved ends the run, anything else becomes a follow-up."""
    invocation, ctx = _run(config)
    work = state["work"]
    cfg = ctx.config.decision
    verdict = combine(work, state["assessment"], cfg)
    verdict = handover(ctx, work, state["assessment"], verdict) or verdict
    ctx.tracer.event("decision.combine", ctx.corr, payload={
        "status": verdict.status.value, "reason": verdict.reason,
        "selected": verdict.selected_option_id, "revision": work.revision(),
        "thresholds": cfg.model_dump(mode="json"),
        "ranking": [r.option_id for r in verdict.ranking]})
    if verdict.status.value == "resolved":
        result = resolved_result(invocation, work, verdict)
        _status_event(ctx, verdict, result.decisions[0].approval_status.value)
        return {"verdict": verdict, "result": _stage(ctx, work, result, basis="resolved_gate")}
    _status_event(ctx, verdict, "proposed" if work.pending_ids else "not_required")
    _remember_assessment(work, state["assessment"], verdict)
    if verdict.ranking:
        return {"verdict": verdict, "followup": design_followup(
            work, verdict.reason, verdict.ranking, cfg)}
    return {"verdict": verdict, "followup": followup_for(
        work, verdict, reserve=reserve_for(work, ctx.config))}


def _remember_assessment(work: Working, assessment: Assessment, verdict: Verdict) -> None:
    """Keep this assessment's scores (and any ranking shown) so the next one can compare."""
    work.cont = work.cont.model_copy(update={
        "last_scores": current_scores(work, assessment),
        "last_scores_evidence": work.evidence_ids,
        "design_ranking": verdict.ranking,
        "design_reason": verdict.reason if verdict.ranking else ""})


def _status_event(ctx: ExecutionContext, verdict: Verdict, approval: str) -> None:
    """Record the small `decision.status` event (ids and counts only, never excerpts)."""
    ctx.tracer.event("decision.status", ctx.corr, payload={
        "assessment_status": verdict.status.value, "approval_status": approval,
        "selected_option_id": verdict.selected_option_id,
        "missing_needs": len(verdict.missing)})


async def _emit(state: DecisionState, config: RunnableConfig) -> dict[str, Any]:
    """Turn the follow-up into waiting, partial or blocked."""
    invocation, _ = _run(config)
    return {"result": emit_followup(invocation, state["work"], state["followup"])}


def _after_assess(state: DecisionState) -> str:
    """Route to emit when the budget fallback already produced the follow-up, else to combine."""
    return "emit" if state.get("followup") else "combine"


def _done_or(node: str):
    """Route to END when a result exists, otherwise to `node`."""
    return lambda state: END if state.get("result") else node


def _after_precedent(state: DecisionState) -> str:
    """Route to emit when the reuse question was built, to END on a result, else to the basis."""
    if state.get("followup"):
        return "emit"
    return END if state.get("result") else "validate_basis"


def _after_basis(state: DecisionState) -> str:
    """Route to emit when the basis needs a follow-up, otherwise to assess."""
    return "emit" if state.get("followup") else "assess"


def build_decision_graph() -> Any:
    """Compile the decision graph (no checkpointer)."""
    graph = StateGraph(DecisionState)
    for name, node in (("load", _load), ("precedent", _precedent),
                       ("validate_basis", _validate_basis), ("assess", _assess),
                       ("combine", _combine), ("emit", _emit)):
        graph.add_node(name, node)
    graph.set_entry_point("load")
    graph.add_conditional_edges("load", _done_or("precedent"),
                                {END: END, "precedent": "precedent"})
    graph.add_conditional_edges("precedent", _after_precedent,
                                {END: END, "emit": "emit", "validate_basis": "validate_basis"})
    graph.add_conditional_edges("validate_basis", _after_basis,
                                {"emit": "emit", "assess": "assess"})
    graph.add_conditional_edges("assess", _after_assess, {"emit": "emit", "combine": "combine"})
    graph.add_conditional_edges("combine", _done_or("emit"), {END: END, "emit": "emit"})
    graph.add_edge("emit", END)
    return graph.compile()


class DecisionExecutor:
    """CapabilityExecutor for the native decision capability."""

    def __init__(self) -> None:
        """Compile the graph once."""
        self._graph = build_decision_graph()

    async def ainvoke(self, invocation: CapabilityInvocation, ctx: ExecutionContext
                      ) -> CapabilityResult:
        """Run the graph; provider, budget and child failures come back as results."""
        config: RunnableConfig = {
            "configurable": {"invocation": invocation, "ctx": ctx},
            "recursion_limit": ctx.config.limits.langgraph_recursion_limit}
        try:
            final = await self._graph.ainvoke({}, config=config)
        except StopCapability as stop:
            return stop.result
        return final["result"]


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: A `precedent` node looks up earlier approved decisions once; with no
#   basis yet one Jev call judges them and a strongly applicable one becomes the reuse-or-decide-
#   anew question, otherwise they are judged inside the assessment batch and are evidence only.
#   A resolved decision a human approved is staged through the memory port (the run's artifacts,
#   never the repository). (#KernelDecisionStore)
# - 2026-10-01 [python-coder]: Budget-aware ending: combine's follow-up passes through the budget
#   gate (a round that would eat the reserved final assessment becomes the ranked human question)
#   and an assessment refused for budget falls back to the last complete assessment.
#   (#KernelV01/E)
# - 2026-10-01 [python-coder]: A chosen design option resolves in `load` with no Jev call; the
#   assess node classifies criterion kinds and combine's ranking becomes a human follow-up.
#   (#KernelV01/A)
# - 2026-10-01 23:00 [python-coder]: When grounding research found nothing the decision blocks
#   (options_ungrounded) if grounding is required, else asks for options with a limitation.
#   (#KernelBootstrapV0/GROUND)
# - 2026-09-30 23:50 [python-coder]: `decision.status` is emitted beside `decision.combine`
#   with ids and counts only, so the observation map shows status and approval per assessment.
#   (#KernelBootstrapV0/P6)
# - 2026-09-30 23:00 [python-coder]: The invocation and ExecutionContext travel in
#   config["configurable"] so they are never part of graph state (Rev 3 section 5.1).
#   (#KernelBootstrapV0/P5)
# ====================================================================
