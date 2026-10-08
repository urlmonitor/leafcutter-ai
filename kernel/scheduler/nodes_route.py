"""
MODULE: kernel.scheduler.nodes_route
GOAL: The `route` node and its dispatch edge: bind each agenda item to a capability (eligibility
    filter, then Jev only where needed), build its CapabilityInvocation and fan native work out
    with LangGraph `Send`.
BUSINESS CONTEXT: Routing is where untrusted semantic choice meets trusted policy: candidates
    are filtered by code first, the binding is validated against the pinned snapshot and the
    BindingTable, and `unavailable` is recorded as a blocked or failed item, never as a gap.
ARCHITECTURE: `route` writes assessments, invocations, item bindings and a `dispatch` plan; the
    conditional edge `after_route` turns the plan into Sends and node names. Every branch ends in
    `integrate`, so parents of items that were blocked while routing still resume.
"""

from __future__ import annotations

from typing import Any

from langgraph.runtime import Runtime
from langgraph.types import Send

from kernel.capabilities.host import template_versions
from kernel.contracts import (
    CapabilityDescriptor,
    CapabilityInvocation,
    Continuation,
    ExecutionMode,
    RequestKind,
    RequestProposal,
    RoutingAssessment,
    RoutingOutcome,
    TraceContext,
    Task,
    WorkItem,
    WorkItemStatus,
    canonical_json,
    new_id,
    sha256_hex,
)
from kernel.contracts.base import fail
from kernel.contracts.work import Binding
from kernel.observability.tracer import TraceState
from kernel.registry.eligibility import filter_candidates
from kernel.intent.roots import root_contract_bound
from kernel.intent.questions import capability_question, repeated_message, unclear_message
from kernel.intent.step import IntentStep
from kernel.interaction.formulation import (
    FORMULATE_CAPABILITY,
    apply_wording,
    formulation_child,
    formulation_proposal,
)
from kernel.scheduler import guards
from kernel.scheduler.context import KernelRuntime, constraint_texts, run_corr, sequential_node
from kernel.scheduler.merge import Draft, child_outcomes, create_children, plan_proposals
from kernel.scheduler.routing import RouteEntry, RouteResult, deterministic_result, route_semantic
from kernel.scheduler.state import KernelState

HUMAN_CAPABILITY = "kernel.human"
ROUTER_CAPABILITY = "kernel.router"
KERNEL_CAP_REV = "1.0.0"
#: Routing failures that mean the provider failed (item fails) rather than "cannot run" (blocks).
PROVIDER_FAILURES = frozenset({"provider_unavailable", "invalid_provider_response",
                               "payload_too_large"})


def _scope_revision(state: KernelState) -> dict[str, Any] | None:
    """Return the task scope revision as a plain dict (or None)."""
    revision = state["task"].scope.revision
    return revision.model_dump() if revision else None


def build_invocation(draft: Draft, state: KernelState, item: WorkItem, binding: Binding,
                     n_invocations: int, current_trace: TraceState | None = None
                     ) -> CapabilityInvocation:
    """Build the invocation for an item: input, continuation, child outcomes, trace context.

    `current_trace` is this process's segment (runtime context); it wins over the trace stored
    in state, which still names the segment that started the run.
    """
    request = draft.request_of(item)
    resumed = item.continuation is not None and item.continuation.resume_reason == "children_done"
    outcomes = child_outcomes(item, draft.items, draft.requests, draft.results) if resumed else []
    invocation_id = new_id("inv")
    corr = run_corr(state, work_item_id=item.id, request_id=request.id,
                    invocation_id=invocation_id, capability_id=binding.capability_id,
                    parent_work_item_id=request.origin_work_item_id)
    trace = current_trace or state.get("trace")
    fingerprint = sha256_hex(canonical_json({
        "capability": [binding.capability_id, binding.version],
        "schema": request.payload_schema, "payload": request.payload,
        "context": request.context_refs,
        "continuation": item.continuation.state if item.continuation else None,
        "children": [(o.work_item_id, o.status.value, o.result_ref) for o in outcomes]}))
    return CapabilityInvocation(
        id=invocation_id, created_at=draft.now, updated_at=draft.now, created_seq=n_invocations,
        work_item_id=item.id, capability_id=binding.capability_id,
        capability_version=binding.version, input_payload_schema=request.payload_schema,
        input_payload=dict(request.payload), context_refs=list(request.context_refs),
        continuation=item.continuation, child_outcomes=outcomes, input_fingerprint=fingerprint,
        versions={"registry_hash": state["registry"].content_hash,
                  "capability": binding.version, **template_versions(binding.capability_id)},
        attempt=item.attempts + 1,
        trace=TraceContext(trace_id=trace.trace_id if trace else None,
                           parent_observation_id=trace.root_observation_id if trace else None,
                           correlation=corr))


