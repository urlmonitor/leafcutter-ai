"""Typed failures at knowledge infrastructure boundaries.
MODULE: knowledge.errors
GOAL: Provide the scoped knowledge retrieval errors responsibility.
BUSINESS CONTEXT: Make attributable research capabilities reusable and explicitly governed.
ARCHITECTURE: Dependencies point inward to neutral contracts; see docs/architecture/components/knowledge-retrieval.md.
"""

from __future__ import annotations


class KnowledgeError(Exception):
    """Typed infrastructure failure safe to report at transport boundaries."""

    def __init__(self, code: str, message: str, retryable: bool = False) -> None:
        """Store injected dependencies without performing network operations.

        Args:
            code: Stable transport-independent failure category.
            message: Secret-free diagnostic for the caller.
            retryable: Whether a later attempt may succeed without changing input.
        """
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class BackendUnavailable(KnowledgeError):
    """Retryable backend connectivity or execution failure."""

    def __init__(self, message: str = "backend unavailable") -> None:
        """Store injected dependencies without performing network operations.

        Args:
            message: Secret-free diagnostic for the caller.
        """
        super().__init__("unavailable", message, True)


class NotReady(KnowledgeError):
    """Explicit unsupported or unready generation response."""

    def __init__(self, message: str = "not ready") -> None:
        """Store injected dependencies without performing network operations.

        Args:
            message: Secret-free diagnostic for the caller.
        """
        super().__init__("unsupported", message)


class InvalidRequest(ValueError):
    """A transport, scope or budget input failed validation."""


def invalid(message: str) -> None:
    """Raise one named validation failure from pure policy checks.

    Args:
        message: Secret-free diagnostic for the caller.
    """
    raise InvalidRequest(message)


def not_ready(message: str) -> None:
    """Raise an explicit unsupported/readiness response with diagnostic context.

    Args:
        message: Secret-free diagnostic for the caller.
    """
    raise NotReady(message)


class CatalogIOError(ValueError):
    """A configured catalog or candidate artifact could not be safely accessed."""

    def __init__(self, detail: str) -> None:
        """Describe a catalog I/O failure without losing its original cause.

        Args:
            detail: Safe operation-level context.
        """
        messages = {
            "candidate_read": "candidate JSON could not be read",
            "catalog_read": "catalog cannot be read",
            "catalog_write": "catalog activation unavailable; prior snapshot retained",
            "catalog_cleanup": "catalog activation cleanup failed",
        }
        super().__init__(messages[detail])


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 15:46 [python-coder]: Bind verified reusable query versions through scoped retrieval. (#KM-500/TICKET-20261001-KM-500b-3)
