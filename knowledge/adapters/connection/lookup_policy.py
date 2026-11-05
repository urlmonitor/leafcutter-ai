"""IPv4-first name lookups scoped to the graph adapter's own worker calls.

MODULE: knowledge.adapters.connection.lookup_policy
GOAL: Keep a stalled IPv6 name lookup from consuming the retrieval deadline.
BUSINESS CONTEXT: On hosts where the AAAA lookup stalls, a cold retrieval must still fit the default deadline.
ARCHITECTURE: One process-wide wrapper around socket.getaddrinfo acts only on threads inside an adapter scope; all other callers pass straight through.

DECISION HISTORY
========================================
- 2026-10-23 12:00 [python-coder]: IPv4-first lookup with fallback and per-process memory, opt-out via LEAFCUTTER_NEO4J_ADDRESS_FAMILY=any. (#KM-400d-4-i)
"""

from __future__ import annotations

from contextlib import contextmanager
import logging
import os
import socket
import threading

from knowledge.step_timing import StepRecorder, timed

logger = logging.getLogger(__name__)

FAMILY_SETTING = "LEAFCUTTER_NEO4J_ADDRESS_FAMILY"
_local = threading.local()
_lock = threading.Lock()
_remembered: dict[tuple, list] = {}
_original = None


def read_family_setting() -> tuple[str, str | None]:
    """Read the address-family setting.

    Returns:
        ``("ipv4", warning)`` or ``("any", None)``; an unrecognised value acts as ipv4-first
        and yields a warning naming the setting.
    """
    raw = os.environ.get(FAMILY_SETTING, "")
    value = raw.strip().lower()
    if value in {"", "ipv4"}:
        return "ipv4", None
    if value == "any":
        return "any", None
    return "ipv4", f"{FAMILY_SETTING}={raw!r} is not recognised; using IPv4-first lookups"


def _lookup(host, port, family, type_, proto, flags, mode):
    """Resolve one name for an adapter thread: remembered, IPv4-first, then the normal lookup.

    Args:
        host: Name to resolve.
        port: Port the answer is for.
        family: Requested family (always 0 here).
        type_: Socket type.
        proto: Protocol.
        flags: Resolver flags.
        mode: ``"ipv4"`` or ``"any"``.

    Returns:
        The resolver answer list and whether it came from memory.
    """
    if mode == "any":
        return _original(host, port, family, type_, proto, flags), False
    key = (host, port, type_, proto, flags)
    with _lock:
        if key in _remembered:
            return list(_remembered[key]), True
    try:
        found = _original(host, port, socket.AF_INET, type_, proto, flags)
    except OSError as exc:
        logger.warning("IPv4 lookup of %s failed (%s); using the normal lookup", host, exc)
        found = _original(host, port, family, type_, proto, flags)
    with _lock:
        _remembered[key] = list(found)
    return found, False


def _guarded(host, port, family=0, type=0, proto=0, flags=0):  # noqa: A002 - socket signature
    """Replacement for socket.getaddrinfo: act only inside an adapter scope.

    Args:
        host: Name to resolve.
        port: Port the answer is for.
        family: Requested family.
        type: Socket type.
        proto: Protocol.
        flags: Resolver flags.

    Returns:
        The resolver answer list.
    """
    scope = getattr(_local, "scope", None)
    if scope is None or int(family) != 0:
        return _original(host, port, family, type, proto, flags)
    recorder, mode, touched = scope
    with timed(recorder, "resolve"):
        found, from_memory = _lookup(host, port, family, type, proto, flags, mode)
    touched.add((host, port, type, proto, flags))
    if recorder is not None:
        recorder.note_lookup(from_memory)
    return found


def _install() -> None:
    """Wrap socket.getaddrinfo exactly once for the process; never re-wrap.

    The resolver in place at the first call is captured as the pass-through target. Anything that
    wraps or patches ``socket.getaddrinfo`` later either chains through ``_guarded`` (fine: it
    reaches the captured original) or replaces it (the policy then simply stays out of the way).
    Re-wrapping would capture such a replacement as the original and recurse through it.
    """
    global _original
    with _lock:
        if _original is None and socket.getaddrinfo is not _guarded:
            _original = socket.getaddrinfo
            socket.getaddrinfo = _guarded


def forget_scope_lookups() -> None:
    """Evict the remembered addresses this thread's current scope resolved (a connect to them failed)."""
    scope = getattr(_local, "scope", None)
    if scope is None:
        return
    with _lock:
        for key in scope[2]:
            _remembered.pop(key, None)
        scope[2].clear()


@contextmanager
def lookup_scope(recorder: StepRecorder | None, mode: str):
    """Mark the current thread as inside the adapter's own calls.

    Args:
        recorder: Step recorder fed with lookup timings, if any.
        mode: ``"ipv4"`` or ``"any"``.

    Yields:
        None while lookups on this thread follow the policy.
    """
    _install()
    _local.scope = (recorder, mode, set())
    try:
        yield
    finally:
        _local.scope = None
