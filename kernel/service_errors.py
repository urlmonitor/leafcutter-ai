"""
MODULE: kernel.service_errors
GOAL: The application-service error types and the CLI error payload builder.
BUSINESS CONTEXT: Clients map these errors to exit codes and JSON; they live apart from the
    service so the session and envelope helpers can raise them without importing the service.
ARCHITECTURE: `SubmissionRejected` is the interaction layer's class (stable `RejectionCode`s,
    `to_error()`), re-exported here so clients import every error from one place. RunNotFound
    comes from persistence.base. Nothing here imports the scheduler.
"""

from __future__ import annotations

from typing import Any

from pydantic import JsonValue

from kernel.contracts.base import KernelModel
from kernel.contracts.run import RunEnvelope
from kernel.interaction.ledger import SubmissionRejected
from kernel.persistence.base import RunNotFound

__all__ = ["CLI_EXIT_CODES", "ErrorBody", "InvalidTaskInput", "ProviderUnavailable",
           "RegistryChanged", "RunIdTaken", "RunNotFound", "RunRecordContended",
           "SubmissionRejected", "error_payload"]

#: CLI exit codes (design part 5): 0 envelope, 2 usage, 3 rejected, 4 unknown run, 5 internal.
CLI_EXIT_CODES: dict[str, int] = {"ok": 0, "usage": 2, "rejected": 3, "run_not_found": 4,
                                  "internal": 5}


class InvalidTaskInput(ValueError):
    """The TaskInput failed validation; no run was created."""

    def __init__(self, detail: str = "") -> None:
        """Build the message from the validation detail."""
        super().__init__(f"invalid task input: {detail}")
        self.detail = detail


class RunIdTaken(InvalidTaskInput):
    """The caller-chosen run id already names a run."""

    def __init__(self, run_id: str) -> None:
        """Build the message from the run id."""
        super().__init__(f"run id {run_id} already exists")
        self.run_id = run_id


class ProviderUnavailable(Exception):
    """Jev (or another required provider) is unavailable; the run fails without a gap."""

    def __init__(self, provider: str = "jev", reason: str = "") -> None:
        """Build the message from the provider and reason."""
        super().__init__(f"provider unavailable ({provider}): {reason}")
        self.provider = provider
        self.reason = reason


class RunRecordContended(RuntimeError):
    """run.json kept changing under the compare-and-update; the status was not written."""

    def __init__(self, run_id: str) -> None:
        """Build the message from the run id."""
        super().__init__(f"run.json of {run_id} kept changing; update not written")
        self.run_id = run_id


class RegistryChanged(Exception):
    """The capability registry no longer matches the snapshot the run pinned."""

    def __init__(self, pinned: str, current: str) -> None:
        """Build the message from the two content hashes."""
        super().__init__(f"registry changed since the run started ({pinned} -> {current})")
        self.pinned = pinned
        self.current = current


class ErrorBody(KernelModel):
    """The `error` object printed by the CLI for exit codes 3, 4 and 5."""

    code: str
    message: str = ""
    details: dict[str, JsonValue] = {}


def error_payload(code: str, message: str, details: dict[str, Any] | None = None,
                  envelope: RunEnvelope | None = None) -> dict:
    """Return the CLI JSON for a failed call: {"error": {...}, "envelope": <envelope|null>}."""
    body = ErrorBody(code=code, message=message, details=details or {})
    return {"error": body.model_dump(mode="json", exclude={"schema_version"}),
            "envelope": envelope.model_dump(mode="json") if envelope else None}


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 11:00 [python-coder]: Moved out of service.py and the P1 RejectCode vocabulary
#   dropped: P6's SubmissionRejected and RejectionCode are the single rejection contract (their
#   codes, including details.pending_interaction, are what the CLI prints). (#KernelBootstrapV0/P7)
# ====================================================================
