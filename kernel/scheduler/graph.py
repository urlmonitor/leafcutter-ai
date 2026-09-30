"""
MODULE: kernel.scheduler.graph
GOAL: Assemble the fixed scheduler graph (intake, schedule, route, execute, integrate,
    record_gaps, open_interactions, await_interaction, finalize) and build its input state.
BUSINESS CONTEXT: The kernel is one fixed LangGraph whose workload is dynamic (Rev 3 section 8):
    the topology never changes per question, so runs are inspectable, resumable and safe from
    model-generated control flow.
ARCHITECTURE: Nodes take `runtime: Runtime[KernelRuntime]`; the graph is invoked with
    `context=KernelRuntime(...)` so runtime dependencies are never serialised. Route's leaves
    (workers, interaction and gap nodes) all lead to `integrate`, which then leads to `schedule`.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from kernel.contracts import RegistrySnapshot, TaskInput
from kernel.scheduler.context import KernelRuntime
from kernel.scheduler.nodes_execute import execute
from kernel.scheduler.nodes_gaps import record_gaps
from kernel.scheduler.nodes_integrate import integrate
from kernel.scheduler.nodes_interaction import await_interaction, open_interactions
from kernel.scheduler.nodes_lifecycle import finalize, intake
from kernel.scheduler.nodes_route import after_route, route
from kernel.scheduler.nodes_schedule import after_schedule, schedule
from kernel.scheduler.state import KernelState


def build_kernel_graph(checkpointer: Any = None) -> Any:
    """Compile the scheduler graph.

    Args:
        checkpointer: LangGraph checkpointer (P2's sqlite saver in production, MemorySaver or
            None in unit tests).

    Returns:
        CompiledStateGraph: Invoke with `context=KernelRuntime(...)` and a `thread_id` equal to
            the run id.
    """
    graph = StateGraph(KernelState, context_schema=KernelRuntime)
    graph.add_node("intake", intake)
    graph.add_node("schedule", schedule)
    graph.add_node("route", route)
    graph.add_node("execute", execute)
    graph.add_node("integrate", integrate)
    graph.add_node("record_gaps", record_gaps)
    graph.add_node("open_interactions", open_interactions)
    graph.add_node("await_interaction", await_interaction)
    graph.add_node("finalize", finalize)
    graph.add_edge(START, "intake")
    graph.add_edge("intake", "schedule")
    graph.add_conditional_edges("schedule", after_schedule,
                                ["route", "await_interaction", "finalize"])
    graph.add_conditional_edges("route", after_route,
                                ["execute", "open_interactions", "record_gaps", "integrate"])
    for leaf in ("execute", "record_gaps", "open_interactions", "await_interaction"):
        graph.add_edge(leaf, "integrate")
    graph.add_edge("integrate", "schedule")
    graph.add_edge("finalize", END)
    return graph.compile(checkpointer=checkpointer)


def initial_state(run_id: str, task_input: TaskInput, registry: RegistrySnapshot
                  ) -> dict[str, Any]:
    """Return the graph input: run id, task input and the pinned registry snapshot."""
    return {"run_id": run_id, "task_input": task_input, "registry": registry}


def run_config(run_id: str, recursion_limit: int, callbacks: list | None = None
               ) -> dict[str, Any]:
    """Return the LangGraph config for a run: thread id, recursion limit and tracer callbacks."""
    config: dict[str, Any] = {"configurable": {"thread_id": run_id},
                              "recursion_limit": recursion_limit}
    if callbacks:
        config["callbacks"] = callbacks
    return config


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:30 [python-coder]: `record_gaps` and `open_interactions` both lead to
#   integrate instead of the design's gap -> open_interactions chain; P9 adds that chain when it
#   implements host fallback. (#KernelBootstrapV0/P4)
# ====================================================================
