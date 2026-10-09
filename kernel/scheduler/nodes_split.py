"""
MODULE: kernel.scheduler.nodes_split
GOAL: The route node's split step: ask the "one question or several?" judgement beside an existing
    Jev question, record the answer, and, for a root that routing turned away (jev_none) and that
    is bundled, start a split instead of recording a capability gap.
BUSINESS CONTEXT: ADR-053 and ADR-067: a bundled request that no single capability fits is offered
    as a split the host proposes parts for and a person approves. Deterministic gates run first
    (cheapest mechanism first); the threshold is biased against false positives; a split never
    adds a Jev provider call.
ARCHITECTURE: A mixin for the route node's `_Router` (like IntentStep): it uses the router's
    draft, state, context, config and `_wait_on` helper. The split record is checkpointed in the
    same pass that parks the root on a `host.decompose_goal` child request, so the run returns
    `waiting_host` with the record already in state; its id is derived from the work item, so a
    re-executed node or a resumed run never creates a second split.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from kernel.contracts import (
    Decomposition,
    FoundAt,
    Priority,
    RequestKind,
    RequestProposal,
    SplitTrigger,
    WorkItem,
    WorkItemStatus,
    schema_ids,
)
from kernel.contracts.split import (
    GoalDecompositionPayload,
    GoalDecompositionRequestPayload,
    KeptRouting,
)
from kernel.providers.base import QuestionSpec
from kernel.scheduler.context import run_corr
from kernel.scheduler.merge import create_children, plan_proposals
from kernel.split.convert import convert_proposal
from kernel.split.gate import gate_proposal
from kernel.split.detect import bundle_question, gates_open, is_bundled, kind_allows_split
from kernel.split.text import derive_subject_kind, normalize_text, split_id

if TYPE_CHECKING:  # the route node imports this module, so these are for the type checker only
    from kernel.config import KernelConfig
    from kernel.scheduler.context import KernelRuntime
    from kernel.scheduler.merge import Draft
    from kernel.scheduler.routing import RouteEntry, RouteResult
    from kernel.scheduler.state import KernelState

DECOMPOSE_OPERATION = "decompose_goal"
#: Child capabilities a goal's parts may be routed to (ADR-067 section 3).
GOAL_CHILD_CAPABILITIES = ["decision", "research"]
JEV_NONE = "jev_none"


class SplitStep:
    """Mixin: the bundle judgement and the start of a split for the route node's router."""

    state: KernelState
    ctx: KernelRuntime
    cfg: KernelConfig
    draft: Draft
    scope_rev: Any
    task_update: Any
    splits: dict[str, Decomposition]
    plan: dict[str, Any]

    if TYPE_CHECKING:
        def _wait_on(self, item: WorkItem, children: list[str],
                     linked: list[str] | None = None) -> None: ...

    def _task(self) -> Any:
        """Return the task as it stands in this pass (the intent step may have updated it)."""
        return self.task_update or self.state["task"]

    def _parts_used(self) -> int:
        """Return the parts the run's splits already hold (the run's part allowance used)."""
        return sum(len(s.parts) for s in self.state.get("splits", {}).values())

    def wants_bundle(self, item: WorkItem) -> bool:
        """Return True when the bundle question should ride this item's next Jev batch."""
        task = self._task()
        if not kind_allows_split(task.intent, task.requested_output_schema):
            return False
        return gates_open(self.cfg, host_operations_used=self.draft.budgets.host_operations,
                          parts_used=self._parts_used(), item=item,
                          request=self.draft.request_of(item),
                          is_root=item.id == task.root_work_item_id)

    def bundle_questions(self, item: WorkItem) -> tuple[QuestionSpec, ...]:
        """Return the bundle question for an item's intent batch (empty when a gate is closed)."""
        if not self.wants_bundle(item):
            return ()
        return (bundle_question(item.id, "task.goal"),)

    def bundle_threshold_for(self, probability: float | None) -> float | None:
        """Return the threshold to record beside a bundle probability (None when not asked)."""
        return None if probability is None else self.cfg.split.bundle_threshold

    def note_bundle(self, item: WorkItem, probability: float | None) -> None:
        """Record an answered bundle judgement on the item (so it is never asked twice)."""
        if probability is None:
            return
        self.draft.put_item(item, split_checked=True, bundle_probability=probability)
        threshold = self.cfg.split.bundle_threshold
        self.draft.emit("split.bundle_judged", f"{probability:.2f} (threshold {threshold:.2f})",
                        work_item_id=item.id)
        self.ctx.tracer.event("split.bundle_judged",
                              run_corr(self.state, work_item_id=item.id),
                              payload={"probability": probability, "threshold": threshold,
                                       "bundled": is_bundled(probability, threshold)})

    def split_applies(self, item: WorkItem, result: RouteResult) -> bool:
        """Return True when routing turned the root away (jev_none) and it is a bundled subject."""
        return JEV_NONE in result.reason_codes and self._root_bundled(item)

    def _root_bundled(self, item: WorkItem) -> bool:
        """Return True for a root with no split yet whose subject kind allows one and is bundled."""
        task = self._task()
        if item.id != task.root_work_item_id:
            return False
        known = split_id(item.id) in self.state.get("splits", {}) or split_id(item.id) in self.splits
        if known or not kind_allows_split(task.intent, task.requested_output_schema):
            return False
        return is_bundled(item.bundle_probability, self.cfg.split.bundle_threshold)

    def ambiguous_split(self, entry: RouteEntry, routing_ref: str) -> bool:
        """Start a split (trigger ambiguous) for a bundled root routing could not decide for."""
        item = self.draft.items[entry.item_id]
        if not self._root_bundled(item):
            return False
        return self.start_split(entry, routing_ref, SplitTrigger.AMBIGUOUS)

    def no_match(self, entry: RouteEntry, result: RouteResult, routing_ref: str) -> None:
        """Handle a no-match outcome: a split for a bundled turned-away root, else a gap."""
        item = self.draft.items[entry.item_id]
        if self.split_applies(item, result) and self.start_split(entry, routing_ref):
            return
        self.draft.put_item(item, status=WorkItemStatus.DISPATCHED, routing_ref=routing_ref)
        self.plan["gap"].append(item.id)

    def accepted_split(self, entry: RouteEntry, descriptor: Any, routing_ref: str) -> bool:
        """Start a split (trigger bundled_accepted) for a bundled root routing has just accepted.

        The accepted routing (capability id, version, assessment id) is kept on the split record,
        so a rejected split can go ahead as that one decision without routing again. False leaves
        the item to be bound to the capability as today.
        """
        item = self.draft.items[entry.item_id]
        if descriptor is None or descriptor.id not in GOAL_CHILD_CAPABILITIES:
            return False
        if not self._root_bundled(item):
            return False
        kept = KeptRouting(capability_id=descriptor.id, capability_version=descriptor.version,
                           routing_assessment_id=routing_ref)
        return self.start_split(entry, routing_ref, SplitTrigger.BUNDLED_ACCEPTED, kept)

    def start_split(self, entry: RouteEntry, routing_ref: str,
                    trigger: SplitTrigger = SplitTrigger.JEV_NONE,
                    kept_routing: KeptRouting | None = None) -> bool:
        """Start the split of a turned-away root; False leaves the item for today's gap path."""
        item = self.draft.items[entry.item_id]
        task = self._task()
        subject = normalize_text(task.original_goal)
        kind = derive_subject_kind(task.requested_output_schema)
        record = Decomposition(
            id=split_id(item.id), run_id=self.state["run_id"], work_item_id=item.id,
            subject_kind=kind, subject_text=subject, found_at=FoundAt.ROUTING,
            work_item_depth=item.depth, trigger=trigger,
            kept_routing=kept_routing)
        payload = GoalDecompositionRequestPayload(
            subject_text=subject, subject_kind=kind, max_parts=self.cfg.split.max_parts,
            split_id=record.id, allowed_capabilities=list(GOAL_CHILD_CAPABILITIES))
        proposal = RequestProposal(
            kind=RequestKind.CAPABILITY, goal=f"Propose the parts of: {subject}"[:300],
            payload_schema=schema_ids.GOAL_DECOMPOSITION_REQUEST,
            payload=payload.model_dump(mode="json", exclude={"schema_version"}),
            requested_output_schema=schema_ids.GOAL_DECOMPOSITION,
            operation=DECOMPOSE_OPERATION, priority=Priority.REQUIRED)
        plan = plan_proposals(self.draft, item, [proposal], self.cfg.limits, self.scope_rev)
        if not plan.accepted:
            self.draft.emit("split.not_started", ",".join(c for _, c in plan.rejected) or "linked",
                            work_item_id=item.id)
            return False
        self.splits[record.id] = record
        item = self.draft.put_item(item, routing_ref=routing_ref)
        self._wait_on(item, create_children(self.draft, item, plan.accepted))
        self.draft.emit("split.started", trigger.value, work_item_id=item.id, split_id=record.id)
        self.ctx.tracer.event(
            "split.started", run_corr(self.state, work_item_id=item.id),
            payload={"split_id": record.id, "trigger": trigger.value, "subject_kind": kind.value,
                     "subject_chars": len(subject)})
        return True

    def _proposal_of(self, item: WorkItem) -> GoalDecompositionPayload | None:
        """Return the host's accepted proposal for the item's decompose_goal child, if it arrived."""
        for child_id in item.child_ids:
            child = self.draft.items[child_id]
            if self.draft.request_of(child).operation != DECOMPOSE_OPERATION:
                continue
            result = self.draft.results.get(child.result_ref or "")
            if child.status is WorkItemStatus.COMPLETED and result is not None:
                return GoalDecompositionPayload.model_validate(result.output_payload)
        return None

    def open_gate(self, item: WorkItem) -> bool:
        """Convert an arrived proposal and open the split gate; False leaves the item to routing.

        The record becomes `proposed` and the root parks on the gate, a human question, so the
        run waits for a person with every part not run. Fewer than two parts leave the item to
        today's routing (DK-400c-3 owns that ending).
        """
        record = self.state.get("splits", {}).get(split_id(item.id))
        proposal = self._proposal_of(item) if record is not None and record.state is None else None
        if record is None or proposal is None:
            return False
        done = convert_proposal(proposal, record.subject_text, record.subject_kind,
                                max_parts=self.cfg.split.max_parts,
                                allowance=self.cfg.split.max_parts_per_run - self._parts_used())
        if done.kept_count < 2 or len(done.parts) < 2:
            self.draft.emit("split.not_offered", f"{len(done.parts)} parts",
                            work_item_id=item.id, split_id=record.id)
            return False
        record = record.model_copy(update={
            "state": "proposed", "parts": done.parts, "dropped": done.dropped,
            "not_covered": done.not_covered, "one_question_rewording": done.rewording})
        released = dict(done.released)
        if not self._park(item, gate_proposal(record, released)):
            return True  # the root was blocked; the split stays unproposed
        self.splits[record.id] = record
        for part_id, ids in done.released:
            self.draft.emit("split.dependency_released", f"{part_id}: {', '.join(ids)}",
                            work_item_id=item.id, split_id=record.id)
        self.draft.emit("split.proposed", f"{len(done.parts)} parts", work_item_id=item.id,
                        split_id=record.id)
        return True


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-06 [python-coder]: A split parks the root on a REQUIRED `host.decompose_goal` child
#   (the formulate_question pattern) instead of a new pause mechanism, so the host handoff,
#   budget and tracing machinery is reused. Telemetry carries the subject length, never its text
#   (data_policy redaction). (#TICKET-20261006-DK-400a-1)
# - 2026-10-06 19:00 [python-coder]: Add the ambiguous split trigger: a bundled root routing cannot decide for is split, not clarified. (#TICKET-20261006-DK-400a-1-i)
# - 2026-10-09 [python-coder]: Add the bundled_accepted trigger: a bundled root routing accepted is split in the same route pass and the accepted routing is kept on the record. (#TICKET-20261006-DK-400a-2)
# - 2026-10-09 [python-coder]: The gate is a human child request of the split root (the clarification pattern), opened in the router pass that meets the accepted proposal; conversion is deterministic code and never asks Jev. (#TICKET-20261006-DK-400c-1)
# ====================================================================
