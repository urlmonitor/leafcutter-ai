"""Request deadline context propagated into worker-thread adapter transactions."""

from __future__ import annotations

from contextvars import ContextVar
import time

deadline = ContextVar("knowledge_deadline", default=None)


def remaining_seconds(default: float) -> float:
    """Return the smaller configured timeout and remaining request deadline.

    Args:
        default: Maximum seconds when no tighter request deadline is active.

    Returns:
        float: Positive remaining seconds, capped by the caller maximum.
    """
    end = deadline.get()
    if end is None:
        return default
    remaining = end - time.monotonic()
    if remaining <= 0:
        raise TimeoutError
    return min(default, remaining)
