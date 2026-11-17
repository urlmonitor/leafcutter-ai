"""Explicit bounded retrieval planning graph.

MODULE: query_graph
GOAL: Make retrieval decision and wait boundaries explicit LangGraph nodes.
BUSINESS CONTEXT: Missing data must not trigger coding and ambiguous counts need clarification.
ARCHITECTURE: Kernel owns durable continuations; config carries trusted runtime services.
"""
from __future__ import annotations

from typing import Any, TypedDict
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph
from kernel.contracts import CapabilityResult
from integrations import query_growth as steps
from integrations.query_answer_scope import missing_scope, scope_clarification
from integrations.query_answer_planning import plan_answer
from integrations.query_planning import clarification
from kernel.capabilities.decision.jev_support import blocked_result
from knowledge.capability_fit import assess_capability_fit


class QueryState(TypedDict, total=False):
    """Serializable local graph state; external waits use kernel continuations."""
    plan: dict
    usage: list
    result: CapabilityResult
    picked: str
    descriptors: dict


def _runtime(config: RunnableConfig) -> dict:
    """Read trusted invocation services from LangGraph config."""
    return config["configurable"]


async def _load(state: QueryState, config: RunnableConfig) -> dict:
    """Load the authoritative continuation or pin the initial source."""
    run = _runtime(config)
    invocation = run["invocation"]
    plan = dict(invocation.continuation.state) if invocation.continuation else await steps._initial(
        run["port"], run["admission"], invocation, run["ctx"], run["payload"])
    return {"plan": plan, "usage": []}


async def _resume(state: QueryState, config: RunnableConfig) -> dict:
    """Consume one current child outcome without repeating completed judgments.

    Args:
        state: Existing query plan and measured provider usage.
        config: Trusted kernel invocation and runtime services.

    Returns:
        Updated plan, execution selection or existing terminal result.
    """
    run = _runtime(config)
    value = await steps._continued(run["port"], run["catalog"], run["invocation"],
        run["ctx"], run["payload"], run["source_ids"], state["plan"], state["usage"])
    if isinstance(value, CapabilityResult):
        return {"result": value}
    if value.get("execution_descriptor"):
        descriptor = value.pop("execution_descriptor")
        return {"plan": value, "picked": descriptor["operation"],
                "descriptors": {descriptor["operation"]: descriptor}}
    return {"plan": value}


def _resumed(state: QueryState) -> str:
    """Continue admitted or clarified query execution without reselecting it."""
    if state.get("result") is not None:
        return END
    return "execute" if state.get("picked") else "clarify_scope"


async def _plan_answer(state: QueryState, config: RunnableConfig) -> dict:
    """Ask existing budgeted Jev for original answer obligations on fresh ready work."""
    run = _runtime(config)
    plan, usage = await plan_answer(run["ctx"], run["invocation"], state["plan"])
    return {"plan": plan, "usage": [*state["usage"], *usage]}


async def _clarify_scope(state: QueryState, config: RunnableConfig) -> dict:
    """Yield an ordinary human child when answer obligations remain ambiguous."""
    run = _runtime(config)
    plan = state["plan"]
    if missing_scope(plan.get("answer_requirements")) or plan.get("answer_planning_missing"):
        return {"result": scope_clarification(run["invocation"], run["ctx"], plan, tuple(state["usage"]))}
    return {}


async def _readiness(state: QueryState, config: RunnableConfig) -> dict:
    """Use bounded Jev readiness only for ready-phase work."""
    run = _runtime(config)
    if state["plan"]["phase"] != "ready":
        return {}
    result = await steps._ready(run["ctx"], run["invocation"], state["plan"], state["usage"])
    return {"result": result} if result is not None else {}


async def _target(state: QueryState, config: RunnableConfig) -> dict:
    """Resolve the answer kind through existing Jev and source mapping checks."""
    run = _runtime(config)
    result = await steps._target(run["ctx"], run["invocation"], state["plan"], state["usage"])
    return {"result": result} if result is not None else {}


