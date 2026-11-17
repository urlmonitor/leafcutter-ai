"""
MODULE: unit_tests/build_orchestration/test_bo4500a_2_ii_trailers.py
GOAL: RED tests for BO-4500a-2-ii -- trailers are the caller's to choose: none
      is added, several are kept, and a retry keeps the same message.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _message_step_support import (  # noqa: E402
    BRAIN_TRAILER,
    OPUS_TRAILER,
    commit_and_read,
    recorded_message,
    scenario,
    write_message,
)


class TestTrailers(unittest.TestCase):
    def test_message_without_trailer_gains_none(self):
        # covers: BO-4500a-2-ii
        # angle: criterion
        """AC BO-4500a-2-ii: subject + body, no Co-Authored-By -> none recorded."""
        sc = scenario(self)
        text = "feat: no credit line\n\nJust a body.\n"
        recorded = commit_and_read(self, sc, text)
        self.assertNotIn("Co-Authored-By", recorded)
        self.assertEqual(recorded, text)

    def test_two_trailers_are_kept_in_order(self):
        # covers: BO-4500a-2-ii
        # angle: criterion
        """AC BO-4500a-2-ii: the Opus trailer then the BrainCandy trailer end the message, in order."""
        sc = scenario(self)
        text = f"feat: two credits\n\nBody.\n\n{OPUS_TRAILER}\n{BRAIN_TRAILER}\n"
        recorded = commit_and_read(self, sc, text)
        self.assertEqual(recorded.splitlines()[-2:], [OPUS_TRAILER, BRAIN_TRAILER])
        self.assertEqual(recorded, text)

    def test_message_after_fixer_retry_equals_the_file(self):
        # covers: BO-4500a-2-ii
        # angle: discrimination
        """AC BO-4500a-2-ii: a fixing check rewrites a.py on run one; the commit lands on run two
        with the caller's message untouched.

        Wrong version caught: amend the body to mention the autofix.
        """
        sc = scenario(self)
        marker = sc.scratch / "fixer_ran_once"
        sc.install_hook(
            f"if [ ! -f '{marker}' ]; then\n"
            f"  touch '{marker}'\n"
            "  echo 'fixed by formatter' > a.py\n"
            "  git add a.py\n"
            "  echo 'fixer...Failed'\n"
            "  exit 1\n"
            "fi\n"
            "exit 0\n"
        )
        text = f"feat: fixer retry\n\nBody stays as written.\n\n{OPUS_TRAILER}\n"
        write_message(sc, text)
        answer = sc.run_step(["a.py"])
        self.assertEqual(answer.get("status"), "committed", answer)
        self.assertTrue(marker.exists(), "the fixing check never ran")
        recorded = recorded_message(sc)
        self.assertEqual(recorded, text)
        self.assertNotIn("autofix", recorded.lower())
        self.assertEqual(sc.committed_text("a.py"), "fixed by formatter\n")


if __name__ == "__main__":
    unittest.main()
