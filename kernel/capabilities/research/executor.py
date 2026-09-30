"""
MODULE: kernel.capabilities.research.executor
GOAL: The native `research` capability: a LangGraph graph (plan_needs and resolve_sources,
    collect, evaluate, finish) wrapped as a CapabilityExecutor.
BUSINESS CONTEXT: Gathers inspectable evidence for a question. Jev selects which generic
    categories are needed; code resolves sources; independent needs fan out as parallel child
    retrievals; synthesis is requested only when raw evidence cannot answer the question
    directly; research stops when needs are satisfied, no progress is possible or a guard hits
    (Rev 3 sections 10.2 and 10.5).
ARCHITECTURE: Compiled once without a checkpointer; the invocation and context travel in the
    run config. The continuation phase (planned, synthesizing) selects the entry node on resume.
    No re-planning happens on resume, so research never loops to raise a confidence score.
"""

from __future__ import annotations

from typing import Any, TypedDict, cast

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from kernel.capabilities.base import ExecutionContext
from kernel.capabilities.decision.jev_support import StopCapability
from kernel.capabilities.research.collect import (
    Judgement,
    close_coverage,
    collect_outcomes,
    judge,
    record_contradiction,
)
from kernel.capabilities.research.planning import plan_needs, resolve_sources
from kernel.capabilities.research.results import bundle_result, waiting_result
from kernel.capabilities.research.state import Collected, Plan, ResearchContinuation
from kernel.contracts.capability import CapabilityResult, Usage
from kernel.contracts.payloads import GoalRequestPayload, ResearchRequestPayload
from kernel.contracts.schema_catalog import validate_payload
from kernel.contracts.work import CapabilityInvocation

CAPABILITY_ID = "research"
CAPABILITY_VERSION = "1.0.0"


class ResearchState(TypedDict, total=False):
    """Graph state between nodes."""

    plan: Plan
    cont: ResearchContinuation
    out: Collected
    usage: list[Usage]
    result: CapabilityResult
    finish: bool


def _run(config: RunnableConfig) -> tuple[CapabilityInvocation, ExecutionContext]:
    """Return the invocation and context the graph was started with."""
    conf = config["configurable"]
    return conf["invocation"], conf["ctx"]


def parse_plan(invocation: CapabilityInvocation) -> Plan:
    """Parse goal_request.v1 or research_request.v1 into a Plan."""
    model = validate_payload(invocation.input_payload_schema, invocation.input_payload)
    if isinstance(model, GoalRequestPayload):
        return Plan(question=model.goal, expected_coverage="all_required", mandated=[],
                    source_restrictions=[])
    request = cast(ResearchRequestPayload, model)
    return Plan(question=request.question, expected_coverage=request.expected_coverage,
                mandated=list(request.evidence_needs),
                source_restrictions=list(request.source_restrictions))


async def _plan(state: ResearchState, config: RunnableConfig) -> dict[str, Any]:
    """plan_needs and resolve_sources: wait for children, or collect at once if none can run."""
    invocation, ctx = _run(config)
    plan = parse_plan(invocation)
    needs, usage = await plan_needs(ctx, invocation, plan)
    resolution = resolve_sources(ctx, needs, plan)
    cont = ResearchContinuation(
        phase="planned", needs=resolution.needs, child_map=resolution.child_map,
        unavailable=resolution.unavailable, attempted=resolution.attempted)
    if resolution.requests:
        return {"plan": plan, "cont": cont, "usage": usage,
                "result": waiting_result(invocation, cont, resolution.requests, usage)}
    return {"plan": plan, "cont": cont, "usage": usage}


async def _collect(state: ResearchState, config: RunnableConfig) -> dict[str, Any]:
    """Merge the children's bundles (or findings) into the collected state."""
    invocation, ctx = _run(config)
    cont = state.get("cont")
    if cont is None:
        cont = ResearchContinuation.model_validate(invocation.continuation.state)
    out = collect_outcomes(ctx, cont, invocation.child_outcomes)
    close_coverage(cont, out)
    return {"plan": state.get("plan") or parse_plan(invocation), "cont": cont, "out": out,
            "usage": state.get("usage", []), "finish": cont.phase == "synthesizing"}


async def _evaluate(state: ResearchState, config: RunnableConfig) -> dict[str, Any]:
    """Record contradictions and ask for synthesis only if the evidence cannot answer directly."""
    invocation, ctx = _run(config)
    plan, cont, out = state["plan"], state["cont"], state["out"]
    ask = ctx.config.research.allow_synthesis and not cont.synthesized
    judgement: Judgement = await judge(ctx, invocation, plan.question, out, ask)
    usage = [*state.get("usage", []), *judgement.usage]
    if judgement.conflict is not None:
        record_contradiction(ctx, out, judgement.conflict)
    threshold = ctx.config.research.evaluable_threshold
    if ask and judgement.evaluable is not None and judgement.evaluable < threshold:
        return {"usage": usage, "result": waiting_result(
            invocation, cont, [], usage, synthesis=(plan.question, out))}
    return {"usage": usage}


async def _finish(state: ResearchState, config: RunnableConfig) -> dict[str, Any]:
    """Build the evidence bundle result (partial when a required need is unsatisfied)."""
    invocation, _ = _run(config)
    return {"result": bundle_result(invocation, state["plan"], state["cont"], state["out"],
                                    state.get("usage", []))}


def _entry(config: RunnableConfig) -> str:
    """Route a fresh invocation to planning and a resumption to collect."""
    invocation, _ = _run(config)
    return "collect" if invocation.continuation else "plan"


def _after_plan(state: ResearchState) -> str:
    """End with `waiting` if children were requested, else go collect nothing."""
    return END if state.get("result") else "collect"


def _after_collect(state: ResearchState) -> str:
    """After a synthesis resume finish at once; otherwise evaluate."""
    return "finish" if state.get("finish") else "evaluate"


def _after_evaluate(state: ResearchState) -> str:
    """End with `waiting` if synthesis was requested, else finish."""
    return END if state.get("result") else "finish"


def build_research_graph() -> Any:
    """Compile the research graph (no checkpointer)."""
    graph = StateGraph(ResearchState)
    for name, node in (("plan", _plan), ("collect", _collect), ("evaluate", _evaluate),
                       ("finish", _finish)):
        graph.add_node(name, node)
    graph.set_conditional_entry_point(lambda state, config: _entry(config),
                                      {"plan": "plan", "collect": "collect"})
    graph.add_conditional_edges("plan", _after_plan, {END: END, "collect": "collect"})
    graph.add_conditional_edges("collect", _after_collect,
                                {"finish": "finish", "evaluate": "evaluate"})
    graph.add_conditional_edges("evaluate", _after_evaluate, {END: END, "finish": "finish"})
    graph.add_edge("finish", END)
    return graph.compile()


class ResearchExecutor:
    """CapabilityExecutor for the native research capability."""

    def __init__(self) -> None:
        """Compile the graph once."""
        self._graph = build_research_graph()

    async def ainvoke(self, invocation: CapabilityInvocation, ctx: ExecutionContext
                      ) -> CapabilityResult:
        """Run the graph; provider and budget problems come back as results."""
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
# - 2026-09-30 23:00 [python-coder]: A synthesis resume goes straight to finish: research never
#   re-plans or re-judges after new findings, so it cannot loop to raise a confidence score
#   (Rev 3 section 10.5). (#KernelBootstrapV0/P5)
# ====================================================================
