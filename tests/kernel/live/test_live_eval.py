"""
MODULE: tests.kernel.live.test_live_eval
GOAL: Run the labelled evaluation set against the live kernel and report the scored table.
BUSINESS CONTEXT: Rev 3 section 16: report how the live kernel behaves on unanswerable,
    missing-information, contradictory and out-of-scope requests instead of assuming calibration;
    the only hard assertions are structural (every case ran, the Jev budget held).
ARCHITECTURE: Skipped unless LEAFCUTTER_KERNEL_LIVE=1 (skipif only). Delegates to eval_runner.
"""

from __future__ import annotations

import unittest

import pytest

from tests.kernel.live.eval_runner import MAX_TOTAL_JEV_CALLS, render, run_eval
from tests.kernel.live.live_support import LIVE, SKIP_REASON


@pytest.mark.skipif(not LIVE, reason=SKIP_REASON)
class TestLiveEval(unittest.TestCase):
    """Score the live kernel on the labelled set."""

    def test_the_labelled_set_is_scored_and_the_jev_budget_holds(self) -> None:
        report = run_eval()
        print("\n" + render(report))
        self.assertEqual(len(report["rows"]), report["total"])
        self.assertLessEqual(report["jev_calls"], MAX_TOTAL_JEV_CALLS)
        for row in report["rows"]:
            self.assertTrue(row["within_budget"], f"{row['id']} exceeded its Jev call cap")


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 17:35 [python-coder]: Calibration is reported by eval_runner.render, never
#   asserted here, as the spec requires. (#KernelBootstrapV0/P10)
# ====================================================================
