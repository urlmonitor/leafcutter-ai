"""
MODULE: kernel.providers.jev_errors
GOAL: Re-export the port-level Jev errors and define the adapter-internal errors.
BUSINESS CONTEXT: Callers must see exactly the error types ScriptedJev raises (defined in
    providers/base.py in P1); the adapter additionally needs an internal "retry me" signal and an
    explicit error for malformed caller questions, neither of which may leak to graphs as a
    capability gap.
ARCHITECTURE: No redefinition of JevUnavailable, JevInvalidResponse or JevPayloadTooLarge; they
    are imported and re-exported. JevTransientError never escapes JevAdapter.assess: exhausted
    retries are converted to JevUnavailable there.
"""

from __future__ import annotations

from kernel.providers.base import (
    JevError,
    JevInvalidResponse,
    JevPayloadTooLarge,
    JevUnavailable,
)

__all__ = [
    "JevBudgetExhausted", "JevError", "JevInvalidRequest", "JevInvalidResponse",
    "JevPayloadTooLarge", "JevTransientError", "JevUnavailable",
]


class JevTransientError(JevError):
    """A retryable provider failure (rate limit, 5xx, timeout, connection) from a transport."""

    def __init__(self, reason: str, retry_after_seconds: float | None = None) -> None:
        """Keep the reason and the server-requested delay, if any."""
        super().__init__(reason)
        self.reason = reason
        self.retry_after_seconds = retry_after_seconds


class JevBudgetExhausted(JevUnavailable):
    """The caller's Jev budget refused a further provider call of a chunked assessment."""

    def __init__(self, reason: str = "jev call budget exhausted") -> None:
        """Keep the reason as the message."""
        super().__init__(reason)


class JevInvalidRequest(JevError, ValueError):
    """The caller built a question the adapter cannot send (a programming error, not Jev's)."""

    def __init__(self, reason: str = "invalid jev request") -> None:
        """Keep the reason as the message."""
        super().__init__(reason)
        self.reason = reason


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: JevBudgetExhausted subclasses JevUnavailable so existing callers
#   (ask_jev, the executor) map it to a provider_unavailable result without new handling.
#   (#KernelV01/C)
# - 2026-09-30 23:00 [python-coder]: Port errors are re-exported from base.py, not redefined;
#   only adapter-internal errors live here. (#KernelBootstrapV0/P3)
# ====================================================================
