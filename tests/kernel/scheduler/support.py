"""
MODULE: tests.kernel.scheduler.support
GOAL: Shared rig for the scheduler tests: descriptors, result builders, a fully faked
    KernelRuntime and helpers that drive the real compiled graph with `ainvoke`.
BUSINESS CONTEXT: Every scheduler behaviour (routing, merge, guards, fan-out, completion) must be
    asserted through `graph.ainvoke` with the P1 fakes, never by reading source, so the tests
    fail when the graph behaves differently, not when code is refactored.
ARCHITECTURE: Imported explicitly (no conftest). A Rig owns the doubles and registers one
    executor instance per binding key so tests can inspect the invocations they received.
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from kernel.config import KernelConfig, load_kernel_config
from kernel.contracts import (
    Actor,
    ActorKind,
    CapabilityDescriptor,
    CapabilityInvocation,
    CapabilityResult,
    RegistrySnapshot,
    RequestProposal,
    ResultStatus,
    TaskInput,
    new_id,
    schema_ids,
)
from kernel.observability.tracer import RecordingTracer
from kernel.persistence.memory import MemoryArtifactStore, MemoryGapStore, MemoryRunStore
from kernel.providers.fakes import ScriptedJev
from kernel.registry import BindingTable
from kernel.scheduler import KernelRuntime, build_kernel_graph, initial_state, run_config
from tests.kernel.helpers import ScriptedExecutor, load_json, make_descriptor, make_scope

REPORT = {"status": "resolved", "recommendation": "Use A", "selected_option_id": "opt-a"}
EMPTY_BUNDLE = {"evidence": [], "findings": []}


def descriptor(cap_id: str, *, kinds: tuple[str, ...] = ("capability",),
               accepts: str = schema_ids.GOAL_REQUEST, produces: str = schema_ids.DECISION_REPORT,
               mode: str = "native", routing: str = "fixed", text: str = "A test capability.",
               operations: tuple[str, ...] = (), **extra: Any) -> CapabilityDescriptor:
    """Return a descriptor with the given shape (binding key equals the id)."""
    return make_descriptor(id=cap_id, binding=cap_id, name=cap_id, description=text,
                           request_kinds=list(kinds), accepts_schemas=[accepts],
                           produces_schemas=[produces], execution_mode=mode, routing=routing,
                           operations=list(operations), permissions_required=[], **extra)


def retrieval_descriptor(cap_id: str = "retrieve.test", routing: str = "fixed"
                         ) -> CapabilityDescriptor:
    """Return a native descriptor serving retrieval_request.v1 evidence requests."""
    return descriptor(cap_id, kinds=("evidence",), accepts=schema_ids.RETRIEVAL_REQUEST,
                      produces=schema_ids.EVIDENCE_BUNDLE, routing=routing)


def completed(inv: CapabilityInvocation, schema: str = schema_ids.DECISION_REPORT,
              payload: dict | None = None, **extra: Any) -> CapabilityResult:
    """Return a completed result (a resolved decision report by default)."""
    body = payload if payload is not None else (REPORT if schema == schema_ids.DECISION_REPORT
                                                else EMPTY_BUNDLE)
    return CapabilityResult(invocation_id=inv.id, work_item_id=inv.work_item_id,
                            status=ResultStatus.COMPLETED, output_schema_id=schema,
                            output_payload=body, **extra)


def proposal(category: str = "prior_decisions", question: str = "Which store does the cache use?",
             **extra: Any) -> RequestProposal:
    """Return a retrieval request proposal for the given evidence category and question."""
    payload = load_json("valid/leafcutter.retrieval_request.v1/valid_basic.json")
    payload["need"].update(category=category, question=question)
    return RequestProposal(kind="evidence", goal=question, payload_schema=schema_ids.RETRIEVAL_REQUEST,
                           payload=payload, requested_output_schema=schema_ids.EVIDENCE_BUNDLE,
                           **extra)


def waiting(inv: CapabilityInvocation, *proposals: RequestProposal,
            state: dict | None = None) -> CapabilityResult:
    """Return a waiting result carrying the given child proposals."""
    return CapabilityResult(invocation_id=inv.id, work_item_id=inv.work_item_id,
                            status=ResultStatus.WAITING, requests=list(proposals),
                            continuation_state=state or {"phase": "waiting"})


def failed(inv: CapabilityInvocation, code: str = "boom", retryable: bool = False
           ) -> CapabilityResult:
    """Return a failed result."""
    return CapabilityResult(invocation_id=inv.id, work_item_id=inv.work_item_id,
                            status=ResultStatus.FAILED,
                            error={"code": code, "message": "x", "retryable": retryable})


def blocked(inv: CapabilityInvocation, text: str = "needs a human") -> CapabilityResult:
    """Return a blocked result naming an unmet prerequisite."""
    return CapabilityResult(invocation_id=inv.id, work_item_id=inv.work_item_id,
                            status=ResultStatus.BLOCKED, limitations=[text])


def two_phase(first: Callable[[CapabilityInvocation], CapabilityResult],
              then: Callable[[CapabilityInvocation], CapabilityResult]
              ) -> Callable[[CapabilityInvocation], CapabilityResult]:
    """Return a factory using `first` for a fresh invocation and `then` once resumed."""
    return lambda inv: first(inv) if inv.continuation is None else then(inv)


def with_limits(cfg: KernelConfig, **limits: Any) -> KernelConfig:
    """Return a config copy with some limits replaced."""
    return cfg.model_copy(update={"limits": cfg.limits.model_copy(update=limits)})


@dataclass
class Rig:
    """Test doubles, bindings and the pinned registry for one scheduler run."""

    descriptors: list[CapabilityDescriptor]
    executors: dict[str, Any] = field(default_factory=dict)
    config: KernelConfig = field(default_factory=load_kernel_config)
    jev: ScriptedJev = field(default_factory=ScriptedJev)
    tracer: RecordingTracer = field(default_factory=RecordingTracer)
    run_store: MemoryRunStore = field(default_factory=MemoryRunStore)
    gap_store: MemoryGapStore = field(default_factory=MemoryGapStore)
    artifacts: MemoryArtifactStore = field(default_factory=MemoryArtifactStore)
    monotonic: Callable[[], float] | None = None
    cancel: Callable[[], bool] = lambda: False
    permissions: tuple[str, ...] = ("read_repo",)
    max_iterations: int | None = None

    def bind(self, cap_id: str, executor: Any = None, *,
             factory: Callable[[CapabilityInvocation], CapabilityResult] = completed
             ) -> ScriptedExecutor:
        """Register an executor (default: a ScriptedExecutor using `factory`) for a binding."""
        self.executors[cap_id] = executor or ScriptedExecutor(factory=factory)
        return self.executors[cap_id]

    def runtime(self) -> KernelRuntime:
        """Build the KernelRuntime; bindings resolve to the registered executor instances."""
        bindings = BindingTable()
        for d in self.descriptors:
            if d.binding in self.executors:
                bindings.register(d.binding, d.version, lambda key=d.binding: self.executors[key])
        extra: dict[str, Any] = {"max_scheduler_iterations": self.max_iterations}
        if self.monotonic:
            extra["monotonic"] = self.monotonic
        return KernelRuntime(config=self.config, bindings=bindings, jev=self.jev,
                             tracer=self.tracer, run_store=self.run_store,
                             gap_store=self.gap_store, artifacts=self.artifacts,
                             cancel_probe=self.cancel, **extra)

    def snapshot(self) -> RegistrySnapshot:
        """Return the pinned registry snapshot of the rig's descriptors."""
        return RegistrySnapshot(registry_id="test", registry_version=1, content_hash="h" * 16,
                                source_path="test", descriptors=self.descriptors)

    def task_input(self, goal: str = "Decide the cache store", **extra: Any) -> TaskInput:
        """Return a TaskInput whose scope is an existing absolute directory."""
        scope = make_scope(Path(tempfile.gettempdir()))
        return TaskInput(goal=goal, caller=Actor(id="tester", kind=ActorKind.HOST), scope=scope,
                         permissions=list(self.permissions), **extra)

    async def start_raw(self, goal: str = "Decide the cache store", **extra: Any
                        ) -> tuple[Any, dict[str, Any], Any]:
        """Run the graph until it ends or pauses; return (graph, config, GraphOutput)."""
        graph = build_kernel_graph(MemorySaver())
        run_id = new_id("run")
        config = run_config(run_id, self.config.limits.langgraph_recursion_limit)
        state = initial_state(run_id, self.task_input(goal, **extra), self.snapshot())
        out = await graph.ainvoke(state, config, context=self.runtime(), version="v2",
                                  durability="sync")
        return graph, config, out

    async def start(self, goal: str = "Decide the cache store", **extra: Any
                    ) -> tuple[Any, dict[str, Any], dict[str, Any]]:
        """Run the graph until it ends or pauses; return (graph, config, final state)."""
        graph, config, out = await self.start_raw(goal, **extra)
        return graph, config, out.value

    async def resume(self, graph: Any, config: dict[str, Any], submission: dict[str, Any]) -> Any:
        """Resume a paused run with a submission (as the service will) and return the output."""
        return await graph.ainvoke(Command(resume=submission), config, context=self.runtime(),
                                   version="v2", durability="sync")

    def item_status(self, state: dict[str, Any]) -> dict[str, str]:
        """Return `{request goal or id: status}` for every work item, in presentation order."""
        items = sorted(state["work_items"].values(), key=lambda i: (i.created_seq, i.id))
        return {state["requests"][i.request_id].goal or i.id: i.status.value for i in items}


def root_item(state: dict[str, Any]) -> Any:
    """Return the root work item of a final state."""
    return state["work_items"][state["task"].root_work_item_id]


def event_kinds(state: dict[str, Any]) -> list[str]:
    """Return the kinds of all run events in order."""
    return [e.kind for e in state["events"]]


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:40 [python-coder]: Executors are registered as instances behind a factory so
#   tests can inspect exactly which invocations each capability received.
#   (#KernelBootstrapV0/P4)
# ====================================================================