def _capability_fit(state: QueryState, config: RunnableConfig) -> dict:
    """Establish field and mapping support before offering query construction.

    Args:
        state: Current scoped plan and measured usage.
        config: Trusted runtime services supplied by the kernel.

    Returns:
        Graph state update preserving the existing capability boundary.
    """
    run = _runtime(config)
    plan = state["plan"]
    kind = plan.get("target_kind")
    fields = (plan.get("answer_requirements") or {}).get("required_fields", [])
    plan["capability_fit"] = assess_capability_fit(plan, required_kinds=[kind] if kind else [],
        required_relationships=plan.get("required_relationships", []),
        required_fields={kind: fields} if kind else {}, matching_operation=None,
        catalog_complete=len(run["catalog"].descriptors()) <= 50)
    if plan["capability_fit"]["status"] == "missing_query":
        plan["capability_fit"].update(status="supported_data_pending_selection",
            limitations=["No missing operation is established until catalog selection."])
    if not kind:
        plan["capability_fit"].update(status="unknown", query_build_eligible=False)
    return {"plan": plan}


async def _select(state: QueryState, config: RunnableConfig) -> dict:
    """Choose only offered registered operations or an eligible query-only gap."""
    run = _runtime(config)
    picked, descriptors, usage = await steps._select(run["catalog"], run["invocation"],
        run["ctx"], state["plan"])
    return {"picked": picked, "descriptors": descriptors, "usage": [*state["usage"], *usage]}


def _clarify(state: QueryState, config: RunnableConfig) -> dict:
    """Yield an existing bounded clarification request."""
    run = _runtime(config)
    return {"result": clarification(run["invocation"], run["ctx"], state["plan"], state["usage"])}


def _build(state: QueryState, config: RunnableConfig) -> dict:
    """Recheck trusted build eligibility and yield the existing coding child."""
    run = _runtime(config)
    return {"result": steps._build_missing(run["catalog"], run["invocation"], run["ctx"],
        state["plan"], state["usage"])}


async def _execute(state: QueryState, config: RunnableConfig) -> dict:
    """Execute a selected digest-pinned operation or record an explicit skip.

    Args:
        state: Current scoped plan and measured usage.
        config: Trusted runtime services supplied by the kernel.

    Returns:
        Graph state update preserving the existing capability boundary.
    """
    run = _runtime(config)
    if state["picked"] == "skip":
        return {"result": blocked_result(run["invocation"], "retrieval_not_needed",
            "No additional query selected", usage=state["usage"])}
    return {"result": await steps._execute(run["port"], run["catalog"], run["invocation"],
        run["ctx"], run["payload"], run["source_ids"], state["plan"],
        state["descriptors"][state["picked"]], state["usage"])}


def _loaded(state: QueryState) -> str:
    """Route persisted waits to resume rather than replaying answer planning."""
    phase = state["plan"]["phase"]
    if phase in {"clarify", "building", "admitting"}:
        return "resume"
    return "plan_answer" if phase == "ready" else "target"


def _next(node: str) -> Any:
    """Stop on a terminal or waiting result, otherwise advance to a named node."""
    return lambda state: END if state.get("result") is not None else node


def _selected(state: QueryState) -> str:
    """Route the bounded Jev option to its explicit action node."""
    return state["picked"] if state["picked"] in {"clarify", "build"} else "execute"


def build_query_growth_graph() -> Any:
    """Compile explicit retrieval branching without a competing checkpoint store."""
    graph = StateGraph(QueryState)
    nodes = {"load": _load, "resume": _resume, "plan_answer": _plan_answer,
        "clarify_scope": _clarify_scope, "readiness": _readiness, "target": _target,
        "capability_fit": _capability_fit, "select": _select,
        "clarify": _clarify, "build": _build, "execute": _execute}
    for name, node in nodes.items():
        graph.add_node(name, node)
    graph.set_entry_point("load")
    graph.add_conditional_edges("load", _loaded, {name: name for name in ("resume", "plan_answer", "target")})
    graph.add_conditional_edges("resume", _resumed,
        {END: END, "execute": "execute", "clarify_scope": "clarify_scope"})
    for source, target in (("plan_answer", "clarify_scope"),
            ("clarify_scope", "readiness"), ("readiness", "target"),
            ("target", "capability_fit"), ("capability_fit", "select")):
        graph.add_conditional_edges(source, _next(target), {END: END, target: target})
    graph.add_conditional_edges("select", _selected, {name: name for name in ("clarify", "build", "execute")})
    for name in ("clarify", "build", "execute"):
        graph.add_edge(name, END)
    return graph.compile()


QUERY_GRAPH = build_query_growth_graph()

# DECISION HISTORY
# - 2026-10-01 [python-coder]: Explicit LangGraph retrieval nodes retain kernel-owned waits and Jev budgets. (#EPIC-RepositoryResearchAnswers/TICKET-20261001-KM-500e-1)
