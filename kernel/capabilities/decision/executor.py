"""
MODULE: kernel.capabilities.decision.executor
GOAL: The native `decision` capability: a LangGraph graph (load, validate_basis, assess, combine,
    emit) wrapped as a CapabilityExecutor.
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
from kernel.capabilities.decision.assess import Assessment, assess
from kernel.capabilities.decision.basis import grounding_gap, validate_basis
from kernel.capabilities.decision.combine import Verdict, combine
from kernel.capabilities.decision.emit import (
    emit_followup,
    followup_for,
    resolved_result,
)
from kernel.capabilities.decision.jev_support import StopCapability, blocked_result
from kernel.capabilities.decision.loading import load_working
from kernel.capabilities.decision.requests import Followup
from kernel.capabilities.decision.state import Working
from kernel.contracts.capability import CapabilityResult
from kernel.contracts.work import CapabilityInvocation

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
    return {"work": work}


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
    """One Jev batch; its usage is recorded on the working state."""
    invocation, ctx = _run(config)
    work = state["work"]
    assessment = await assess(ctx, invocation, work)
    work.usage.append(assessment.result.usage)
    return {"assessment": assessment}


async def _combine(state: DecisionState, config: RunnableConfig) -> dict[str, Any]:
    """Apply the resolved-gate; resolved ends the run, anything else becomes a follow-up."""
    invocation, ctx = _run(config)
    work = state["work"]
    verdict = combine(work, state["assessment"], ctx.config.decision)
    ctx.tracer.event("decision.combine", ctx.corr, payload={
        "status": verdict.status.value, "reason": verdict.reason,
        "selected": verdict.selected_option_id, "revision": work.revision(),
        "thresholds": ctx.config.decision.model_dump(mode="json")})
    if verdict.status.value == "resolved":
        result = resolved_result(invocation, work, verdict)
        _status_event(ctx, verdict, result.decisions[0].approval_status.value)
        return {"verdict": verdict, "result": result}
    _status_event(ctx, verdict, "proposed" if work.pending_ids else "not_required")
    return {"verdict": verdict, "followup": followup_for(work, verdict)}


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


def _done_or(node: str):
    """Route to END when a result exists, otherwise to `node`."""
    return lambda state: END if state.get("result") else node


def _after_basis(state: DecisionState) -> str:
    """Route to emit when the basis needs a follow-up, otherwise to assess."""
    return "emit" if state.get("followup") else "assess"


def build_decision_graph() -> Any:
    """Compile the decision graph (no checkpointer)."""
    graph = StateGraph(DecisionState)
    for name, node in (("load", _load), ("validate_basis", _validate_basis),
                       ("assess", _assess), ("combine", _combine), ("emit", _emit)):
        graph.add_node(name, node)
    graph.set_entry_point("load")
    graph.add_conditional_edges("load", _done_or("validate_basis"),
                                {END: END, "validate_basis": "validate_basis"})
    graph.add_conditional_edges("validate_basis", _after_basis,
                                {"emit": "emit", "assess": "assess"})
    graph.add_edge("assess", "combine")
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
