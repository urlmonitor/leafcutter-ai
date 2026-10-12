"""
MODULE: test_bo_400e_4_repeatability
GOAL: Cover ADR-048 Decision 6 -- a second build-feature.js run over the same
    four tickets, restored to the same state, must produce the same four
    answers as the first run.
BUSINESS CONTEXT: Covers ADR-048 (docs/architecture/adrs/ADR-048-order-
    independent-per-ticket-completion.md). See test_bo_400e_4_fixtures for
    the full fixture-shape rationale. Combined with the control ticket, this
    also proves the repeatability observed here is not the trivial
    repeatability of a writer that refuses everything (ADR-048 Decision 7).
ARCHITECTURE: Carried out of test_bo_400e_4.py (GE-127a-1 / GE-127b-1
    file-size split, no behaviour change). Subclasses
    test_bo_400e_4_fixtures._FourTicketOneRunCase and reuses its
    _assert_three_refused_one_written() shared assertion.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _driver_harness as H  # noqa: E402
from test_bo_400e_4_fixtures import ALL_LABELS, _FourTicketOneRunCase  # noqa: E402

# ---------------------------------------------------------------------------
# 3 -- a second run over the same four tickets reproduces the first run
# ---------------------------------------------------------------------------


class TestASecondRunOverTheSameFourTicketsProducesTheSameFourAnswers(
    _FourTicketOneRunCase
):
    def test_a_second_run_over_the_same_four_tickets_produces_the_same_four_answers(
        self,
    ):
        # covers: BO-400e-4
        # angle: criterion
        """Restore the same four tickets to the same state and drive a
        SECOND full run, asserting the four answers match the first run's
        four answers exactly (ADR-048 Decision 6). Combined with the control
        ticket it also proves the repeatability is not the trivial
        repeatability of a writer that refuses everything (ADR-048
        Decision 7)."""
        order = list(ALL_LABELS)

        worktree1 = self._worktree()
        observation1, paths1 = self._drive(worktree1, order=order)
        self._assert_three_refused_one_written("run 1", observation1, paths1)

        # The SAME four tickets, restored to the SAME state -- a fresh
        # worktree standing in for "restore the same four tickets to the
        # same state", since each run must observe its own real on-disk
        # records rather than the first run's already-mutated ones.
        worktree2 = self._worktree()
        observation2, paths2 = self._drive(worktree2, order=order)
        self._assert_three_refused_one_written("run 2", observation2, paths2)

        for label in ALL_LABELS:
            record1 = H.read_record(paths1[label])
            record2 = H.read_record(paths2[label])
            self.assertEqual(
                record1["lifecycle_status"],
                record2["lifecycle_status"],
                f"ticket {label}: the two runs disagree on the final lifecycle "
                f"status -- run 1={record1['lifecycle_status']!r}, "
                f"run 2={record2['lifecycle_status']!r}. One run cannot give two "
                f"answers to one question.",
            )
