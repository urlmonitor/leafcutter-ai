"""Per-request timing of the name-lookup, connect and query steps of one retrieval.

MODULE: knowledge.step_timing
GOAL: Report where retrieval time went and which step a deadline miss happened in.
BUSINESS CONTEXT: A deadline miss must name its step so operators can tell a stalled name lookup from a slow query.
ARCHITECTURE: The service installs one recorder per request in a context variable; the Neo4j adapter feeds it from its worker thread.

DECISION HISTORY
========================================
- 2026-10-23 12:00 [python-coder]: Add per-request step timings and deadline-step attribution. (#KM-400d-4-iii)
"""

from __future__ import annotations

from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
import threading
import time

STEPS = ("resolve", "connect", "query")
STEP_NAMES = {"resolve": "name lookup", "connect": "connect", "query": "query"}

recorder_var: ContextVar[StepRecorder | None] = ContextVar("knowledge_step_recorder", default=None)


class StepRecorder:
    """Thread-safe accumulator of step durations; a step never reached stays None."""

    def __init__(self) -> None:
        """Start with no step reached."""
        self._lock = threading.Lock()
        self._done: dict[str, float | None] = dict.fromkeys(STEPS)
        self._open: dict[str, tuple[float, float]] = {}
        self._from_memory: bool | None = None

    def open(self, step: str) -> None:
        """Mark a step as started now.

        Args:
            step: One of ``STEPS``.
        """
        with self._lock:
            # Only a name lookup is "reached" on open: connect and query first spend their time on
            # name lookups made inside them, so they are reached once they close or are counted
            # as the step a deadline miss happened in (see snapshot/close).
            if self._done[step] is None and step == "resolve":
                self._done[step] = 0.0
            self._open[step] = (time.monotonic(), self._done["resolve"] or 0.0)

    def close(self, step: str) -> None:
        """Add the elapsed time of an open step; connect and query exclude the lookups inside them.

        Args:
            step: One of ``STEPS``.
        """
        with self._lock:
            started, resolve_base = self._open.pop(step)
            elapsed = time.monotonic() - started
            if step != "resolve":
                elapsed -= (self._done["resolve"] or 0.0) - resolve_base
            # A step's own time never goes negative, however the lookups nested in it overlapped.
            self._done[step] = (self._done[step] or 0.0) + max(elapsed, 0.0)

    def note_lookup(self, from_memory: bool) -> None:
        """Record whether a lookup was answered from the process memory.

        Args:
            from_memory: True when no resolver call was made.
        """
        with self._lock:
            self._from_memory = (
                from_memory if self._from_memory is None else self._from_memory and from_memory
            )

    def snapshot(self, missed: bool) -> dict | None:
        """Return the additive stats fields, or None when no step was ever reached.

        Args:
            missed: Whether the request deadline was missed; steps still open are then counted
                up to now and the earliest open step is named.

        Returns:
            Stats fields ``resolve_ms``, ``connect_ms``, ``query_ms``, ``resolve_from_memory``
            and ``deadline_step``, or None.
        """
        with self._lock:
            now = time.monotonic()
            values = dict(self._done)
            step = None
            if missed:
                open_resolve = (now - self._open["resolve"][0]) if "resolve" in self._open else 0.0
                for name in STEPS:
                    if name not in self._open or (name != "resolve" and "resolve" in self._open):
                        continue
                    extra = now - self._open[name][0]
                    if name != "resolve":
                        total = (self._done["resolve"] or 0.0) + open_resolve
                        extra -= total - self._open[name][1]
                    values[name] = (values[name] or 0.0) + max(extra, 0.0)
                    step = step or STEP_NAMES[name]
            if all(value is None for value in values.values()):
                return None
            fields: dict[str, int | bool | str | None] = {}
            for name in STEPS:
                seconds = values[name]
                fields[f"{name}_ms"] = None if seconds is None else round(seconds * 1000)
            fields["resolve_from_memory"] = self._from_memory
            fields["deadline_step"] = step
            return fields


def timed(recorder: StepRecorder | None, step: str):
    """Context manager timing one step on a recorder (a no-op without one).

    Args:
        recorder: Active recorder, if any.
        step: One of ``STEPS``.

    Returns:
        A context manager that opens the step on entry and closes it on exit.
    """
    if recorder is None:
        return nullcontext()
    return _timed(recorder, step)


@contextmanager
def _timed(recorder: StepRecorder, step: str):
    """Open and always close one step.

    Args:
        recorder: Active recorder.
        step: One of ``STEPS``.

    Yields:
        None while the step runs.
    """
    recorder.open(step)
    try:
        yield
    finally:
        recorder.close(step)
