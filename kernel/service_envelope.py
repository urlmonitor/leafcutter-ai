"""
MODULE: kernel.service_envelope
GOAL: Build the RunEnvelope a client sees from the run record and the checkpointed graph state.
BUSINESS CONTEXT: Clients drive runs purely from the envelope (Rev 3 section 7.9), so it must
    agree with both the durable run.json and the graph state, and must never claim success the
    kernel did not reach.
ARCHITECTURE: Pure functions over plain values (no IO), so the service, its error paths and the
    tests share one mapping. Status precedence: a cancellation in run.json wins, then a terminal
    graph status, then a terminal record status (set by the service when a guard stopped the
    graph without a finalize), then the graph's own status.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from kernel.contracts.capability import ErrorInfo
from kernel.contracts.enums import ObservabilityStatus, RunStatus
from kernel.contracts.run import RunEnvelope, TraceRefs, UsageSummary
from kernel.interaction import pending_packet
from kernel.observability.tracer import TraceState
from kernel.persistence.base import RunRecord

TERMINAL = frozenset({RunStatus.COMPLETED, RunStatus.PARTIAL, RunStatus.BLOCKED,
                      RunStatus.FAILED, RunStatus.CANCELLED})


def effective_status(record: RunRecord, values: Mapping[str, Any]) -> RunStatus:
    """Return the status to report, following the precedence in the module docstring."""
    if record.cancel is not None:
        return RunStatus.CANCELLED
    graph_status = values.get("status")
    if graph_status in TERMINAL:
        return RunStatus(graph_status)
    if record.status in TERMINAL:
        return record.status
    return RunStatus(graph_status) if graph_status is not None else record.status


def _usage(values: Mapping[str, Any]) -> UsageSummary:
    """Summarise the budget counters (tokens stay unknown: the kernel does not sum them)."""
    budgets = values.get("budgets")
    if budgets is None:
        return UsageSummary()
    nothing_known = budgets.cost_unknown_calls > 0 and budgets.cost_usd_known == 0.0
    return UsageSummary(jev_calls=budgets.jev_calls, host_operations=budgets.host_operations,
                        cost_usd_known=None if nothing_known else budgets.cost_usd_known,
                        cost_unknown_calls=budgets.cost_unknown_calls)


def build_envelope(record: RunRecord, values: Mapping[str, Any], *,
                   trace: TraceState | None, observability: ObservabilityStatus,
                   diagnostics: list[str] | None = None, report_path: str | None = None
                   ) -> RunEnvelope:
    """Build the envelope for a run.

    Args:
        record: The run.json record (status, revision, cancellation).
        values: The checkpointed graph state values (empty before the first superstep).
        trace: This process's trace identity, else the one stored in the record.
        observability: Export health after the segment closed.
        diagnostics: Extra limitation lines (for example a tripped recursion limit).
        report_path: Absolute path of the rendered report; replaces the artifact name in
            `report_ref` so a client can open it without knowing the run layout.

    Returns:
        RunEnvelope: A valid envelope; waiting statuses carry their packet, terminal ones none.
    """
    status = effective_status(record, values)
    outcome = values.get("outcome")
    waiting = status in (RunStatus.WAITING_HOST, RunStatus.WAITING_HUMAN)
    limitations = [*(outcome.limitations if outcome else []), *(diagnostics or [])]
    errors = list(outcome.errors) if outcome else []
    if status is RunStatus.FAILED and not errors:
        errors = _failure_errors(diagnostics)
    shown = trace or record.trace
    return RunEnvelope(
        run_id=record.run_id, root_task_id=values.get("root_task_id") or record.root_task_id,
        state_revision=values.get("state_revision", record.state_revision), status=status,
        output=outcome.output if outcome and status is RunStatus.COMPLETED else None,
        report_ref=(report_path or outcome.report_ref) if outcome else None,
        decision_ids=sorted(values.get("decisions", {})),
        evidence_ids=sorted(values.get("evidence", {})),
        open_questions=list(outcome.open_questions) if outcome else [],
        pending_interaction=pending_packet(values) if waiting else None,
        limitations=limitations, gaps=list(values.get("gaps", {}).values()),
        usage_summary=_usage(values), errors=errors,
        trace_refs=TraceRefs(trace_id=shown.trace_id if shown else None,
                             trace_url=shown.trace_url if shown else None,
                             observability=observability))


def _failure_errors(diagnostics: list[str] | None) -> list[ErrorInfo]:
    """Return one generic ErrorInfo for a failed run whose outcome carried none."""
    detail = "; ".join(diagnostics or []) or "the run failed"
    return [ErrorInfo(code="failed", message=detail)]


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 16:50 [python-coder]: When every call's cost is unknown the envelope reports
#   cost_usd_known as null, not 0.0 (Rev 3 section 16, unknown billing); a partly known cost
#   keeps its sum plus cost_unknown_calls. (#KernelBootstrapV0/P10)
# - 2026-10-01 10:30 [python-coder]: A terminal record status outranks a non-terminal graph
#   status so a run the service stopped (recursion limit) stays blocked even though the graph
#   never reached finalize. (#KernelBootstrapV0/P7)
# ====================================================================
