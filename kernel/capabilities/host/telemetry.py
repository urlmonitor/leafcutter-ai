"""
MODULE: kernel.capabilities.host.telemetry
GOAL: Record one `host.<operation>` observation per host interaction: the packet text and its
    fingerprint, the template, the time to answer, the host-reported usage and the outcome.
BUSINESS CONTEXT: Rev 3 section 11.7: record the exact submitted packet, the result, the elapsed
    time and any usage the host reports; unknown billing or token counts stay unavailable, never
    zero and never inferred. This is how a developer sees in Langfuse what the host was asked.
ARCHITECTURE: One tracer event built from values the graph node already holds. The packet was
    redacted before it was stored, so its text is safe to record. Telemetry never decides
    anything: it reads the packet, the submission and the result and returns nothing.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from kernel.capabilities.host.spec import parse_compiled_by
from kernel.contracts import (
    CapabilityResult,
    CorrelationIds,
    HostWorkRequest,
    InteractionSubmission,
    ResultStatus,
)
from kernel.observability.tracer import Tracer


def _usage_payload(submission: InteractionSubmission | None) -> list[dict[str, Any]] | None:
    """Return the host-reported usage as plain dicts, or None when the host reported none."""
    if submission is None or not submission.usage:
        return None
    return [u.model_dump(mode="json") for u in submission.usage]


def host_event_payload(packet: HostWorkRequest, submission: InteractionSubmission | None,
                       result: CapabilityResult, now: datetime) -> dict[str, Any]:
    """Return the payload of the `host.<operation>` event (plain JSON values only)."""
    ref = parse_compiled_by(packet.output_requirements)
    usage = _usage_payload(submission)
    return {
        "operation": packet.operation, "interaction_id": packet.id, "attempt": packet.attempt,
        "template": f"{ref.template_id}@{ref.template_version}" if ref else None,
        "prompt_fingerprint": ref.fingerprint if ref else None,
        "prompt": packet.goal, "requirements": list(packet.output_requirements),
        "output_schema_id": packet.output_schema_id, "repairs": len(packet.rejections),
        "elapsed_ms": max(0, int((now - packet.created_at).total_seconds() * 1000)),
        "usage_available": usage is not None, "usage": usage,
        "actor_kind": submission.actor.kind.value if submission else None,
        "result_status": result.status.value, "evidence_count": len(result.evidence),
        "finding_count": len(result.findings), "limitations": list(result.limitations)}


def emit_host_telemetry(tracer: Tracer, corr: CorrelationIds, packet: HostWorkRequest,
                        submission: InteractionSubmission | None, result: CapabilityResult,
                        now: datetime) -> None:
    """Record the `host.<operation>` event (WARNING when the host work failed)."""
    failed = result.status is ResultStatus.FAILED
    tracer.event(f"host.{packet.operation}", corr, level="WARNING" if failed else "DEFAULT",
                 payload=host_event_payload(packet, submission, result, now))


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 11:45 [python-coder]: An event, not a span: the kernel does not run host work, so
#   it cannot time it; `elapsed_ms` is the time from opening the packet to accepting the answer
#   and honestly includes any wait. (#KernelBootstrapV0/P8)
# ====================================================================
