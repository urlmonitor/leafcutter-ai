"""
MODULE: kernel.intent.step
GOAL: The root-intent step of the route node: classify the root goal when the caller did not
    choose an output contract, then shape the root request, decline it plainly, or ask a human
    to clarify, and record the assessment like any other routing assessment.
BUSINESS CONTEXT: The root request must pick a supported output contract (Rev 3 section 7.11).
    Classification is bounded (one Jev choice question over the five answer kinds), a decline is
    deterministic and never a build opportunity, and a clarification answer re-drives the
    classification on the goal as clarified so an answered question is never asked again.
ARCHITECTURE: A mixin for the route node's `_Router`: it uses the router's draft, state, context,
    config, assessments and `_park`/`_set` helpers. Scheduler functions are imported inside the
    methods because the scheduler imports this package (a module-level import would be circular).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from kernel.contracts import (
    FallbackOutcome,
    RequestKind,
    RoutingAssessment,
    RoutingOutcome,
    Task,
    WorkItem,
    WorkItemStatus,
    new_id,
)
from kernel.intent.classify import (
    ANSWER_KINDS,
    CHANGE,
    INTENT_DEFAULT,
    INTENT_TEMPLATE_ID,
    INTENT_TEMPLATE_REV,
    KIND_SCHEMA,
    ClarificationAnswer,
    IntentAssessment,
    assess_intent,
    chosen_kind,
    effective_goal,
)
from kernel.intent.gap_quality import NO_OUTPUT_SCHEMA
from kernel.intent.questions import answer_of, intent_question
from kernel.intent.roots import (
    decline_for,
    decline_limitation,
    shape_root,
    write_denial_reason,
)


if TYPE_CHECKING:  # the scheduler imports this package, so these are for the type checker only
    from kernel.config import KernelConfig
    from kernel.contracts import RequestProposal
    from kernel.scheduler.context import KernelRuntime
    from kernel.scheduler.merge import Draft
    from kernel.scheduler.state import KernelState


class IntentStep:
    """Mixin: resolve the root's answer kind before the root is routed.

    It is mixed into the route node's router, which supplies the attributes declared below.
    """

    state: KernelState
    ctx: KernelRuntime
    cfg: KernelConfig
    draft: Draft
    assessments: dict[str, RoutingAssessment]
    scope_rev: Any
    task_update: Any
    gaps: dict[str, Any]

    if TYPE_CHECKING:
        def _set(self, item: WorkItem, status: WorkItemStatus, *limits: str, **changes: Any
                 ) -> None: ...

        def _park(self, item: WorkItem, proposal: RequestProposal) -> bool: ...

    def answers_of(self, item: WorkItem) -> list[ClarificationAnswer]:
        """Return the human clarification answers given to an item, oldest first."""
        answers: list[ClarificationAnswer] = []
        children = [self.draft.items[r] for r in {*item.child_ids, *item.dependency_ids}
                    if r in self.draft.items]
        for child in sorted(children, key=lambda c: (c.created_seq, c.id)):
            request = self.draft.request_of(child)
            result = self.draft.results.get(child.result_ref) if child.result_ref else None
            if request.kind is not RequestKind.HUMAN or result is None:
                continue
            found = answer_of(request.payload, result.output_payload)
            if found is not None:
                answers.append(found)
        return answers

    async def resolve_intent(self) -> None:
        """Resolve the root's contract when it is about to be routed and still unresolved."""
        task = self.state["task"]
        if task.intent is not None or task.root_work_item_id not in self.state.get("agenda", []):
            return
        item = self.draft.items[task.root_work_item_id]
        answers = self.answers_of(item)
        assessment = await self._classify(task, item, answers)
        self._record_intent(item, assessment)
        item = self.draft.items[item.id]
        if assessment.kind is not None:
            self._apply_kind(item, task, assessment.kind, effective_goal(task.original_goal,
                                                                         answers))
        elif (assessment.outcome is RoutingOutcome.INSUFFICIENT_CONTEXT
              and self.cfg.routing.on_insufficient_context == "human"
              and len(answers) < self.cfg.intent.max_clarifications):
            question = intent_question(task.original_goal, answers[-1] if answers else None,
                                       context=self.state.get("context_enrichment"))
            if self._park(item, question):
                return
            self.task_update = task.model_copy(update={"intent": INTENT_DEFAULT})
        else:
            self.task_update = task.model_copy(update={"intent": INTENT_DEFAULT})

    async def _classify(self, task: Task, item: WorkItem, answers: list[ClarificationAnswer]
                        ) -> IntentAssessment:
        """Return the assessment: the human's own pick, else Jev's, else `unavailable`."""
        from kernel.scheduler import guards
        from kernel.scheduler.context import run_corr

        picked = chosen_kind(answers)
        if picked is not None:
            return IntentAssessment(RoutingOutcome.SELECTED, kind=picked,
                                    reason_codes=["human_chosen"])
        if guards.jev_calls_available(self.draft.budgets, self.cfg.limits) < 1:
            return IntentAssessment(RoutingOutcome.UNAVAILABLE, reason_codes=["budget_exhausted"])
        context = self.state.get("context_enrichment")
        if context is not None and not self.cfg.data_policy.send_repo_excerpts_to_jev:
            context = context.model_copy(update={"evidence": [], "limitations": [
                *context.limitations, "repository context withheld from Jev by data policy"]})
        assessment = await assess_intent(
            self.ctx.jev, task.original_goal, answers, task.scope.component_ids, self.cfg.intent,
            run_corr(self.state, work_item_id=item.id), context=context,
            max_state_chars=self.cfg.jev.max_state_chars)
        self.draft.budgets = guards.account_usage(
            self.draft.budgets.model_copy(update={
                "jev_calls": self.draft.budgets.jev_calls + 1}),
            assessment.usage, self.cfg.jev.price_per_input_token_usd)
        return assessment

    def _record_intent(self, item: WorkItem, result: IntentAssessment) -> None:
        """Persist the assessment (state, event, tracer) like any other routing assessment."""
        from kernel.scheduler.context import run_corr

        cfg = self.cfg.intent
        assessment = RoutingAssessment(
            id=new_id("ra"), created_at=self.draft.now, updated_at=self.draft.now,
            work_item_id=item.id, eligible_candidate_ids=list(ANSWER_KINDS),
            selected=result.kind if result.outcome is RoutingOutcome.SELECTED else None,
            probabilities=result.probabilities, provider_confidence=result.confidence,
            template_id=INTENT_TEMPLATE_ID if result.jev_called else None,
            template_version=INTENT_TEMPLATE_REV if result.jev_called else None,
            model_id=result.model_id, outcome=result.outcome, reason_codes=result.reason_codes,
            thresholds={"min_selected_probability": cfg.min_selected_probability,
                        "min_confidence": cfg.min_confidence}, jev_called=result.jev_called)
        self.assessments[assessment.id] = assessment
        self.draft.put_item(item, routing_ref=assessment.id)
        self.ctx.tracer.event("intent.assessed", run_corr(self.state, work_item_id=item.id),
                              payload={"outcome": result.outcome.value, "selected": result.kind,
                                       "reason_codes": result.reason_codes,
                                       "confidence": result.confidence,
                                       "probabilities": result.probabilities,
                                       "thresholds": assessment.thresholds})
        self.draft.emit("intent.assessed", result.kind or result.outcome.value,
                        work_item_id=item.id, assessment_id=assessment.id)

    def _apply_kind(self, item: WorkItem, task: Task, kind: str, goal: str) -> None:
        """Shape the root for a served kind, or decline it plainly."""
        from kernel.scheduler import guards

        decline = decline_for(kind)
        if decline is not None:
            self._decline(item, task, kind, decline)
            return
        shaped = shape_root(self.draft.request_of(item), kind, goal)
        self.draft.add_request(shaped.model_copy(update={
            "dedup_key": guards.request_dedup_key(shaped, self.scope_rev)}))
        self.task_update = task.model_copy(update={
            "intent": kind, "requested_output_schema": KIND_SCHEMA[kind]})

    def _decline(self, item: WorkItem, task: Task, kind: str, decline: Any) -> None:
        """Block the root with a plain decline and record its observation (no build opportunity)."""
        from kernel.scheduler.nodes_gaps import build_gap, record_observation

        reason = (write_denial_reason(self.state.get("permissions", [])) if kind == CHANGE
                  else "the goal is not about software engineering in this repository")
        self._set(item, WorkItemStatus.BLOCKED, decline_limitation(decline))
        self.draft.progress = True
        self.draft.emit("work_item.blocked", f"{decline.code}: {reason}", work_item_id=item.id)
        request = self.draft.request_of(item)
        gap = build_gap(self.state, item, request, None, decline.gap_type, self.draft.now,
                        FallbackOutcome.BLOCKED).model_copy(update={
                            "why_insufficient": f"{decline.code}: {reason}",
                            "output_schema": NO_OUTPUT_SCHEMA})
        stored, events = record_observation(self.ctx, self.state, item, gap, self.draft.now)
        self.draft.events.extend(events)
        self.gaps[stored.id] = stored
        self.task_update = task.model_copy(update={"intent": kind})


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-02 [python-coder]: The mixin declares the attributes and methods the router supplies
#   (type-checker only), so its use of them is checked. (#KernelBootstrapV0/GROUND)
# - 2026-10-01 23:00 [python-coder]: A decline gap records output schema `none`: the kernel
#   produces no report for it, and the classified kind is on the task. (#KernelBootstrapV0/GROUND)
# - 2026-10-01 22:00 [python-coder]: The step lives in the route node (not intake) so a human
#   clarification can reuse the router's park-and-resume machinery; the provisional root contract
#   from intake is replaced here, once, and `Task.intent` records that it was resolved.
#   (#KernelBootstrapV0/INTENT)
# - 2026-10-01 22:00 [python-coder]: A human's own pick from the offered kinds needs no Jev call;
#   free text is re-classified on the goal as clarified. (#KernelBootstrapV0/INTENT)
# ====================================================================
