"""
MODULE: kernel.service
GOAL: The client-independent application API: the RunService protocol and KernelService, which
    implements start, resume, get and cancel over the compiled graph, the file stores and the
    tracer.
BUSINESS CONTEXT: The CLI, tests, a future MCP tool and other Python code all drive runs through
    four operations; nothing in the scheduler, capabilities or providers may import a client
    adapter (Rev 3 section 5.1). The service is the only writer of run.json status and
    state_revision, so a client never sees a status the kernel did not durably record.
ARCHITECTURE: Each call opens one process segment (`open_session`: trace segment, checkpointer,
    Jev adapter, graph), drives the graph, flushes the events the finish node could not, updates
    run.json and builds the envelope after the segment closed (so `observability` is accurate).
    Failures never corrupt state: a rejected submission leaves the checkpoint untouched, and a
    tripped LangGraph recursion limit is recorded as a blocked run with diagnostics.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Protocol, runtime_checkable

from langgraph.errors import GraphRecursionError

from kernel.bootstrap import KernelEnvironment
from kernel.contracts import new_id
from kernel.contracts.base import utc_now
from kernel.contracts.enums import RunStatus
from kernel.contracts.interaction import InteractionSubmission
from kernel.contracts.run import RunEnvelope
from kernel.contracts.task import Actor, TaskInput
from kernel.interaction import SubmissionRejected, submit_interaction
from kernel.persistence.base import CancelInfo, RunAlreadyExists, RunRecord
from kernel.registry.adapter import RegistryCompatibilityError, verify_pinned
from kernel.scheduler import flush_events, initial_state
from kernel.service_envelope import TERMINAL, build_envelope, effective_status
from kernel.service_errors import (
    CLI_EXIT_CODES,
    ErrorBody,
    InvalidTaskInput,
    ProviderUnavailable,
    RegistryChanged,
    RunIdTaken,
    RunNotFound,
    error_payload,
)
from kernel.service_session import Session, open_session

logger = logging.getLogger(__name__)

__all__ = ["CLI_EXIT_CODES", "ErrorBody", "InvalidTaskInput", "KernelService",
           "ProviderUnavailable", "RegistryChanged", "RunNotFound", "RunService",
           "SubmissionRejected", "error_payload", "new_envelope"]

Values = dict[str, Any]


@runtime_checkable
class RunService(Protocol):
    """The four operations every client uses."""

    async def start_run(self, task_input: TaskInput, *, run_id: str | None = None
                        ) -> RunEnvelope:
        """Validate the input, create the run and drive it until it waits or finishes.

        Raises:
            InvalidTaskInput: The input is invalid (no run is created).
        """

    async def resume_run(self, run_id: str, submission: InteractionSubmission | Mapping[str, Any]
                         ) -> RunEnvelope:
        """Apply a host or human submission to the pending interaction and continue.

        Raises:
            RunNotFound: Unknown run id.
            SubmissionRejected: Stale, wrong-kind, invalid or conflicting submission.
        """

    async def get_run(self, run_id: str) -> RunEnvelope:
        """Return the current envelope without changing state.

        Raises:
            RunNotFound: Unknown run id.
        """

    async def cancel_run(self, run_id: str, actor: Actor) -> RunEnvelope:
        """Cancel the run (idempotent) and return the cancelled envelope.

        Raises:
            RunNotFound: Unknown run id.
        """


def new_envelope(run_id: str, root_task_id: str, state_revision: int, status: RunStatus,
                 **fields: object) -> RunEnvelope:
    """Build a validated RunEnvelope (status/interaction invariants are enforced).

    Args:
        run_id: Run id.
        root_task_id: Root task id.
        state_revision: Current state revision.
        status: Run status.
        **fields: Any other RunEnvelope fields.

    Returns:
        RunEnvelope: The envelope.
    """
    return RunEnvelope(run_id=run_id, root_task_id=root_task_id, state_revision=state_revision,
                       status=status, **fields)


class KernelService:
    """RunService over one composed KernelEnvironment (one process segment per call)."""

    def __init__(self, env: KernelEnvironment) -> None:
        """Bind the service to its environment."""
        self._env = env

    # ---- public API --------------------------------------------------
    async def start_run(self, task_input: TaskInput, *, run_id: str | None = None
                        ) -> RunEnvelope:
        """Create the run record, drive the graph to its first pause or end, return the envelope.

        Raises:
            InvalidTaskInput: The run id is already taken.
            ProviderUnavailable: No Jev credential is configured (no run is created).
        """
        env = self._env
        self._require_jev()
        run_id = run_id or new_id("run")
        record = RunRecord(run_id=run_id, root_task_id="pending",
                           registry_hash=env.snapshot.content_hash)
        try:
            env.run_store.create_run(record)
        except RunAlreadyExists as exc:
            raise RunIdTaken(run_id) from exc
        guard: list[str] = []
        async with open_session(env, "start", run_id) as session:
            state = initial_state(run_id, task_input, env.snapshot)
            state["trace"] = session.trace
            values = await self._guarded(session, guard, lambda: self._ainvoke(session, state))
        return self._finish(session, values, guard)

    async def resume_run(self, run_id: str, submission: InteractionSubmission | Mapping[str, Any]
                         ) -> RunEnvelope:
        """Submit an answer to the pending interaction through the ledger and continue the run.

        Raises:
            RunNotFound: Unknown run id.
            SubmissionRejected: Refused; `.envelope` carries the current envelope.
            RegistryChanged: The registry differs from the snapshot the run pinned.
            ProviderUnavailable: No Jev credential is configured.
        """
        env = self._env
        record = env.run_store.get_run(run_id)
        self._require_jev()
        raw = submission.model_dump(mode="json") if isinstance(
            submission, InteractionSubmission) else submission
        guard: list[str] = []
        rejection: SubmissionRejected | None = None
        async with open_session(env, "resume", run_id, record.root_task_id) as session:
            self._require_pinned_registry(await session.values())
            try:
                values = await self._guarded(session, guard, lambda: self._submit(
                    session, run_id, raw))
            except SubmissionRejected as exc:
                rejection, values = exc, await session.values()
        if rejection is not None:
            rejection.envelope = self._finish(session, values, guard, persist=False)
            raise rejection
        return self._finish(session, values, guard)

    async def get_run(self, run_id: str) -> RunEnvelope:
        """Return the current envelope (a `status` trace segment; no state change)."""
        record = self._env.run_store.get_run(run_id)
        async with open_session(self._env, "status", run_id, record.root_task_id) as session:
            values = await session.values()
        return self._finish(session, values, [], persist=False)

    async def cancel_run(self, run_id: str, actor: Actor) -> RunEnvelope:
        """Mark the run cancelled (idempotent); later submissions are refused.

        A run that already reached a terminal status is returned unchanged. P9 hardens this
        (stopping in-flight work, cancelling children).
        """
        env = self._env
        record = env.run_store.get_run(run_id)
        async with open_session(env, "cancel", run_id, record.root_task_id) as session:
            values = await session.values()
            if effective_status(record, values) not in TERMINAL:
                now = utc_now()
                self._persist(record.model_copy(update={
                    "cancel": CancelInfo(by=actor.id, at=now), "status": RunStatus.CANCELLED,
                    "updated_at": now}))
                env.tracer.event("run.cancelled", session.runtime_corr(), level="WARNING",
                                 payload={"by": actor.id})
        return self._finish(session, values, [], persist=False)

    # ---- internals ---------------------------------------------------
    def _require_jev(self) -> None:
        """Raise ProviderUnavailable before any state is created when Jev has no credential."""
        if self._env.jev_factory is None:
            raise ProviderUnavailable("jev", "no Jev API key is configured")

    async def _ainvoke(self, session: Session, state: Values) -> Values:
        """Run the graph from the initial state and return the state values."""
        out = await session.graph.ainvoke(state, session.config, context=session.runtime,
                                          version="v2", durability="sync")
        return dict(out.value)

    async def _submit(self, session: Session, run_id: str, raw: object) -> Values:
        """Submit through the ledger (validate, write, resume) and return the state values."""
        result = await submit_interaction(session.graph, session.config, session.runtime,
                                          self._env.run_store, run_id, raw)
        return result.state

    async def _guarded(self, session: Session, diagnostics: list[str],
                       call: Callable[[], Awaitable[Values]]) -> Values:
        """Run `call`; a tripped recursion limit becomes diagnostics and the last checkpoint."""
        try:
            return await call()
        except GraphRecursionError:
            limit = self._env.config.limits.langgraph_recursion_limit
            logger.warning("run %s hit the LangGraph recursion limit (%s)", session.run_id, limit)
            diagnostics.append(f"guard: langgraph_recursion_limit ({limit} supersteps) reached")
            return await session.values()

    def _require_pinned_registry(self, values: Mapping[str, Any]) -> None:
        """Refuse to continue an unfinished run whose pinned registry no longer matches."""
        pinned = values.get("registry")
        if pinned is None or values.get("status") in TERMINAL:
            return
        try:
            verify_pinned(pinned, self._env.snapshot)
        except RegistryCompatibilityError as exc:
            raise RegistryChanged(pinned.content_hash, self._env.snapshot.content_hash) from exc

    def _persist(self, record: RunRecord) -> None:
        """Write run.json; the store is the only durable status, so a failure is raised."""
        try:
            self._env.run_store.update_run(record)
        except OSError:
            logger.exception("could not write run.json of %s", record.run_id)
            raise

    def _finish(self, session: Session, values: Values, diagnostics: list[str], *,
                persist: bool = True) -> RunEnvelope:
        """Mirror leftover events, update run.json (when `persist`) and build the envelope."""
        env = self._env
        record = env.run_store.get_run(session.run_id)
        if persist and values:
            flush_events(env.run_store, values)
            record = self._updated_record(record, session, values, bool(diagnostics))
            self._persist(record)
        return build_envelope(record, values, trace=session.trace,
                              observability=session.observability, diagnostics=diagnostics,
                              report_path=self._report_path(session.run_id, values))

    def _report_path(self, run_id: str, values: Mapping[str, Any]) -> str | None:
        """Return the absolute path of the Markdown report (else the JSON one) when it exists."""
        outcome = values.get("outcome")
        if outcome is None or not outcome.report_ref:
            return None
        for ref in ("report.md", outcome.report_ref):
            try:
                path = self._env.artifacts.absolute_path(run_id, ref)
            except (KeyError, ValueError):
                logger.warning("no path for report %s of %s", ref, run_id, exc_info=True)
                continue
            if path:
                return path
        return None

    @staticmethod
    def _updated_record(record: RunRecord, session: Session, values: Mapping[str, Any],
                        blocked: bool) -> RunRecord:
        """Return the record with the service-owned status, revision, root task and trace."""
        status = RunStatus.BLOCKED if blocked else effective_status(record, values)
        return record.model_copy(update={
            "status": status, "updated_at": utc_now(), "trace": session.trace,
            "state_revision": values.get("state_revision", record.state_revision),
            "root_task_id": values.get("root_task_id") or record.root_task_id})


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 11:10 [python-coder]: The envelope is built after the segment closed so
#   trace_refs.observability reflects the flush, and a rejection carries the current envelope
#   on the exception (one segment per process). (#KernelBootstrapV0/P7)
# - 2026-10-01 11:10 [python-coder]: The run record is created before the first graph call: the
#   ledger reads it for cancellation, and a crash before the first checkpoint still leaves a
#   diagnosable run. (#KernelBootstrapV0/P7)
# - 2026-10-01 11:10 [python-coder]: Only the service writes run.json status; cancellation is a
#   record flag the graph polls between supersteps (P9 hardens in-flight cancellation).
#   (#KernelBootstrapV0/P7)
# - 2026-09-30 22:00 [python-coder]: Protocol, errors and envelope helper only; the exit-code
#   table is data so the CLI and tests share it. (#KernelBootstrapV0/P1)
# ====================================================================
