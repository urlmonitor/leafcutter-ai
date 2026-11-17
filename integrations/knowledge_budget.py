"""Retain the research requester's reserve on the existing worker budget.

MODULE: knowledge_budget
GOAL: Bound graph planning without creating a second usage ledger.
BUSINESS CONTEXT: Optional graph decisions must leave room for the final assessment.
ARCHITECTURE: A view delegates reservations to the scheduler's actual worker share.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace

from kernel.capabilities.base import BudgetPort, BudgetResource, ExecutionContext
from kernel.providers.jev_budget import bind_call_budget


class ReservedBudget:
    """Expose only the spendable portion of the existing worker budget."""

    def __init__(self, delegate: BudgetPort, reserve: int) -> None:
        """Keep the actual reservation owner and the requester's reserved Jev calls.

        Args:
            delegate: Existing scheduler budget that owns the usage ledger.
            reserve: Jev calls to retain for the requester.
        """
        self.delegate = delegate
        self.jev_reserve = reserve

    def available(self, resource: BudgetResource) -> int | None:
        """Return the delegate's allowance after protecting the Jev reserve.

        Args:
            resource: Resource whose remaining allowance is requested.

        Returns:
            Spendable units, or None when the underlying budget is unbounded.
        """
        probe = getattr(self.delegate, "available", None)
        left = probe(resource) if callable(probe) else None
        if left is None:
            return None
        return max(0, int(left) - (self.jev_reserve if resource == "jev" else 0))

    def reserve(self, resource: BudgetResource) -> bool:
        """Charge the real delegate exactly once if the protected allowance permits it."""
        left = self.available(resource)
        if left is not None and left < 1:
            return False
        return self.delegate.reserve(resource)


@contextmanager
def preserve_jev_reserve(ctx: ExecutionContext, reserve: int) -> Iterator[ExecutionContext]:
    """Bind first and additional provider chunks to one reserve-preserving budget view.

    Args:
        ctx: Actual execution context owning the scheduler's worker share.
        reserve: Jev calls retained for the requester by the persisted input contract.

    Yields:
        Context using the same ledger with the protected reserve withheld.
    """
    if reserve == 0:
        yield ctx
        return
    budget = ReservedBudget(ctx.budget, reserve)
    with bind_call_budget(budget):
        yield replace(ctx, budget=budget)

# DECISION HISTORY
# - 2026-10-02 04:42 [python-coder]: Protect research reserves while charging every graph provider chunk to the existing share. (#TICKETLESS reason=kernel-v01-integration)
