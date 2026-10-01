"""
MODULE: kernel.scheduler.merge
GOAL: The Draft working copy of run state and the deterministic merge rules: settling a result
    onto its work item, planning and creating child requests, linking duplicates and resuming
    parents whose children are terminal (spec section 8.1 steps 7 to 10).
BUSINESS CONTEXT: The kernel, never a capability, decides lifecycle. Children are created only
    within the work-item, depth and cycle guards; an equivalent request is linked instead of
    re-run; a parent can never complete while a required child failed.
ARCHITECTURE: Nodes copy the maps they change into a Draft, apply these pure-ish functions and
    return `draft.update()`, so only touched entries reach the reducers. All iteration is in
    (created_seq, id) or sorted-id order, so the result does not depend on worker timing.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from kernel.config import LimitsConfig
from kernel.contracts import (
    CapabilityInvocation,
    CapabilityResult,
    Continuation,
    Decision,
    Evidence,
    Finding,
    Priority,
    Request,
    RequestProposal,
    ResultStatus,
    RunEvent,
    WorkItem,
    new_id,
)
from kernel.contracts import WorkItemStatus as WS
from kernel.contracts.evidence import EvidenceBundlePayload, stronger_category
from kernel.contracts.work import ChildOutcome
from kernel.scheduler import guards
from kernel.scheduler.state import Budgets, KernelState, new_event, result_artifact_name

_AS_RESULT = {WS.COMPLETED: ResultStatus.COMPLETED, WS.PARTIAL: ResultStatus.PARTIAL,
              WS.BLOCKED: ResultStatus.BLOCKED, WS.FAILED: ResultStatus.FAILED,
              WS.CANCELLED: ResultStatus.FAILED}
_AS_ITEM = {ResultStatus.COMPLETED: WS.COMPLETED, ResultStatus.PARTIAL: WS.PARTIAL,
            ResultStatus.BLOCKED: WS.BLOCKED}
_FAILING = frozenset({ResultStatus.FAILED, ResultStatus.BLOCKED})


@dataclass
class ProposalPlan:
    """Decision about each proposal of one waiting result."""

    accepted: list[tuple[RequestProposal, str]] = field(default_factory=list)
    linked: list[str] = field(default_factory=list)
    rejected: list[tuple[RequestProposal, str]] = field(default_factory=list)


class Draft:
    """Mutable working copy of the maps a node changes; `update()` returns only the changes."""

    def __init__(self, state: KernelState, now: datetime) -> None:
        """Copy the maps from state (nothing is shared with the graph state)."""
        self.now = now
        self.run_id = state["run_id"]
        self.rev = state.get("state_revision", 0)
        self.items: dict[str, WorkItem] = dict(state.get("work_items", {}))
        self.requests: dict[str, Request] = dict(state.get("requests", {}))
        self.results = state.get("results", {})
        self.evidence: dict[str, Evidence] = dict(state.get("evidence", {}))
        self.findings: dict[str, Finding] = dict(state.get("findings", {}))
        self.decisions: dict[str, Decision] = dict(state.get("decisions", {}))
        self.budgets: Budgets = state.get("budgets", Budgets())
        self.events: list[RunEvent] = []
        self.fingerprints: dict[str, int] = {}
        self.progress = False
        self.neutral = 0
        self._touched: set[str] = set()
        self._touched_requests: set[str] = set()
        self._new: dict[str, dict[str, Any]] = {"evidence": {}, "findings": {}, "decisions": {}}

    def put_item(self, item: WorkItem, **changes: Any) -> WorkItem:
        """Replace an item with a copy carrying `changes`, stamped with the current revision."""
        changes.update(updated_revision=self.rev, updated_at=self.now)
        new = item.model_copy(update=changes)
        self.items[new.id] = new
        self._touched.add(new.id)
        return new

    def add_request(self, request: Request) -> None:
        """Register a new request."""
        self.requests[request.id] = request
        self._touched_requests.add(request.id)

    def add_item(self, item: WorkItem) -> None:
        """Register a new work item."""
        self.items[item.id] = item
        self._touched.add(item.id)

    def emit(self, kind: str, detail: str = "", **refs: str | None) -> None:
        """Queue an event (the reducer numbers it)."""
        self.events.append(new_event(self.run_id, self.now, kind, detail, **refs))

    def request_of(self, item: WorkItem) -> Request:
        """Return the request a work item serves."""
        return self.requests[item.request_id]

    def sorted_items(self) -> list[WorkItem]:
        """Return all items in presentation order (created_seq, id)."""
        return sorted(self.items.values(), key=lambda i: (i.created_seq, i.id))

    def note_new(self, bucket: str, key: str, value: Any) -> None:
        """Record a new evidence, finding or decision entry (counts as progress)."""
        self._new[bucket][key] = value
        self.progress = True

    def update(self, *, include_budgets: bool = True) -> dict[str, Any]:
        """Return the partial state update holding only what changed.

        Args:
            include_budgets: False for nodes that run in parallel with others: `budgets` has a
                replace reducer, so only one node per superstep may write it.
        """
        out: dict[str, Any] = {"budgets": self.budgets} if include_budgets else {}
        if self._touched:
            out["work_items"] = {i: self.items[i] for i in sorted(self._touched)}
        if self._touched_requests:
            out["requests"] = {i: self.requests[i] for i in sorted(self._touched_requests)}
        for bucket, entries in self._new.items():
            if entries:
                out[bucket] = entries
        if self.fingerprints:
            out["fingerprints"] = self.fingerprints
        if self.events:
            out["events"] = self.events
        return out


def child_outcomes(item: WorkItem, items: Mapping[str, WorkItem],
                   requests: Mapping[str, Request], results: Mapping[str, CapabilityResult]
                   ) -> list[ChildOutcome]:
    """Return the terminal summaries of an item's children and linked dependencies."""
    refs = sorted({*item.child_ids, *item.dependency_ids},
                  key=lambda i: (items[i].created_seq, i) if i in items else (0, i))
    current = set(item.continuation.wait_child_ids) if item.continuation else set()
    out: list[ChildOutcome] = []
    for ref in refs:
        child = items.get(ref)
        if child is None or child.status not in guards.TERMINAL_STATUSES:
            continue
        result = results.get(child.result_ref) if child.result_ref else None
        request = requests[child.request_id]
        out.append(ChildOutcome(
            work_item_id=ref, request_kind=request.kind, status=_AS_RESULT[child.status],
            output_schema_id=result.output_schema_id if result else None,
            result_ref=result_artifact_name(child.result_ref) if result else None,
            priority=request.priority, current_wait=not current or ref in current,
            actor_id=next((e.provenance.actor for e in result.evidence
                           if e.provenance.actor), None) if result else None))
    return out


