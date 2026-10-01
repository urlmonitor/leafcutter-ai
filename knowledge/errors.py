"""Typed failures at knowledge infrastructure boundaries."""

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
