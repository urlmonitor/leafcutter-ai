"""
MODULE: kernel.scheduler.state
GOAL: KernelState (the LangGraph state schema), its deterministic reducers, the Budgets counters
    and the RunOutcome value the finalize node produces.
BUSINESS CONTEXT: Parallel workers finish in any order, so every map merges by id in sorted-key
    order and events get their sequence number inside the reducer; a run therefore produces the
    same state whatever the completion order (Rev 3 section 8.3).
ARCHITECTURE: Every value is a contract model or a scalar (nothing runtime-only is serialised,
    spec 5.1). STATE_MODELS lists the models defined here so P2's checkpoint serde allowlist can
    include them next to contracts.ALL_MODELS. Only kernel nodes write lifecycle fields.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Annotated, Any, TypedDict

from pydantic import Field

from kernel.contracts import (
    CapabilityGap,
    CapabilityInvocation,
    CapabilityResult,
    Decision,
    ErrorInfo,
    Evidence,
    Finding,
    HostWorkRequest,
    HumanQuestion,
    KernelModel,
    OutputRef,
    RegistrySnapshot,
    Request,
    RoutingAssessment,
    RunEvent,
    RunStatus,
    Task,
    TaskInput,
    WorkItem,
)
from kernel.observability.tracer import TraceState


class Budgets(KernelModel):
    """Run counters used by the guards (design part 3, `Budgets`)."""

    work_items_created: int = Field(default=0, ge=0)
    jev_calls: int = Field(default=0, ge=0)
    host_operations: int = Field(default=0, ge=0)
    scheduler_iterations: int = Field(default=0, ge=0)
    active_seconds: float = Field(default=0.0, ge=0.0)
    cost_usd_known: float = Field(default=0.0, ge=0.0)
    cost_unknown_calls: int = Field(default=0, ge=0)
    #: Token totals over the provider calls that reported them; None while none has (never 0).
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    retries: dict[str, int] = Field(default_factory=dict)
    no_progress_streak: int = Field(default=0, ge=0)


class RunOutcome(KernelModel):
    """Terminal result of a run as decided by finalize (the service builds the envelope)."""

    status: RunStatus
    output: OutputRef | None = None
    report_ref: str | None = None
    limitations: list[str] = Field(default_factory=list)
    errors: list[ErrorInfo] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    diagnostics: list[str] = Field(default_factory=list)


#: Models kept in state that contracts.ALL_MODELS does not cover (checkpoint serde allowlist, P2).
STATE_MODELS: tuple[type, ...] = (Budgets, RunOutcome, TraceState)


def result_artifact_name(invocation_id: str) -> str:
    """Return the artifact name under which an invocation's CapabilityResult JSON is stored.

    `ChildOutcome.result_ref` carries this name, so a resumed parent reads a child's output with
    `ctx.artifacts.read_artifact(ctx.run_id, result_ref)`.
    """
    return f"result-{invocation_id}.json"


def _revision(value: object) -> int:
    """Return the `updated_revision` of a value, or 0 when it has none."""
    return int(getattr(value, "updated_revision", 0))


def merge_map(left: Mapping[str, Any] | None, right: Mapping[str, Any] | None
              ) -> dict[str, Any]:
    """Merge two id-keyed maps deterministically: sorted keys, newer `updated_revision` wins.

    Args:
        left: Current map.
        right: Incoming updates.

    Returns:
        dict[str, Any]: A new map with keys in sorted order; an incoming value replaces the
            current one unless the current one carries a higher `updated_revision`.
    """
    merged = dict(left or {})
    for key in sorted(right or {}):
        incoming, current = right[key], merged.get(key)
        if current is not None and _revision(incoming) < _revision(current):
            continue
        merged[key] = incoming
    return {key: merged[key] for key in sorted(merged)}


def sum_counts(left: Mapping[str, int] | None, right: Mapping[str, int] | None
               ) -> dict[str, int]:
    """Add two counter maps key by key (used for attempt fingerprints)."""
    merged = dict(left or {})
    for key in sorted(right or {}):
        merged[key] = merged.get(key, 0) + right[key]
    return {key: merged[key] for key in sorted(merged)}


def append_events(left: list[RunEvent] | None, right: list[RunEvent] | None) -> list[RunEvent]:
    """Append incoming events and number them after the existing ones.

    Nodes emit events with a placeholder `seq`; numbering happens here so parallel nodes can
    never collide and the order is the deterministic order LangGraph applies updates in.
    """
    base = list(left or [])
    numbered = [event.model_copy(update={"seq": len(base) + i})
                for i, event in enumerate(right or [])]
    return base + numbered


class KernelState(TypedDict, total=False):
    """The fixed scheduler graph state (`total=False`: nodes write partial updates)."""

    run_id: str
    root_task_id: str
    task_input: TaskInput
    task: Task
    registry: RegistrySnapshot
    permissions: list[str]
    requests: Annotated[dict[str, Request], merge_map]
    work_items: Annotated[dict[str, WorkItem], merge_map]
    agenda: list[str]
    dispatch: dict[str, Any]
    invocations: Annotated[dict[str, CapabilityInvocation], merge_map]
    results: Annotated[dict[str, CapabilityResult], merge_map]
    routing: Annotated[dict[str, RoutingAssessment], merge_map]
    evidence: Annotated[dict[str, Evidence], merge_map]
    findings: Annotated[dict[str, Finding], merge_map]
    decisions: Annotated[dict[str, Decision], merge_map]
    interactions: Annotated[dict[str, HostWorkRequest | HumanQuestion], merge_map]
    interaction_queue: list[str]
    gaps: Annotated[dict[str, CapabilityGap], merge_map]
    budgets: Budgets
    fingerprints: Annotated[dict[str, int], sum_counts]
    events: Annotated[list[RunEvent], append_events]
    events_flushed: int
    state_revision: int
    status: RunStatus
    halt_reason: str | None
    outcome: RunOutcome | None
    trace: TraceState


def new_event(run_id: str, at: datetime, kind: str, detail: str = "", **refs: str) -> RunEvent:
    """Build a RunEvent with a placeholder seq (the reducer assigns the real one).

    Args:
        run_id: Run id.
        at: Event time (from the injectable clock).
        kind: Dotted event kind, for example `guard.tripped`.
        detail: Short human-readable detail.
        **refs: Id references (work item, invocation, ...); None values are dropped.

    Returns:
        RunEvent: The event.
    """
    clean = {key: str(value) for key, value in refs.items() if value is not None}
    return RunEvent(seq=0, run_id=run_id, kind=kind, at=at, refs=clean, detail=detail)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 22:00 [python-coder]: Budgets carries the known token totals (None until a call
#   reports them) so the envelope can show usage without guessing 0 for an unknown count.
#   (#KernelBootstrapV0/INTENT)
# - 2026-09-30 23:59 [python-coder]: Child results reach parents as run artifacts named by
#   result_artifact_name; `WorkItem.result_ref` stays the invocation id (the key of `results`).
#   (#KernelBootstrapV0/INT)
# - 2026-09-30 22:30 [python-coder]: Event numbering lives in the reducer (not in nodes) so
#   parallel writers cannot collide on seq. (#KernelBootstrapV0/P4)
# - 2026-09-30 22:30 [python-coder]: Added `dispatch`, `halt_reason`, `permissions` and
#   `events_flushed` to the design's key list: route must tell its conditional edge what to
#   dispatch, schedule must tell finalize why it stopped, and the run permissions are not in
#   Task. (#KernelBootstrapV0/P4)
# ====================================================================
