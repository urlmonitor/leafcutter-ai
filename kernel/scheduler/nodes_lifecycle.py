"""
MODULE: kernel.scheduler.nodes_lifecycle
GOAL: The run bookends: `intake` (normalise TaskInput, create the root request and work item,
    pin the registry) and `finalize` (root completion check, RunOutcome, report artifacts).
BUSINESS CONTEXT: A run may only report `completed` when the root output contract is satisfied
    (Rev 3 section 8.1 step 11): a completed child, a guard stop or a rejected result must end as
    partial, blocked, failed or cancelled with diagnostics, never as a false success.
ARCHITECTURE: intake is idempotent (it does nothing when `task` is set). finalize decides the
    outcome in the pure function `decide_outcome`, then writes report.json and report.md through
    the artifact port; a report write failure becomes a limitation, not a crash.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langgraph.runtime import Runtime

from kernel.contracts import (
    ErrorInfo,
    Evidence,
    EvidenceSource,
    OutputRef,
    PayloadValidationError,
    Priority,
    Provenance,
    Request,
    RequestKind,
    RunStatus,
    SemanticContext,
    SemanticValidationError,
    SemanticType,
    SourceKind,
    Task,
    UnknownSchemaError,
    WorkItem,
    WorkItemStatus,
    content_hash,
    evidence_id,
    new_id,
    schema_ids,
    validate_payload,
    validate_semantics,
)
from kernel.contracts.evidence import EvidenceInput
from kernel.intent.report_text import (
    can_do_hint,
    has_plain_reason,
    output_sections,
    stop_explanation,
)
from kernel.intent.roots import initial_contract
from kernel.observability.correlation import deterministic_trace_id
from kernel.observability.tracer import TraceState
from kernel.scheduler import guards
from kernel.scheduler.context import KernelRuntime, flush_events, run_corr, sequential_node
from kernel.scheduler.state import Budgets, KernelState, RunOutcome, new_event, root_item_id

logger = logging.getLogger(__name__)


class IntakeError(ValueError):
    """The graph input lacks something intake needs."""

    def __init__(self, missing: str) -> None:
        """Build the message from the missing key."""
        super().__init__(f"graph input is missing {missing!r}")
        self.missing = missing


def _input_evidence(inputs: list[EvidenceInput], now: Any) -> dict[str, Evidence]:
    """Convert caller-supplied initial evidence into content-addressed task_context Evidence."""
    out: dict[str, Evidence] = {}
    for index, item in enumerate(inputs):
        locator = item.locator or f"task_input#{index}"
        digest = content_hash(item.excerpt)
        evidence = Evidence(
            id=evidence_id(locator, digest), created_at=now, updated_at=now,
            category=item.category, semantic_type=SemanticType.TASK_CONTEXT,
            excerpt=item.excerpt,
            source=EvidenceSource(id="task_input", kind=SourceKind.TASK_INPUT, locator=locator,
                                  title=item.title),
            content_hash=digest, provenance=Provenance(producer="kernel.intake"))
        out[evidence.id] = evidence
    return out


@sequential_node("intake")
async def intake(state: KernelState, runtime: Runtime[KernelRuntime]) -> dict[str, Any]:
    """Create the task, root request, root work item and initial evidence (idempotent)."""
    if state.get("task") is not None:
        return {}
    for key in ("run_id", "task_input", "registry"):
        if key not in state:
            raise IntakeError(key)
    ctx, task_input, run_id = runtime.context, state["task_input"], state["run_id"]
    now = ctx.clock()
    evidence = _input_evidence(task_input.initial_evidence, now)
    root_task_id = new_id("task")
    stamps: dict[str, Any] = {"created_at": now, "updated_at": now, "created_seq": 0}
    payload = task_input.input_payload
    output_schema, intent = initial_contract(task_input.requested_output_schema,
                                             task_input.input_payload_schema)
    request = Request(
        id=new_id("req"), kind=RequestKind.CAPABILITY, goal=task_input.goal,
        payload_schema=(task_input.input_payload_schema or schema_ids.GOAL_REQUEST)
        if payload is not None else schema_ids.GOAL_REQUEST,
        payload=dict(payload) if payload is not None else {"goal": task_input.goal},
        requested_output_schema=output_schema, context_refs=sorted(evidence), **stamps)
    revision = task_input.scope.revision
    request = request.model_copy(update={"dedup_key": guards.request_dedup_key(
        request, revision.model_dump() if revision else None)})
    root = WorkItem(id=new_id("work"), root_task_id=root_task_id, request_id=request.id,
                    **stamps)
    task = Task(id=root_task_id, root_task_id=root_task_id, original_goal=task_input.goal,
                scope=task_input.scope, evidence_refs=sorted(evidence),
                constraint_refs=[c.id for c in task_input.constraints],
                requested_output_schema=output_schema, intent=intent,
                root_work_item_id=root.id, **stamps)
    events = [new_event(run_id, now, "run.started", task_input.goal[:200], task_id=root_task_id,
                        work_item_id=root.id)]
    events += [new_event(run_id, now, "evidence.added", evidence_id=e) for e in sorted(evidence)]
    return {"task": task, "root_task_id": root_task_id, "permissions": list(task_input.permissions),
            "requests": {request.id: request}, "work_items": {root.id: root},
            "evidence": evidence, "budgets": Budgets(work_items_created=1), "state_revision": 0,
            "status": RunStatus.RUNNING, "agenda": [], "interaction_queue": [],
            "halt_reason": None, "events_flushed": 0, "events": events,
            "trace": state.get("trace") or TraceState(trace_id=deterministic_trace_id(run_id))}


def _error_from_limitation(item: WorkItem) -> ErrorInfo:
    """Return the first `code: message` limitation of an item as an ErrorInfo."""
    if not item.limitations:
        return ErrorInfo(code="failed", message="the root work item failed")
    code, _, message = item.limitations[0].partition(":")
    return ErrorInfo(code=code.strip() or "failed", message=message.strip())


def _completion_problems(state: KernelState, root: WorkItem, task: Task,
                         schema_id: str | None, payload: dict | None) -> list[str]:
    """Return why the root output does not satisfy the contract (empty list: it does)."""
    problems: list[str] = []
    if schema_id != task.requested_output_schema:
        problems.append(f"output_schema_mismatch: {schema_id} is not {task.requested_output_schema}")
    requests = state["requests"]
    open_required = [i.id for i in state["work_items"].values()
                     if requests[i.request_id].priority is Priority.REQUIRED
                     and i.status not in guards.TERMINAL_STATUSES]
    if open_required:
        problems.append(f"required_work_open: {', '.join(sorted(open_required))}")
    if schema_id is not None and payload is not None and not problems:
        ctx = SemanticContext(known_evidence_ids=frozenset(state.get("evidence", {})),
                              known_finding_ids=frozenset(state.get("findings", {})))
        try:
            validate_semantics(schema_id, validate_payload(schema_id, payload), ctx)
        except (PayloadValidationError, SemanticValidationError, UnknownSchemaError) as exc:
            problems.append(f"semantic_invalid: {exc}")
    return problems


def _child_diagnostics(state: KernelState, root: WorkItem) -> list[str]:
    """Return `work-id: limitation` lines for non-root items that did not succeed."""
    lines: list[str] = []
    for item in sorted(state["work_items"].values(), key=lambda i: (i.created_seq, i.id)):
        if item.id != root.id and item.status in (WorkItemStatus.BLOCKED, WorkItemStatus.FAILED):
            lines += [f"{item.id}: {text}" for text in item.limitations]
    return lines


def decide_outcome(state: KernelState) -> RunOutcome:
    """Decide the terminal RunOutcome from the root item, guards and completion contract."""
    task, items = state["task"], state["work_items"]
    root = items[root_item_id(state)]
    result = state.get("results", {}).get(root.result_ref) if root.result_ref else None
    schema_id = result.output_schema_id if result else None
    payload = dict(result.output_payload) if result and result.output_payload else None
    halt = state.get("halt_reason")
    limitations = [*root.limitations, *(result.limitations if result else [])]
    diagnostics = [f"guard: {halt}"] if halt else []
    output = OutputRef(schema_id=schema_id, payload=payload) if schema_id and payload is not None \
        else None
    errors: list[ErrorInfo] = []
    if halt == "cancelled":
        status = RunStatus.CANCELLED
    elif root.status is WorkItemStatus.COMPLETED:
        problems = _completion_problems(state, root, task, schema_id, payload)
        status = RunStatus.PARTIAL if problems else RunStatus.COMPLETED
        limitations += problems
    elif root.status is WorkItemStatus.FAILED:
        status = RunStatus.FAILED
        errors = [result.error] if result and result.error else [_error_from_limitation(root)]
    elif root.status is WorkItemStatus.BLOCKED:
        status = RunStatus.BLOCKED
    elif root.status is WorkItemStatus.PARTIAL:
        status = RunStatus.PARTIAL
    else:
        useful = bool(state.get("evidence")) or any(
            i.status in (WorkItemStatus.COMPLETED, WorkItemStatus.PARTIAL)
            for i in items.values() if i.id != root.id)
        status = RunStatus.PARTIAL if useful else RunStatus.BLOCKED
    if status is RunStatus.COMPLETED:
        limitations = list(dict.fromkeys(limitations))
    else:
        limitations = list(dict.fromkeys([*limitations, *_child_diagnostics(state, root)]))
    if status is RunStatus.BLOCKED and not has_plain_reason(limitations):
        limitations.append(can_do_hint())  # a bare "blocked" says nothing; name what works
    asked = (payload or {}).get("open_questions")
    questions = [str(q) for q in asked] if isinstance(asked, list) else []
    return RunOutcome(status=status, output=output, limitations=limitations, errors=errors,
                      open_questions=questions, diagnostics=diagnostics)


def render_report_md(state: KernelState, outcome: RunOutcome) -> str:
    """Render the human-readable report from a template (no model-written text)."""
    lines = [f"# Run report {state['run_id']}", "", f"- Status: {outcome.status.value}",
             f"- Task: {state['task'].original_goal}"]
    trace = state.get("trace")
    if trace is not None and trace.trace_url:
        lines.append(f"- Trace: {trace.trace_url}")
    lines.append("")
    lines += stop_explanation(outcome.status.value, outcome.limitations)
    if outcome.output is not None:
        lines += output_sections(outcome.output.schema_id, outcome.output.payload)
        lines += ["## Output", "", f"Schema: `{outcome.output.schema_id}`", "", "```json",
                  json.dumps(outcome.output.payload, indent=2, sort_keys=True), "```", ""]
    for title, entries in (("Limitations", outcome.limitations),
                           ("Open questions", outcome.open_questions),
                           ("Diagnostics", outcome.diagnostics)):
        if entries:
            lines += [f"## {title}", "", *[f"- {e}" for e in entries], ""]
    lines += ["## Work items", ""]
    for item in sorted(state["work_items"].values(), key=lambda i: (i.created_seq, i.id)):
        lines.append(f"- {item.id}: {item.status.value} (depth {item.depth})")
    return "\n".join(lines) + "\n"


def _write_report(runtime: KernelRuntime, state: KernelState, outcome: RunOutcome
                  ) -> RunOutcome:
    """Store report.json and report.md; a failure is recorded as a limitation."""
    body = {"run_id": state["run_id"], "status": outcome.status.value,
            "outcome": outcome.model_dump(mode="json"),
            "work_items": [{"id": i.id, "status": i.status.value, "depth": i.depth,
                            "binding": i.binding.capability_id if i.binding else None}
                           for i in sorted(state["work_items"].values(),
                                           key=lambda x: (x.created_seq, x.id))]}
    try:
        ref = runtime.artifacts.write_artifact(state["run_id"], "report.json",
                                               json.dumps(body, indent=2, sort_keys=True))
        runtime.artifacts.write_artifact(state["run_id"], "report.md",
                                         render_report_md(state, outcome))
    except (OSError, ValueError):
        logger.warning("could not write the report of run %s", state["run_id"], exc_info=True)
        return outcome.model_copy(update={"limitations": [*outcome.limitations,
                                                          "report_not_written"]})
    else:
        return outcome.model_copy(update={"report_ref": ref.ref})


@sequential_node("finalize")
async def finalize(state: KernelState, runtime: Runtime[KernelRuntime]) -> dict[str, Any]:
    """Decide and record the terminal outcome of the run."""
    ctx = runtime.context
    outcome = _write_report(ctx, state, decide_outcome(state))
    event = new_event(state["run_id"], ctx.clock(), "run.finished", outcome.status.value)
    ctx.tracer.event("run.finalized", run_corr(state), payload={
        "status": outcome.status.value, "limitation_count": len(outcome.limitations),
        "error_codes": [e.code for e in outcome.errors],
        "open_question_count": len(outcome.open_questions),
        "halt_reason": state.get("halt_reason"), "state_revision": state.get("state_revision", 0)
    })
    return {"status": outcome.status, "outcome": outcome, "events": [event],
            "state_revision": state.get("state_revision", 0) + 1,
            "events_flushed": flush_events(ctx.run_store, state)}


__all__ = ["IntakeError", "decide_outcome", "finalize", "intake", "render_report_md"]

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-02 [python-coder]: mypy: intake narrows the optional payload once; open questions are read as a list (#KernelBootstrapV0/GROUND)
# - 2026-10-01 23:00 [python-coder]: report.md names the Langfuse trace URL when tracing exported
#   one (the envelope already carried it in trace_refs), so a reader of the report can open the
#   trace. (#KernelBootstrapV0/GROUND)
# - 2026-10-01 22:00 [python-coder]: A blocked run without a plain limitation gets a `can_do`
#   hint, and report.md explains blocked and partial stops and renders evidence and idea outputs
#   readably (ideas as proposals) before the unchanged JSON block. (#KernelBootstrapV0/INTENT)
# - 2026-10-01 00:30 [python-coder]: `run.finalized` is a tracer event inside the finalize span
#   (status and counts only; limitation text stays in run.json). (#KernelBootstrapV0/OBS)
# - 2026-09-30 22:30 [python-coder]: A root that completed but fails the completion contract
#   is reported `partial` (with the problems as limitations) rather than `completed`; the work
#   is useful but the contract is not met. (#KernelBootstrapV0/P4)
# ====================================================================
