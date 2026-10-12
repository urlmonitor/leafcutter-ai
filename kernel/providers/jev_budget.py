"""
MODULE: kernel.providers.jev_budget
GOAL: Let the Jev adapter reserve every provider call after the first from the caller's budget
    share, so a chunked assessment cannot silently exceed `max_jev_calls`.
BUSINESS CONTEXT: A decision assessment with more questions than `max_questions_per_call` is sent
    as several provider calls. The capability reserves one call before `assess`; the remaining
    chunks must be reserved by the adapter so budget, usage rows, envelope and trace all count
    provider calls (Kernel V0.1 fix C).
ARCHITECTURE: A ContextVar holds the worker's BudgetPort-like share while its executor runs
    (bound by the scheduler's execute node); the adapter reads it per chunk. With nothing bound
    (routing, intent, tests) every chunk is granted. The module has no kernel imports, so the
    providers layer does not depend on the capabilities layer.
"""

from __future__ import annotations

import contextvars
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Literal, Protocol

_Resource = Literal["jev", "host", "work_item"]


class CallBudget(Protocol):
    """Anything that can reserve one unit of a resource (the capabilities' BudgetPort)."""

    def reserve(self, resource: _Resource) -> bool:
        """Reserve one unit; return False (and reserve nothing) if the limit is reached."""


_BOUND: contextvars.ContextVar[CallBudget | None] = contextvars.ContextVar(
    "jev_call_budget", default=None)


@contextmanager
def bind_call_budget(budget: CallBudget) -> Iterator[None]:
    """Make `budget` the share that extra provider calls of this task are reserved from."""
    token = _BOUND.set(budget)
    try:
        yield
    finally:
        _BOUND.reset(token)


def reserve_extra_call() -> bool:
    """Reserve one more provider call from the bound budget (always granted when none is bound)."""
    budget = _BOUND.get()
    return True if budget is None else budget.reserve("jev")


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: The first provider call of an assessment stays reserved by the
#   capability (ask_jev); the adapter reserves chunks 2..N, so reserved calls equal calls made.
#   (#KernelV01/C)
# ====================================================================
