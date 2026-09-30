"""
MODULE: kernel.interaction.ledger
GOAL: The submission entry point a client adapter calls: validate against the paused run, write
    the idempotency ledger entry, then resume the graph; identical replays are no-ops, conflicting
    or stale ones are rejected, and invalid host output is repaired a bounded number of times.
BUSINESS CONTEXT: A process can die at any moment around an accepted submission (Rev 3 section
    13.1). The ledger entry is written before the graph resumes, so a restart never loses an
    accepted answer, and first-write-wins means it is never applied twice or overwritten.
ARCHITECTURE: Steps: cancelled? -> ledger lookup by interaction id (same hash: replay or finish
    an interrupted resume; other hash: conflicting duplicate) -> `check_submission` -> ledger
    write -> `Command(resume=...)`. Content-invalid host output is the one rejection that does
    reach the graph (without a ledger entry) because the repair counter lives in the checkpointed
    packet; everything else is rejected without touching the graph, so state is never changed.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from langgraph.types import Command
from pydantic import ValidationError

from kernel.contracts import CorrelationIds, HostWorkRequest, InteractionSubmission
from kernel.interaction.submissions import (
    RejectionCode,
    Verdict,
    check_submission,
    pending_packet,
    submission_hash,
)
from kernel.persistence.base import RunStorePort, SubmissionRecord

logger = logging.getLogger(__name__)


class SubmissionRejected(Exception):
    """A submission was refused; the run state is unchanged (apart from a repair counter)."""

    def __init__(self, code: RejectionCode, message: str, details: dict[str, Any] | None = None
                 ) -> None:
        """Keep the stable code, the message and the structured details."""
        super().__init__(f"{code.value}: {message}")
        self.code = code
        self.message = message
        self.details = dict(details or {})

    def to_error(self) -> dict[str, Any]:
        """Return the `{code, message, details}` object of the CLI error payload."""
        return {"code": self.code.value, "message": self.message, "details": self.details}


class SubmitStatus(StrEnum):
    """What a call to `submit_interaction` did."""

    ACCEPTED = "accepted"
    REPLAYED = "replayed"
    REPAIR_EXHAUSTED = "repair_exhausted"


@dataclass
class SubmitResult:
    """Result of an accepted (or replayed) submission.

    Attributes:
        status: Accepted, an idempotent replay, or repairs exhausted (the item failed).
        interaction_id: The interaction the submission addressed.
        state: The graph state values after the call (paused or final).
        pending: The next pending packet as JSON, if the run paused again.
    """

    status: SubmitStatus
    interaction_id: str
    state: dict[str, Any] = field(default_factory=dict)
    pending: dict[str, Any] | None = None


def _parse(raw: Mapping[str, Any]) -> InteractionSubmission:
    """Parse a raw submission or raise a schema_invalid rejection."""
    try:
        return InteractionSubmission.model_validate(dict(raw))
    except ValidationError as exc:
        raise SubmissionRejected(RejectionCode.SCHEMA_INVALID, "the submission has invalid fields",
                                 {"detail": str(exc)[:1500]}) from exc


def _ledger_entry(run_store: RunStorePort, run_id: str, raw: object) -> SubmissionRecord | None:
    """Return the ledger entry for the interaction a raw submission names, if any."""
    if not isinstance(raw, Mapping) or raw.get("run_id") != run_id:
        return None
    interaction_id = raw.get("interaction_id")
    return run_store.get_submission(run_id, interaction_id) \
        if isinstance(interaction_id, str) else None


def _paused(snapshot: Any) -> bool:
    """True if the checkpointed graph is waiting on an interrupt."""
    return any(getattr(task, "interrupts", ()) for task in snapshot.tasks)


async def _invoke(graph: Any, config: dict[str, Any], context: Any, value: Any) -> Any:
    """Run the graph from its checkpoint (`value` is a resume Command or None)."""
    return await graph.ainvoke(value, config, context=context, version="v2", durability="sync")


def _result(status: SubmitStatus, interaction_id: str, out: Any) -> SubmitResult:
    """Build the SubmitResult from a GraphOutput."""
    pending = out.interrupts[0].value if out.interrupts else None
    return SubmitResult(status, interaction_id, dict(out.value), pending)


async def _replay(graph: Any, config: dict[str, Any], context: Any, snapshot: Any,
                  interaction_id: str) -> SubmitResult:
    """Answer an identical replay: a no-op, except finishing a run that died mid-flight."""
    if snapshot.next and not _paused(snapshot):
        out = await _invoke(graph, config, context, None)
        return _result(SubmitStatus.REPLAYED, interaction_id, out)
    values = dict(snapshot.values)
    packet = pending_packet(values)
    return SubmitResult(SubmitStatus.REPLAYED, interaction_id, values,
                        packet.model_dump(mode="json") if packet else None)


async def _repair(graph: Any, config: dict[str, Any], context: Any, raw: Mapping[str, Any],
                  verdict: Verdict) -> SubmitResult:
    """Count one invalid host submission in the graph; reject it or report the exhausted item."""
    interaction_id = str(raw["interaction_id"])
    out = await _invoke(graph, config, context, Command(resume=dict(raw)))
    packet = out.interrupts[0].value if out.interrupts else None
    if packet is None or packet.get("id") != interaction_id:
        return _result(SubmitStatus.REPAIR_EXHAUSTED, interaction_id, out)
    allowed = context.config.host.max_repair_attempts
    raise SubmissionRejected(verdict.code, verdict.message,
                             {**verdict.details, "interaction_id": interaction_id,
                              "repairs_remaining": max(0, allowed - len(packet["rejections"])),
                              "pending_interaction": packet})


async def _accept(run_store: RunStorePort, graph: Any, config: dict[str, Any], context: Any,
                  run_id: str, submission: InteractionSubmission, *, write: bool
                  ) -> SubmitResult:
    """Write the ledger entry (unless it exists) and then resume the graph."""
    if write:
        record = SubmissionRecord(run_id=run_id, interaction_id=submission.interaction_id,
                                  sha256=submission_hash(submission), submission=submission)
        try:
            run_store.record_submission(record)
        except OSError:
            logger.exception("could not write the ledger entry of %s", submission.interaction_id)
            raise
    out = await _invoke(graph, config, context, Command(resume=submission.model_dump(mode="json")))
    return _result(SubmitStatus.ACCEPTED, submission.interaction_id, out)


async def submit_interaction(graph: Any, config: dict[str, Any], context: Any,
                             run_store: RunStorePort, run_id: str, raw: object) -> SubmitResult:
    """Validate a submission, persist it in the ledger and resume the paused run.

    Args:
        graph: The compiled kernel graph (with the checkpointer that holds the run).
        config: The LangGraph config of the run (`thread_id` equal to the run id).
        context: The `KernelRuntime` of this process.
        run_store: Run store holding run.json, interactions and the submission ledger.
        run_id: The run the submission is for.
        raw: The submission exactly as received (parsed JSON; never trusted).

    Returns:
        SubmitResult: Accepted, an identical replay, or repair-exhausted with the state after.

    Raises:
        SubmissionRejected: Refused; the code is one of `RejectionCode`. RunNotFound propagates
            from the run store for an unknown run.
    """
    try:
        return await _submit(graph, config, context, run_store, run_id, raw)
    except SubmissionRejected as exc:
        interaction_id = raw.get("interaction_id") if isinstance(raw, Mapping) else None
        context.tracer.event(
            "submission.rejected", CorrelationIds(
                run_id=run_id, interaction_id=interaction_id if isinstance(
                    interaction_id, str) else None),
            level="WARNING", payload={"code": exc.code.value})
        raise


async def _submit(graph: Any, config: dict[str, Any], context: Any,
                  run_store: RunStorePort, run_id: str, raw: object) -> SubmitResult:
    """Run the submission steps; `submit_interaction` documents the contract."""
    record = run_store.get_run(run_id)
    if record.cancel is not None:
        raise SubmissionRejected(RejectionCode.CANCELLED_OR_SUPERSEDED, "the run was cancelled",
                                 {"cancelled_by": record.cancel.by})
    snapshot = await graph.aget_state(config)
    values = dict(snapshot.values)
    entry = _ledger_entry(run_store, run_id, raw)
    if entry is not None:
        submission = _parse(raw)  # type: ignore[arg-type]
        if submission_hash(submission) != entry.sha256:
            raise SubmissionRejected(RejectionCode.NOT_PENDING,
                                     "this interaction was already answered differently",
                                     {"reason": "conflicting_duplicate",
                                      "interaction_id": entry.interaction_id})
        head = pending_packet(values)
        if head is not None and head.id == entry.interaction_id:
            return await _accept(run_store, graph, config, context, run_id, entry.submission,
                                 write=False)
        return await _replay(graph, config, context, snapshot, entry.interaction_id)
    verdict = check_submission(raw, values)
    if verdict.ok and verdict.submission is not None:
        return await _accept(run_store, graph, config, context, run_id, verdict.submission,
                             write=True)
    if verdict.repairable and isinstance(pending_packet(values), HostWorkRequest):
        return await _repair(graph, config, context, raw, verdict)  # type: ignore[arg-type]
    raise SubmissionRejected(verdict.code or RejectionCode.SCHEMA_INVALID, verdict.message,
                             verdict.details)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:55 [python-coder]: The ledger is keyed by interaction id with first-write-wins
#   (P2), so "same hash" means idempotent and "different hash" means conflicting duplicate; the
#   latter is reported as not_pending with details.reason=conflicting_duplicate.
#   (#KernelBootstrapV0/P6)
# - 2026-09-30 23:55 [python-coder]: Invalid host output is the only rejection that resumes the
#   graph, without a ledger entry, because a repair counter kept anywhere but in the checkpoint
#   (the paused node's replayed resume values) would be lost on restart. (#KernelBootstrapV0/P6)
# ====================================================================
