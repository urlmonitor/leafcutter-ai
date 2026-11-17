"""
MODULE: unit_tests/build_orchestration/test_bo4500a_2_ii_retry_only_after_a_fix.py
GOAL: The retry BO-4500a-2-ii keeps the message across is earned only by a fixing
      check that actually rewrote a file the commit carries.

BO-4500a-3 (approved) says a judging check's failure gets no in-call retry. A
blanket "retry once whenever a hook failed" would run a judging check twice, and a
flaky judging check that passed on its second run would let the commit through.
These tests count real hook invocations through the REAL step.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _message_step_support import scenario, write_message  # noqa: E402


class TestRetryOnlyAfterAFix(unittest.TestCase):
    def test_judging_failure_is_not_retried(self):
        # covers: BO-4500a-2-ii
        # angle: discrimination
        """A check that fails without rewriting anything runs once; the answer is hook_failed.

        Wrong version caught: retrying on any hook failure (the check would run twice).
        """
        sc = scenario(self)
        log = sc.scratch / "judge_runs"
        sc.install_hook(f"echo run >> '{log}'\necho 'judge...Failed'\nexit 1\n")
        write_message(sc, "feat: judged\n")
        commits_before = sc.commit_count()

        answer = sc.run_step(["a.py"])

        self.assertEqual(answer.get("status"), "hook_failed", answer)
        self.assertEqual(log.read_text().count("run"), 1, "the judging check was run more than once")
        self.assertEqual(sc.commit_count(), commits_before, "a commit was recorded")

    def test_flaky_judge_that_passes_second_time_does_not_get_a_second_chance(self):
        # covers: BO-4500a-2-ii
        # angle: discrimination
        """A judging check that would pass on a second run still blocks the commit.

        Wrong version caught: a blanket retry lets a flaky judge wave the commit through.
        """
        sc = scenario(self)
        marker = sc.scratch / "judge_failed_once"
        sc.install_hook(
            f"if [ ! -f '{marker}' ]; then\n"
            f"  touch '{marker}'\n"
            "  echo 'judge...Failed'\n"
            "  exit 1\n"
            "fi\n"
            "exit 0\n"
        )
        write_message(sc, "feat: flaky judge\n")
        commits_before = sc.commit_count()

        answer = sc.run_step(["a.py"])

        self.assertEqual(answer.get("status"), "hook_failed", answer)
        self.assertEqual(sc.commit_count(), commits_before, "the flaky judge let the commit through")

    def test_fixer_that_leaves_its_change_unstaged_still_earns_the_retry(self):
        # covers: BO-4500a-2-ii
        # angle: boundary
        """A fixing check that rewrites a.py WITHOUT staging it (the common formatter
        shape) still earns the one retry, and the rewritten content is committed."""
        sc = scenario(self)
        marker = sc.scratch / "fixer_ran_once"
        sc.install_hook(
            f"if [ ! -f '{marker}' ]; then\n"
            f"  touch '{marker}'\n"
            "  echo 'formatted' > a.py\n"
            "  echo 'fixer...Failed'\n"
            "  exit 1\n"
            "fi\n"
            "exit 0\n"
        )
        write_message(sc, "feat: unstaged fixer\n")

        answer = sc.run_step(["a.py"])

        self.assertEqual(answer.get("status"), "committed", answer)
        self.assertEqual(sc.committed_text("a.py"), "formatted\n")


if __name__ == "__main__":
    unittest.main()