def plan_proposals(draft: Draft, parent: WorkItem, proposals: list[RequestProposal],
                   limits: LimitsConfig, scope_revision: Mapping[str, Any] | None
                   ) -> ProposalPlan:
    """Decide, in proposal order, which proposals become children, links or rejections."""
    parents = {i.id: draft.request_of(i).origin_work_item_id for i in draft.items.values()}
    chain = guards.ancestor_ids(draft.items, parents, parent.id)
    ancestor_keys = {draft.request_of(draft.items[a]).dedup_key for a in chain}
    existing = {draft.request_of(i).dedup_key: i.id for i in draft.sorted_items()
                if draft.request_of(i).dedup_key}
    plan, seen = ProposalPlan(), set()
    for proposal in proposals:
        key = guards.request_dedup_key(proposal, scope_revision)
        if key in ancestor_keys:
            plan.rejected.append((proposal, "cycle"))
        elif any(d not in draft.items for d in proposal.depends_on):
            plan.rejected.append((proposal, "unknown_dependency"))
        elif any(guards.reaches(draft.items, d, parent.id) for d in proposal.depends_on):
            plan.rejected.append((proposal, "cycle"))
        elif key in existing:
            plan.linked.append(existing[key])
        elif key in seen:
            continue
        elif not guards.depth_allows(parent.depth, limits):
            plan.rejected.append((proposal, "max_depth"))
        elif not guards.work_item_cap_allows(draft.budgets.work_items_created,
                                             len(plan.accepted) + 1, limits):
            plan.rejected.append((proposal, "work_item_cap"))
        else:
            seen.add(key)
            plan.accepted.append((proposal, key))
    return plan


def create_children(draft: Draft, parent: WorkItem,
                    accepted: list[tuple[RequestProposal, str]]) -> list[str]:
    """Register a Request and a READY WorkItem for each accepted proposal; return item ids."""
    created: list[str] = []
    for proposal, key in accepted:
        seq = len(draft.requests)
        stamps = {"created_at": draft.now, "updated_at": draft.now, "created_seq": seq}
        request = Request(id=new_id("req"), origin_work_item_id=parent.id, dedup_key=key,
                          **stamps, **proposal.model_dump(exclude={"schema_version"}))
        item = WorkItem(id=new_id("work"), root_task_id=parent.root_task_id,
                        request_id=request.id, depth=parent.depth + 1,
                        dependency_ids=list(proposal.depends_on),
                        updated_revision=draft.rev, **stamps)
        draft.add_request(request)
        draft.add_item(item)
        created.append(item.id)
    draft.budgets = draft.budgets.model_copy(update={
        "work_items_created": draft.budgets.work_items_created + len(created)})
    if created:
        draft.progress = True
    return created


