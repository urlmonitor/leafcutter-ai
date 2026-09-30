"""
MODULE: kernel.service
GOAL: The client-independent application API (RunService protocol), its error types and small
    RunEnvelope builders.
BUSINESS CONTEXT: The CLI, tests, a future MCP tool and other Python code all drive runs through
    four operations; nothing in the scheduler, capabilities or providers may import a client
    adapter (Rev 3 section 5.1).
ARCHITECTURE: P1 defines only the protocol, errors and helpers; KernelService (P7) implements
    the protocol and P9 hardens cancel_run. RunNotFound is re-exported from persistence.base.
"""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from kernel.contracts.base import KernelModel
from kernel.contracts.enums import RunStatus
from kernel.contracts.interaction import InteractionSubmission
from kernel.contracts.run import RunEnvelope
from kernel.contracts.task import Actor, TaskInput
from kernel.persistence.base import RunNotFound

__all__ = ["REJECT_CODES", "CLI_EXIT_CODES", "ErrorBody", "InvalidTaskInput", "ProviderUnavailable",
           "RejectCode", "RunNotFound", "RunService", "SubmissionRejected", "error_payload",
           "new_envelope"]

RejectCode = Literal["stale_submission", "kind_mismatch", "schema_invalid", "semantic_invalid",
                     "conflicting_duplicate", "run_cancelled"]
REJECT_CODES: tuple[str, ...] = ("stale_submission", "kind_mismatch", "schema_invalid",
                                 "semantic_invalid", "conflicting_duplicate", "run_cancelled")
#: CLI exit codes (design part 5): 0 envelope, 2 usage, 3 rejected, 4 unknown run, 5 internal.
CLI_EXIT_CODES: dict[str, int] = {"ok": 0, "usage": 2, "rejected": 3, "run_not_found": 4,
                                  "internal": 5}


class InvalidTaskInput(ValueError):
    """The TaskInput failed validation; no run was created."""

    def __init__(self, detail: str = "") -> None:
        """Build the message from the validation detail."""
        super().__init__(f"invalid task input: {detail}")
        self.detail = detail


class SubmissionRejected(Exception):
    """A submission was rejected; run state is unchanged."""

    def __init__(self, code: RejectCode, message: str = "",
                 details: dict[str, str] | None = None) -> None:
        """Keep the machine code, message and details; the text combines code and message."""
        super().__init__(f"submission rejected ({code}): {message}")
        self.code = code
        self.message = message
        self.details = details or {}


class ProviderUnavailable(Exception):
    """Jev (or another required provider) is unavailable; the run fails without a gap."""

    def __init__(self, provider: str = "jev", reason: str = "") -> None:
        """Build the message from the provider and reason."""
        super().__init__(f"provider unavailable ({provider}): {reason}")
        self.provider = provider
        self.reason = reason


class ErrorBody(KernelModel):
    """The `error` object printed by the CLI for exit codes 3, 4 and 5."""

    code: str
    message: str = ""
    details: dict[str, str] = {}


@runtime_checkable
class RunService(Protocol):
    """The four operations every client uses."""

    async def start_run(self, task_input: TaskInput, *, run_id: str | None = None
                        ) -> RunEnvelope:
        """Validate the input, create the run and drive it until it waits or finishes.

        Raises:
            InvalidTaskInput: The input is invalid (no run is created).
        """

    async def resume_run(self, run_id: str, submission: InteractionSubmission) -> RunEnvelope:
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


def error_payload(code: str, message: str, details: dict[str, str] | None = None,
                  envelope: RunEnvelope | None = None) -> dict:
    """Return the CLI JSON for a rejected call: {"error": {...}, "envelope": <envelope|null>}."""
    body = ErrorBody(code=code, message=message, details=details or {})
    return {"error": body.model_dump(mode="json", exclude={"schema_version"}),
            "envelope": envelope.model_dump(mode="json") if envelope else None}


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:00 [python-coder]: Protocol, errors and envelope helpers only; the exit-code
#   table is data here so P7's CLI and tests share it. (#KernelBootstrapV0/P1)
# ====================================================================
