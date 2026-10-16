"""
MODULE: unit_tests/build_orchestration/test_bo4500a_2_message_from_file.py
GOAL: RED tests for BO-4500a-2 -- the message the caller wrote is the message
      that lands, author credit included, whoever runs the step.

Every test runs the real script (templates/scripts/commit_changes.py) as a
subprocess on a scratch repo and reads the message back from the commit object.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _message_step_support import (  # noqa: E402
    OPUS_TRAILER,
    commit_and_read,
    scenario,
)

FIVE_PART = (
    "fix(build): stage the parent with the child\n"
    "\n"
    "Body line one.\n"
    "Body line two.\n"
    "\n"
    f"{OPUS_TRAILER}\n"
)


class TestMessageFromFile(unittest.TestCase):
    def test_recorded_message_is_identical_to_the_file_line_for_line(self):
        # covers: BO-4500a-2
        # angle: criterion
        """AC BO-4500a-2: the recorded message equals the five-part file, line for line."""
        sc = scenario(self)
        recorded = commit_and_read(self, sc, FIVE_PART)
        self.assertEqual(recorded.splitlines(), FIVE_PART.splitlines())
        self.assertEqual(recorded, FIVE_PART)

    def test_trailer_names_the_caller_model_not_the_running_agent(self):
        # covers: BO-4500a-2
        # angle: discrimination
        """AC BO-4500a-2: with a Claude Sonnet 5 runner, the trailer still names Opus 5.5.

        Wrong versions caught: the step appends its own Co-Authored-By footer;
        the step substitutes the running model's name into the trailer.
        """
        sc = scenario(self)
        sc.env["CLAUDE_MODEL"] = "claude-sonnet-5"
        sc.env["ANTHROPIC_MODEL"] = "claude-sonnet-5"
        recorded = commit_and_read(self, sc, FIVE_PART)
        trailers = [ln for ln in recorded.splitlines() if ln.startswith("Co-Authored-By:")]
        self.assertEqual(trailers, [OPUS_TRAILER])
        self.assertNotIn("Sonnet", recorded)

    def test_step_adds_removes_or_changes_no_message_line(self):
        # covers: BO-4500a-2
        # angle: criterion
        """AC BO-4500a-2: across a corpus, the recorded message never gains/loses/alters a line."""
        corpus = [
            "feat: no trailer\n\nplain body\n",
            f"feat: two trailers\n\nbody\n\n{OPUS_TRAILER}\nCo-Authored-By: Other <o@example.com>\n",
            "feat: hash lines\n\n# covers: BO-4500a-2\n#1043 is the fix\nafter\n",
            "feat: indented\n\n    four spaces\n\ttab line\nend\n",
            "feat: blank run\n\npara one\n\n\n\npara two\n",
        ]
        for text in corpus:
            with self.subTest(text=text):
                sc = scenario(self)
                recorded = commit_and_read(self, sc, text)
                self.assertEqual(recorded, text)


if __name__ == "__main__":
    unittest.main()