def _add_limitations(item: WorkItem, *texts: str) -> list[str]:
    """Return the item's limitations extended with new distinct texts."""
    merged = list(item.limitations)
    merged.extend(t for t in texts if t and t not in merged)
    return merged


def _error_text(result: CapabilityResult) -> list[str]:
    """Return `code: message` for the result error, if any."""
    err = result.error
    return [f"{err.code}: {err.message}".strip()] if err else []


def merge_payload_items(draft: Draft, result: CapabilityResult) -> None:
    """Merge the result's evidence, findings and decisions by id (dedup by content address)."""
    inline_evidence: list[Evidence] = []
    inline_findings: list[Finding] = []
    if result.output_payload is not None and result.output_schema_id:
        bundle = _as_bundle(result)
        if bundle is not None:
            inline_evidence, inline_findings = bundle.evidence, bundle.findings
    for evidence in [*result.evidence, *inline_evidence]:
        kept = stronger_category(draft.evidence.get(evidence.id), evidence)
        if kept is not draft.evidence.get(evidence.id):
            draft.evidence[evidence.id] = kept
            draft.note_new("evidence", evidence.id, kept)
    for finding in [*result.findings, *inline_findings]:
        if finding.id not in draft.findings:
            draft.findings[finding.id] = finding
            draft.note_new("findings", finding.id, finding)
    for decision in result.decisions:
        known = draft.decisions.get(decision.id)
        if known is not None:  # one record per decision: it keeps its first created_at
            decision = decision.model_copy(update={"created_at": known.created_at})
        if known is None or decision.differs_from(known):
            draft.decisions[decision.id] = decision
            draft.note_new("decisions", decision.id, decision)


def _as_bundle(result: CapabilityResult) -> EvidenceBundlePayload | None:
    """Return the evidence bundle payload of a result, if it carries one that validates."""
    from kernel.contracts import PayloadValidationError, validate_payload

    try:
        payload = validate_payload(str(result.output_schema_id), dict(result.output_payload or {}))
    except (PayloadValidationError, ValueError):
        return None
    return payload if isinstance(payload, EvidenceBundlePayload) else None


def settle_result(draft: Draft, item: WorkItem, invocation: CapabilityInvocation,
                  result: CapabilityResult, limits: LimitsConfig,
                  scope_revision: Mapping[str, Any] | None, *, no_progress: bool) -> None:
    """Apply a validated result to its work item (lifecycle, children, limitations)."""
    merge_payload_items(draft, result)
    if result.status is ResultStatus.FAILED:
        _settle_failed(draft, item, invocation, result, limits)
    elif result.status is ResultStatus.WAITING:
        if no_progress:
            _block(draft, item, invocation, "no_progress: the same work repeats without new input")
        else:
            _settle_waiting(draft, item, invocation, result, limits, scope_revision)
    else:
        _settle_terminal(draft, item, invocation, result)


def reject_result(draft: Draft, item: WorkItem, invocation: CapabilityInvocation, code: str,
                  text: str) -> None:
    """Fail the item because its result was invalid; nothing of the result is merged."""
    draft.put_item(item, status=WS.FAILED, result_ref=invocation.id, interaction_ref=None,
                   limitations=_add_limitations(item, f"{code}: {text}"))
    draft.progress = True
    draft.emit("result.rejected", f"{code}: {text}", work_item_id=item.id,
               invocation_id=invocation.id)


def _block(draft: Draft, item: WorkItem, invocation: CapabilityInvocation, text: str) -> None:
    """Block the item with a diagnostic (terminal, so it counts as progress)."""
    draft.put_item(item, status=WS.BLOCKED, result_ref=invocation.id, interaction_ref=None,
                   limitations=_add_limitations(item, text))
    draft.progress = True
    draft.emit("guard.tripped", text, work_item_id=item.id, guard=text.split(":", 1)[0])


def _settle_failed(draft: Draft, item: WorkItem, invocation: CapabilityInvocation,
                   result: CapabilityResult, limits: LimitsConfig) -> None:
    """Retry a transient failure with the same binding; otherwise fail the item."""
    if guards.retry_allowed(draft.budgets, item.id, result.error, limits):
        retries = {**draft.budgets.retries, item.id: draft.budgets.retries.get(item.id, 0) + 1}
        draft.budgets = draft.budgets.model_copy(update={"retries": retries})
        draft.neutral += 1
        draft.put_item(item, status=WS.READY, interaction_ref=None)
        draft.emit("work_item.retry", f"attempt {invocation.attempt} failed transiently",
                   work_item_id=item.id)
        return
    draft.put_item(item, status=WS.FAILED, result_ref=invocation.id, interaction_ref=None,
                   limitations=_add_limitations(item, *_error_text(result), *result.limitations))
    draft.progress = True