class _Router(IntentStep):
    """One routing pass: collects decisions, applies them to a Draft and builds the plan."""

    def __init__(self, state: KernelState, runtime: Runtime[KernelRuntime]) -> None:
        """Bind the state, runtime dependencies and an empty plan."""
        self.state, self.ctx = state, runtime.context
        self.cfg = runtime.context.config
        self.draft = Draft(state, self.ctx.clock())
        self.plan: dict[str, Any] = {"native": [], "interaction": [], "gap": []}
        self.invocations: dict[str, CapabilityInvocation] = {}
        self.assessments: dict[str, RoutingAssessment] = {}
        self.scope_rev = _scope_revision(state)
        self.task_update: Any = None
        self.gaps: dict[str, Any] = {}

    def _set(self, item: WorkItem, status: WorkItemStatus, *limits: str, **changes: Any) -> None:
        """Change an item's status and append limitation texts."""
        merged = [*item.limitations, *[t for t in limits if t not in item.limitations]]
        self.draft.put_item(item, status=status, limitations=merged, **changes)

    def _dispatch(self, item: WorkItem, binding: Binding, routing_ref: str | None) -> None:
        """Create the invocation and move the item to DISPATCHED (native) or WAITING."""
        if item.continuation is not None and item.continuation.capability_id == ROUTER_CAPABILITY:
            item = self.draft.put_item(item, continuation=None)  # the router's wait is over
        all_invocations = len(self.state.get("invocations", {})) + len(self.invocations)
        invocation = build_invocation(self.draft, self.state, item, binding, all_invocations,
                                     self.ctx.trace)
        self.invocations[invocation.id] = invocation
        native = binding.execution_mode is ExecutionMode.NATIVE
        status = WorkItemStatus.DISPATCHED if native else WorkItemStatus.WAITING
        self.draft.put_item(item, status=status, binding=binding, attempts=item.attempts + 1,
                            routing_ref=routing_ref or item.routing_ref)
        self.plan["native" if native else "interaction"].append(invocation.id if native
                                                                   else item.id)

    def _bind_descriptor(self, item: WorkItem, descriptor: CapabilityDescriptor,
                         routing_ref: str | None) -> None:
        """Bind an item to a descriptor; host operations are counted against the budget."""
        if descriptor.execution_mode is ExecutionMode.HOST_HANDOFF:
            ops = descriptor.cost_hints.host_operations
            self.draft.budgets = self.draft.budgets.model_copy(update={
                "host_operations": self.draft.budgets.host_operations
                + (ops if ops is not None else 1)})
        binding = Binding(capability_id=descriptor.id, version=descriptor.version,
                          execution_mode=descriptor.execution_mode)
        self._dispatch(item, binding, routing_ref)

    def _dispatch_bound(self, item: WorkItem, binding: Binding) -> None:
        """Continuations and retries keep their pinned binding; it is re-validated, not re-routed."""
        descriptor = self.state["registry"].get(binding.capability_id)
        ok = (descriptor is not None and descriptor.version == binding.version
              and (binding.capability_id == HUMAN_CAPABILITY
                   or self.ctx.bindings.has(descriptor.binding, descriptor.version)))
        if not ok:
            self._set(item, WorkItemStatus.BLOCKED, "binding_missing: pinned binding unavailable")
            return
        self._dispatch(item, binding, None)

    def _formulate(self, item: WorkItem) -> bool:
        """Send the human question to `host.formulate_question` first; True while it is waiting.

        Off by default (`host.formulate_questions`). Only the wording comes back: the converted
        payload replaces the request payload and the kernel then creates the interaction itself.
        A refused, failed or unavailable formulation leaves the original question as it is.
        """
        child = formulation_child(self.draft, item)
        if child is not None:
            if child.status in guards.TERMINAL_STATUSES:
                apply_wording(self.draft, item, child)
                self.draft.put_item(item, continuation=None)
            return child.status not in guards.TERMINAL_STATUSES
        descriptor = self.state["registry"].get(FORMULATE_CAPABILITY)
        if descriptor is None or not self.ctx.bindings.has(descriptor.binding, descriptor.version):
            return False
        plan = plan_proposals(self.draft, item, [formulation_proposal(self.draft.request_of(item))],
                              self.cfg.limits, self.scope_rev)
        if not plan.accepted:
            return False
        self._wait_on(item, create_children(self.draft, item, plan.accepted))
        return True

    def _wait_on(self, item: WorkItem, children: list[str], linked: list[str] | None = None
                 ) -> None:
        """Park the item on child requests with the router continuation (resumed when done)."""
        continuation = Continuation(capability_id=ROUTER_CAPABILITY,
                                    capability_version=KERNEL_CAP_REV, state={},
                                    resume_reason="children_done")
        self.draft.put_item(item, status=WorkItemStatus.WAITING, continuation=continuation,
                            child_ids=[*item.child_ids, *children],
                            dependency_ids=sorted({*item.dependency_ids, *(linked or [])}))

    def _dispatch_human(self, item: WorkItem) -> None:
        """Human requests are fixed control flow: no routing, straight to an interaction."""
        if self.cfg.host.formulate_questions and self._formulate(item):
            return
        item = self.draft.items[item.id]
        binding = Binding(capability_id=HUMAN_CAPABILITY, version=KERNEL_CAP_REV,
                          execution_mode=ExecutionMode.HOST_HANDOFF)
        self._dispatch(item, binding, None)

    def _park(self, item: WorkItem, proposal: RequestProposal) -> bool:
        """Ask a human `proposal` and park the item until it is answered; False when blocked."""
        plan = plan_proposals(self.draft, item, [proposal], self.cfg.limits, self.scope_rev)
        linked_open = [i for i in plan.linked if self.draft.items[i].status
                       not in guards.TERMINAL_STATUSES]
        if plan.rejected:
            code = plan.rejected[0][1]
            self._set(item, WorkItemStatus.BLOCKED, f"{code}: clarification could not be requested")
        elif not plan.accepted and not linked_open:
            self._set(item, WorkItemStatus.BLOCKED, repeated_message())
        else:
            self._wait_on(item, create_children(self.draft, item, plan.accepted), plan.linked)
            return True
        return False

    def _unclear(self, entry: RouteEntry, result: RouteResult) -> None:
        """Insufficient context: ask a human once more (with choices) or end plainly.

        A gap is recorded only when the request ends unresolved, never before the human answered.
        """
        item = self.draft.items[entry.item_id]
        answers = self.answers_of(item)
        if self.cfg.routing.on_insufficient_context != "human":
            self._set(item, WorkItemStatus.BLOCKED,
                      f"insufficient_context: {', '.join(result.reason_codes)}")
        elif len(answers) >= self.cfg.intent.max_clarifications:
            self._set(item, WorkItemStatus.BLOCKED, unclear_message())
        else:
            task = self.state["task"]
            goal = task.original_goal if item.id == task.root_work_item_id else (
                entry.request.goal or entry.request.question or "the request")
            if self._park(item, capability_question(goal, entry.report.semantic_candidates,
                                                    answers[-1] if answers else None)):
                return
        self.plan["gap"].append(item.id)

    def _record(self, entry: RouteEntry, result: RouteResult) -> RoutingAssessment:
        """Persist the RoutingAssessment for an entry."""
        report = entry.report
        assessment = RoutingAssessment(
            id=new_id("ra"), created_at=self.draft.now, updated_at=self.draft.now,
            work_item_id=entry.item_id, eligible_candidate_ids=report.eligible_ids,
            excluded=list(report.excluded),
            selected=result.selected, probabilities=result.probabilities,
            provider_confidence=result.confidence, template_id="kernel.route" if result.jev_called
            else None, template_version="1" if result.jev_called else None,
            model_id=result.model_id, outcome=result.outcome, reason_codes=result.reason_codes,
            thresholds={"min_selected_probability": self.cfg.routing.min_selected_probability,
                        "min_confidence": self.cfg.routing.min_confidence},
            jev_called=result.jev_called)
        self.assessments[assessment.id] = assessment
        self.ctx.tracer.event("routing.assessed", run_corr(self.state, work_item_id=entry.item_id),
                              payload={"outcome": result.outcome.value,
                                       "selected": result.selected,
                                       "reason_codes": result.reason_codes})
        self.draft.emit("routing.assessed", result.outcome.value, work_item_id=entry.item_id,
                        assessment_id=assessment.id)
        return assessment

    def _apply(self, entry: RouteEntry, result: RouteResult, ref: str) -> None:
        """Apply one routing outcome to the item."""
        item = self.draft.items[entry.item_id]
        outcome = result.outcome
        if outcome is RoutingOutcome.SELECTED:
            descriptor = self.state["registry"].get(str(result.selected))
            self._bind_descriptor(item, descriptor or fail("selected capability not in the registry"), ref)
        elif outcome is RoutingOutcome.NO_MATCH:
            self.draft.put_item(item, status=WorkItemStatus.DISPATCHED, routing_ref=ref)
            self.plan["gap"].append(item.id)
        elif outcome is RoutingOutcome.UNAVAILABLE:
            codes = ", ".join(result.reason_codes) or "unspecified"
            failed = result.failure in PROVIDER_FAILURES
            status = WorkItemStatus.FAILED if failed else WorkItemStatus.BLOCKED
            code = result.failure if failed else "unavailable"
            self._set(item, status, f"{code}: {codes}", routing_ref=ref)
            self.draft.progress = True
        else:
            self.draft.put_item(item, routing_ref=ref)
            self._unclear(entry, result)

    def _entries(self, task: Task) -> list[RouteEntry]:
        """Dispatch pinned and human work, returning agenda entries needing capability routing."""
        state, draft = self.state, self.draft
        entries: list[RouteEntry] = []
        for item_id in state.get("agenda", []):
            item = draft.items[item_id]
            request = draft.request_of(item)
            if item.status is not WorkItemStatus.READY:
                continue
            if item.binding is not None:
                self._dispatch_bound(item, item.binding)
            elif request.kind is RequestKind.HUMAN:
                self._dispatch_human(item)
            else:
                report = filter_candidates(request, state["registry"], self.ctx.bindings,
                                           state.get("permissions", []), draft.budgets, self.cfg,
                                           scope=state["task"].scope,
                                           operation=request.operation)
                entries.append(RouteEntry(item.id, request, report,
                                          [a.text for a in self.answers_of(item)],
                                          intent_bound=root_contract_bound(task, request, item.id)))
        return entries

    async def run(self) -> dict[str, Any]:
        """Route the whole agenda and return the state update."""
        state, draft = self.state, self.draft
        await self.resolve_intent()
        entries = self._entries(self.task_update or state["task"])
        results: dict[str, RouteResult | None] = {
            e.item_id: deterministic_result(e.report, e.intent_bound) for e in entries}
        semantic = [e for e in entries if results[e.item_id] is None]
        if semantic:
            routed, calls = await route_semantic(
                self.ctx.jev, semantic, goal=state["task"].original_goal,
                component_ids=state["task"].scope.component_ids, cfg=self.cfg,
                calls_available=guards.jev_calls_available(draft.budgets, self.cfg.limits),
                corr=run_corr(state))
            results.update(routed)
            usage = [u for r in routed.values() for u in r.usage]
            draft.budgets = guards.account_usage(
                draft.budgets.model_copy(update={"jev_calls": draft.budgets.jev_calls + calls}),
                usage, self.cfg.jev.price_per_input_token_usd)
        for entry in entries:
            result = results[entry.item_id]
            if result is None:
                fail("a semantic routing entry came back without a result")
            self._apply(entry, result, self._record(entry, result).id)
        native = len(self.plan["native"])
        if native:
            self.plan["shares"] = {
                "jev": guards.jev_calls_available(draft.budgets, self.cfg.limits) // native,
                "work_item": max(0, self.cfg.limits.max_work_items
                                 - draft.budgets.work_items_created) // native}
        update = draft.update()
        update.update(invocations=self.invocations, routing=self.assessments, dispatch=self.plan)
        if self.task_update is not None:
            update["task"] = self.task_update
        if self.gaps:
            update["gaps"] = self.gaps
        return update


@sequential_node("route")
async def route(state: KernelState, runtime: Runtime[KernelRuntime]) -> dict[str, Any]:
    """Bind every agenda item to a capability (or an interaction, gap or terminal state)."""
    return await _Router(state, runtime).run()


def after_route(state: KernelState) -> list[Send | str]:
    """Dispatch edge: Sends for native items, interaction/gap nodes, else straight to integrate."""
    plan = state.get("dispatch") or {}
    targets: list[Send | str] = [Send("execute", _packet(state, inv_id, plan.get("shares", {})))
                                 for inv_id in plan.get("native", [])]
    if plan.get("interaction"):
        targets.append("open_interactions")
    if plan.get("gap"):
        targets.append("record_gaps")
    return targets or ["integrate"]


def _packet(state: KernelState, invocation_id: str, shares: dict[str, int]) -> dict[str, Any]:
    """Build the read-only packet a Send worker receives (a snapshot, never shared state)."""
    invocation = state["invocations"][invocation_id]
    root = state["work_items"].get(state["task"].root_work_item_id or "")
    request = state["requests"].get(root.request_id) if root else None
    clarifications = request.payload.get("clarifications", []) if request else []
    return {"invocation": invocation,
            "descriptor": state["registry"].get(invocation.capability_id),
            "evidence": dict(state.get("evidence", {})), "scope": state["task"].scope,
            "context_enrichment": state.get("context_enrichment"),
            "entity_context": state.get("entity_context"),
            "clarifications": clarifications if isinstance(clarifications, list) else [],
            "constraints": constraint_texts(state), "shares": dict(shares)}


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-02 [python-coder]: mypy: impossible-state branches fail clearly instead of passing None on (#KernelBootstrapV0/GROUND)
# - 2026-10-01 22:00 [python-coder]: The root's answer kind is resolved before routing (IntentStep
#   mixin), clarification is `_park` + `_unclear` (choices, one follow-up, a gap only when the
#   request ends unresolved), and the router continuation is built in one place. It is dropped
#   when the item is bound: a clarification answer must not reach the capability as one of its
#   own answers. (#KernelBootstrapV0/INTENT)
# - 2026-10-01 20:00 [python-coder]: Routing usage is no longer truncated to the call count: each
#   Jev call contributes exactly one usage record (see routing.py). (#KernelBootstrapV0/FIXB)
# - 2026-09-30 22:30 [python-coder]: Every route branch (including "nothing dispatchable")
#   leads to integrate, not schedule as in the design diagram: integrate is where parents of
#   items blocked at routing are resumed. (#KernelBootstrapV0/P4)
# - 2026-10-01 18:00 [python-coder]: With `host.formulate_questions` on, a human request first
#   spawns a `host.formulate_question` child and waits (like a clarification); on resume the
#   converted wording replaces the request payload and the kernel creates the human interaction.
#   A formulation that did not complete is ignored. (#KernelBootstrapV0/INT2)
# - 2026-09-30 22:30 [python-coder]: Insufficient context with policy `human` creates a human
#   child request and parks the item with a `kernel.router` continuation, reusing the generic
#   wait/resume machinery instead of a second pause mechanism. (#KernelBootstrapV0/P4)
# - 2026-10-01 11:10 [python-coder]: A host invocation records its packet template in `versions`
#   (host_template), so the template identity is part of the invocation record.
#   (#KernelBootstrapV0/P8)
# - 2026-10-01 10:00 [python-coder]: build_invocation prefers the runtime's current segment trace
#   over state["trace"], so invocations and host packets created after a resume nest under the
#   resuming segment (bug D). (#KernelBootstrapV0/P7)
# - 2026-10-02 16:54 [python-coder]: Bind typed research only after eligibility. (#KM-500a/2)
# - 2026-10-03 15:10 [python-coder]: Preserve verbatim goals and separate meaning, caller and clarification channels. (#DK-300/entity-context)
# ====================================================================
