"""
MODULE: unit_tests/build_orchestration/test_bo4500a_2_iii_verbatim_cleanup.py
GOAL: RED tests for BO-4500a-2-iii -- a message line that starts with # or ends
      in blank lines is kept, not tidied away (verbatim cleanup).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _message_step_support import commit_and_read, scenario  # noqa: E402


class TestVerbatimCleanup(unittest.TestCase):
    def test_hash_lines_survive_in_place(self):
        # covers: BO-4500a-2-iii
        # angle: discrimination
        """AC BO-4500a-2-iii: '# covers:' and '#1043' body lines are recorded unchanged, in place.

        Wrong version caught: use the default strip cleanup.
        """
        sc = scenario(self)
        text = (
            "fix: keep hash lines\n"
            "\n"
            "# covers: BO-4500a-2\n"
            "#1043 is the fix this follows\n"
            "closing line\n"
        )
        recorded = commit_and_read(self, sc, text)
        lines = recorded.splitlines()
        self.assertEqual(lines[2:4], ["# covers: BO-4500a-2", "#1043 is the fix this follows"])
        self.assertEqual(recorded, text)

    def test_indentation_and_whitespace_survive(self):
        # covers: BO-4500a-2-iii
        # angle: criterion
        """AC BO-4500a-2-iii: indentation, trailing spaces and blank runs survive byte for byte.

        Wrong version caught: use the whitespace cleanup mode (collapses blank lines).
        """
        sc = scenario(self)
        text = (
            "fix: whitespace\n"
            "\n"
            "    four-space indented\n"
            "trailing spaces   \n"
            "\n"
            "\n"
            "after two blank lines\n"
        )
        recorded = commit_and_read(self, sc, text)
        self.assertIn("    four-space indented\n", recorded)
        self.assertEqual(recorded.encode("utf-8"), text.encode("utf-8"))

    def test_repo_cleanup_config_does_not_change_the_result(self):
        # covers: BO-4500a-2-iii
        # angle: boundary
        """AC BO-4500a-2-iii: commit.cleanup=strip and core.commentChar set -> message still equals the file."""
        sc = scenario(self)
        sc.git("config", "commit.cleanup", "strip")
        sc.git("config", "core.commentChar", ";")
        text = "fix: hostile config\n\n# covers: BO-4500a-2\n; semicolon line\n\n\nend\n"
        recorded = commit_and_read(self, sc, text)
        self.assertEqual(recorded, text)


if __name__ == "__main__":
    unittest.main()