def _settle_terminal(draft: Draft, item: WorkItem, invocation: CapabilityInvocation,
                     result: CapabilityResult) -> None:
    """Complete, partial or block the item; a parent cannot complete over a failed required child."""
    outcomes = child_outcomes(item, draft.items, draft.requests, draft.results)
    failing = [o for o in outcomes if o.status in _FAILING]
    required_failed = [o.work_item_id for o in failing if o.priority is Priority.REQUIRED]
    supporting_failed = [f"supporting_child_failed: {o.work_item_id}" for o in failing
                         if o.priority is Priority.SUPPORTING]
    if result.status is ResultStatus.COMPLETED and required_failed:
        _block(draft, item, invocation,
               f"required_child_failed: {', '.join(required_failed)}")
        return
    draft.put_item(item, status=_AS_ITEM[result.status], result_ref=invocation.id,
                   interaction_ref=None, continuation=None,
                   limitations=_add_limitations(item, *result.limitations,
                                                *_error_text(result), *supporting_failed))
    draft.progress = True


def _settle_waiting(draft: Draft, item: WorkItem, invocation: CapabilityInvocation,
                    result: CapabilityResult, limits: LimitsConfig,
                    scope_revision: Mapping[str, Any] | None) -> None:
    """Create children, link duplicates and park the parent with its continuation."""
    plan = plan_proposals(draft, item, result.requests, limits, scope_revision)
    for _, code in plan.rejected:
        draft.emit("guard.tripped", code, work_item_id=item.id, guard=code)
    required = [c for p, c in plan.rejected if p.priority is Priority.REQUIRED]
    if required:
        _block(draft, item, invocation, f"{required[0]}: a required child request was rejected")
        return
    children = create_children(draft, item, plan.accepted)
    dependencies = sorted({*item.dependency_ids, *plan.linked})
    skipped = [f"{c}: a supporting child request was rejected" for _, c in plan.rejected]
    continuation = Continuation(
        capability_id=invocation.capability_id, capability_version=invocation.capability_version,
        state=dict(result.continuation_state or {}), resume_reason="children_done",
        wait_child_ids=[*children, *plan.linked])
    draft.put_item(item, status=WS.WAITING, child_ids=[*item.child_ids, *children],
                   dependency_ids=dependencies, continuation=continuation,
                   result_ref=invocation.id, interaction_ref=None,
                   limitations=_add_limitations(item, *skipped))


def resume_ready_parents(draft: Draft) -> list[str]:
    """Make every parked parent READY once all its children and dependencies are terminal."""
    resumed: list[str] = []
    for item in draft.sorted_items():
        if (item.status is not WS.WAITING or item.continuation is None
                or item.interaction_ref is not None):
            continue
        refs = {*item.child_ids, *item.dependency_ids}
        if all(r in draft.items and draft.items[r].status in guards.TERMINAL_STATUSES
               for r in refs):
            continuation = item.continuation.model_copy(update={"resume_reason": "children_done"})
            draft.put_item(item, status=WS.READY, continuation=continuation)
            draft.emit("work_item.resumed", "children done", work_item_id=item.id)
            resumed.append(item.id)
    return resumed


__all__ = ["Draft", "ProposalPlan", "child_outcomes", "create_children",
           "merge_payload_items", "plan_proposals", "reject_result", "resume_ready_parents",
           "settle_result"]

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 23:00 [python-coder]: A decision updates in place on any change but the clock.
#   (#KernelBootstrapV0/GROUND)
# - 2026-09-30 23:30 [python-coder]: A resumed parent still sees every finished child, but each
#   ChildOutcome says whether the child belongs to the parent's latest wait; a capability that
#   applies answers (decision) must apply only current ones, because the child list also holds
#   children of an earlier binding of the same item. (#KernelBootstrapV0/P6)
# - 2026-09-30 22:30 [python-coder]: A parent's COMPLETED result is rejected whenever any
#   required child failed or blocked (design 8.1 step 10 says "cites"; results carry no
#   citation list, so the safe over-approximation prevents a false success). (#KernelBootstrapV0/P4)
# - 2026-09-30 22:30 [python-coder]: A required proposal rejected by a guard blocks the parent
#   before any child is created, so no half-planned subtree exists. (#KernelBootstrapV0/P4)
# ====================================================================
