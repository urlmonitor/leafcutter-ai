"""Initial context gathering, checkpointed before the scheduler can classify intent."""

from __future__ import annotations

import asyncio
from typing import Any

from langgraph.runtime import Runtime

from kernel.context_enrichment import gather_context
from kernel.scheduler.context import KernelRuntime, run_corr, sequential_node
from kernel.scheduler.state import KernelState, new_event


@sequential_node("enrich_context")
async def enrich_context(state: KernelState, runtime: Runtime[KernelRuntime]) -> dict[str, Any]:
    """Gather once per run, retaining the snapshot across waits and process restarts."""
    if state.get("context_enrichment") is not None:
        return {}
    ctx = runtime.context
    context = await asyncio.to_thread(gather_context, state["task_input"], ctx.config,
                                       state["registry"], redactor=ctx.redactor)
    detail = f"{context.status}: {len(context.evidence)} excerpt(s), {context.files_scanned} files"
    corr = run_corr(state, work_item_id=state["task"].root_work_item_id)
    ctx.tracer.event("context.enriched", corr, payload={
        "status": context.status, "sources_consulted": context.sources_consulted,
        "files_scanned": context.files_scanned, "evidence_count": len(context.evidence),
        "truncated": context.truncated, "limitations": context.limitations})
    return {"context_enrichment": context, "events": [new_event(
        state["run_id"], ctx.clock(), "context.enriched", detail,
        work_item_id=state["task"].root_work_item_id)]}
