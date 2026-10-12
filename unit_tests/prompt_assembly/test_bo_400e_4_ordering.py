"""
MODULE: test_bo_400e_4_ordering
GOAL: Cover the load-bearing case of the BO-400e-4 suite -- four tickets in
    one run receive one answer per condition -- and its order-independence
    corollary: the answer must not move with the order the run reaches the
    four tickets.
BUSINESS CONTEXT: Covers ADR-048 (docs/architecture/adrs/ADR-048-order-
    independent-per-ticket-completion.md). See test_bo_400e_4_fixtures for
    the full fixture-shape rationale (the identical trio + control ticket,
    and why this must be driven as ONE build-feature.js run rather than four
    independent single-ticket runs). ADR-048 Decision 5: order-independence
    is a property of the DECISION, not of the fixture -- canonically sorting
    the input would not satisfy this, so this suite drives the same fixture
    under several explicit permutations of reach-order.
ARCHITECTURE: Carried out of test_bo_400e_4.py (GE-127a-1 / GE-127b-1
    file-size split, no behaviour change). Both classes here subclass
    test_bo_400e_4_fixtures._FourTicketOneRunCase and reuse its
    _assert_three_refused_one_written() shared assertion.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_bo_400e_4_fixtures import ALL_LABELS, _FourTicketOneRunCase  # noqa: E402

# ---------------------------------------------------------------------------
# 1 -- THE LOAD-BEARING CASE: four tickets, one run, one answer per condition
# ---------------------------------------------------------------------------


class TestFourTicketsInOneRunReceiveOneAnswerThreeRefusedOneWritten(
    _FourTicketOneRunCase
):
    def test_four_tickets_in_one_run_receive_one_answer_three_refused_one_written(
        self,
    ):
        # covers: BO-400e-4
        # angle: boundary
        """Drive FOUR tickets through the real workflow in ONE run: three in
        the identical state (same phases named needed, every one signed off
        except the same single phase -- pr-reviewer -- in all three, which
        has no sign-off) plus a fourth whose every needed phase is signed
        off. Assert the three receive the same answer as each other, that
        the answer is refusal (no recorded state changed, the same
        outstanding phase named in each), and that the fourth is written
        finished. FOUR SEPARATE SINGLE-TICKET RUNS DO NOT REPRODUCE THIS:
        the defect is the disagreement between tickets inside one run."""
        worktree = self._worktree()
        observation, paths = self._drive(worktree, order=list(ALL_LABELS))
        self._assert_three_refused_one_written("one run", observation, paths)


# ---------------------------------------------------------------------------
# 2 -- order-independence: the decision must not move with reach-order
# ---------------------------------------------------------------------------


class TestAnswersDoNotVaryWithTheOrderTheRunReachesTheFourTickets(
    _FourTicketOneRunCase
):
    def test_answers_do_not_vary_with_the_order_the_run_reaches_the_four_tickets(
        self,
    ):
        # covers: BO-400e-4
        # angle: criterion
        """Re-drive THE SAME four-tickets-in-one-run fixture with the
        tickets permuted -- including runs in which the control ticket is
        reached first and last -- and assert each ticket's answer is
        unchanged by its position. The observed split correlated with
        position in the run (ticket 01 refused, 03 and 20 written), so an
        answer that moves with order has relocated the disagreement rather
        than removed it (ADR-048 Decision 5: order-independence is a
        property of the DECISION, not of the fixture -- canonically sorting
        the input would not satisfy this). Must reuse the one-run fixture:
        permuting four independent single-ticket runs proves nothing."""
        orders = [
            ["A", "B", "C", "D"],  # control reached LAST
            ["D", "A", "B", "C"],  # control reached FIRST
            ["C", "B", "A", "D"],  # identical trio reversed, control last
            ["B", "D", "C", "A"],  # control reached in the middle
        ]
        for order in orders:
            with self.subTest(order=order):
                worktree = self._worktree()
                observation, paths = self._drive(worktree, order=order)
                self._assert_three_refused_one_written(
                    f"order={order}", observation, paths
                )
