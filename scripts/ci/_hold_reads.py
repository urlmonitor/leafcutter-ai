"""
MODULE: _hold_reads
GOAL: How the hold `Post-merge suite status` names a failed read and retries a transient one:
    the cause wording, the one bounded retry, and the environment knobs for both.
BUSINESS CONTEXT: TQ-600a-13-ix. "Could not look" must never look like "found nothing wrong":
    the two verdict reads (the workflow's state and its run history) either answer in the
    expected shape or the check fails and says why. One transient failure (rate limit, server
    error, timeout, refused connection) is not an outage, so those reads get exactly one retry.
ARCHITECTURE: ``cause_of(exc)`` turns a ``GitHubError`` into the cause text the output and the
    verdict carry, by its ``kind`` (``_github_rest.KINDS``): ``HTTP <code>`` (http), ``timed out``,
    ``connection failed``, ``TLS certificate not verified``, ``not JSON``, ``unexpected shape``
    (shape); any other exception is its type name and a short, path-free message. ``read_with_retry(read, sleep, base_delay)`` runs ``read`` and, only
    for 429, 5xx, timeout or connection failure, once more after ``retry_delay`` (a numeric
    ``Retry-After`` replaces the base delay; either is capped at ``MAX_DELAY_SECONDS``); 401,
    403, 404, a TLS certificate error, a body that is not JSON and one of the wrong shape are never retried. ``sleep`` is
    injected so a test pays nothing. ``timeout_seconds`` and ``base_delay_seconds`` read
    ``POST_MERGE_HOLD_TIMEOUT_SECONDS`` and ``POST_MERGE_HOLD_RETRY_DELAY_SECONDS`` (unusable
    text falls back to the default). ``shape_error`` is the error for a body that parses but is
    not what the read needs.
"""

from __future__ import annotations

import logging
import math
import os
import re
from collections.abc import Callable
from typing import TypeVar

from scripts.ci._github_rest import GitHubError

logger = logging.getLogger("post_merge_hold")

T = TypeVar("T")
TIMEOUT_ENV = "POST_MERGE_HOLD_TIMEOUT_SECONDS"
DELAY_ENV = "POST_MERGE_HOLD_RETRY_DELAY_SECONDS"
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_DELAY_SECONDS = 2.0
MAX_DELAY_SECONDS = 5.0
TOO_MANY_REQUESTS = 429
SERVER_ERROR_FLOOR = 500
CAUSE_SHAPE = "unexpected shape"
MAX_CAUSE_TEXT = 80
PATH_RE = re.compile(r"(?:[A-Za-z]:)?[\\/][^\s'\"():]+")  # a file-system path or URL path: never worth printing


def _env_seconds(name: str, default: float, *, allow_zero: bool) -> float:
    """The environment's number of seconds for ``name`` when it is finite and in range, else ``default``."""
    text = os.environ.get(name, "").strip()
    try:
        value = float(text)
    except ValueError:
        return default
    if not math.isfinite(value) or value < 0 or (value == 0 and not allow_zero):
        return default
    return value


def timeout_seconds() -> float:
    """The per-request timeout the client is built with (default 10 s, never zero)."""
    return _env_seconds(TIMEOUT_ENV, DEFAULT_TIMEOUT_SECONDS, allow_zero=False)


def base_delay_seconds() -> float:
    """The pause before the one retry when the service names none (default 2 s; 0 is allowed)."""
    return min(_env_seconds(DELAY_ENV, DEFAULT_DELAY_SECONDS, allow_zero=True), MAX_DELAY_SECONDS)


def shape_error(what: str) -> GitHubError:
    """The error for an answer that parsed but is not the shape the read needs (never retried)."""
    return GitHubError(f"{what} (unexpected shape)", kind="shape")


def cause_of(exc: BaseException) -> str:
    """The cause named in the output: the HTTP status, or the kind of failure."""
    if not isinstance(exc, GitHubError):
        text = PATH_RE.sub("<path>", str(exc)).strip()[:MAX_CAUSE_TEXT]
        return f"{type(exc).__name__}: {text}" if text else type(exc).__name__
    if exc.status:
        return f"HTTP {exc.status}"
    named = {"timeout": "timed out", "connection": "connection failed", "tls": "TLS certificate not verified", "not_json": "not JSON", "shape": CAUSE_SHAPE}
    return named.get(exc.kind, "request failed")


def is_transient(exc: GitHubError) -> bool:
    """True for 429, 5xx, a timeout or a connection failure; false for everything else (a TLS certificate error included)."""
    if exc.status:
        return exc.status == TOO_MANY_REQUESTS or exc.status >= SERVER_ERROR_FLOOR
    return exc.kind in {"timeout", "connection"}


def retry_delay(exc: GitHubError, base: float) -> float:
    """Seconds to wait before the retry: a numeric ``Retry-After`` when the service sent one, else ``base``; at most the cap."""
    try:
        asked = float(exc.retry_after) if exc.retry_after is not None else None
    except ValueError:  # an HTTP date or other text: not a number of seconds, so the base delay stands
        asked = None
    chosen = asked if asked is not None and math.isfinite(asked) and asked >= 0 else base
    return min(chosen, MAX_DELAY_SECONDS)


def read_with_retry(read: Callable[[], T], sleep: Callable[[float], object], base_delay: float) -> T:
    """Run ``read``; on a transient ``GitHubError`` pause once and run it again. Any other failure, or a second one, raises."""
    try:
        return read()
    except GitHubError as exc:
        if not is_transient(exc):
            raise
        delay = retry_delay(exc, base_delay)
        logger.warning("post-merge hold: a read failed (%s); retrying once after %.1f s", cause_of(exc), delay)
    sleep(delay)
    return read()
