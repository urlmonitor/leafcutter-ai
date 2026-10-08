"""MODULE: kernel.scheduler.nodes_enrichment
GOAL: Checkpoint deterministic interpretation before intent can classify the request.
BUSINESS CONTEXT: Meaning cards explain names without becoming task evidence or authority.
ARCHITECTURE: One recognition boundary, retaining entity and historical checkpoints on resume.
"""

from __future__ import annotations

import asyncio
from typing import Any

from langgraph.runtime import Runtime

from kernel.entity_context import recognize_entities
from kernel.scheduler.context import KernelRuntime, run_corr, sequential_node
from kernel.scheduler.state import KernelState, new_event


@sequential_node("enrich_context")
async def enrich_context(state: KernelState, runtime: Runtime[KernelRuntime]) -> dict[str, Any]:
    """Recognize once, preserving either interpretation contract across waits and restarts."""
    if state.get("entity_context") is not None or state.get("context_enrichment") is not None:
        return {}
    ctx = runtime.context
    corr = run_corr(state, work_item_id=state["task"].root_work_item_id)
    with ctx.tracer.span("entity.recognition", "context", corr):
        context = await asyncio.to_thread(recognize_entities, state["task_input"], ctx.config,
                                          state["registry"], redactor=ctx.redactor)
    summary = {"status": context.status, "coverage": context.coverage.model_dump(mode="json"),
               "budgets": context.budgets.model_dump(mode="json"),
               "limitations": context.limitations}
    if ctx.redactor is not None:
        summary = ctx.redactor.mask(summary)
    ctx.tracer.event("entity.resolution", corr, payload={"coverage": summary["coverage"]})
    ctx.tracer.event("entity.projection", corr, payload={"budgets": summary["budgets"]})
    ctx.tracer.event("context.recognized", corr, payload=summary)
    detail = f"{context.status}: {len(context.entities)} meaning(s)"
    return {"entity_context": context, "events": [new_event(
        state["run_id"], ctx.clock(), "context.recognized", detail,
        work_item_id=state["task"].root_work_item_id)]}

# DECISION HISTORY
# ====================================================================
# - 2026-10-03 15:10 [python-coder]: Preserve verbatim goals and separate meaning, caller and clarification channels. (#DK-300/entity-context)
