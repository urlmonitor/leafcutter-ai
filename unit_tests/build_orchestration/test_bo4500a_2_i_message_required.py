"""
MODULE: unit_tests/build_orchestration/test_bo4500a_2_i_message_required.py
GOAL: RED tests for BO-4500a-2-i -- no message, an empty message or an
      unreadable message file means no commit.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _commit_step_support import STEP  # noqa: E402
from _message_step_support import scenario, write_message  # noqa: E402

import json  # noqa: E402


def _run_closed_stdin(sc, argv):
    """Run the real step with stdin closed and a short timeout."""
    return subprocess.run(
        [sys.executable, str(STEP), *argv],
        cwd=sc.repo,
        env=sc.env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


class TestMessageRequired(unittest.TestCase):
    def test_missing_message_file_argument_is_refused(self):
        # covers: BO-4500a-2-i
        # angle: failure
        """AC BO-4500a-2-i: no message file -> refused, policy_message_missing, no commit, a.py unstaged."""
        sc = scenario(self)
        head = sc.head()
        proc = _run_closed_stdin(sc, ["a.py"])
        answer = json.loads(proc.stdout)
        self.assertEqual(answer.get("status"), "refused", answer)
        self.assertEqual(answer.get("reason_code"), "policy_message_missing")
        self.assertIn("message file", (answer.get("reason") or "").lower())
        self.assertEqual(sc.head(), head)
        self.assertEqual(sc.staged_names(), [])

    def test_nonexistent_and_blank_message_files_are_refused_with_distinct_codes(self):
        # covers: BO-4500a-2-i
        # angle: discrimination
        """AC BO-4500a-2-i: not-found vs blank-only are different codes, each naming the file.

        Wrong versions caught: fall back to a default message; report both
        conditions with one code.
        """
        sc = scenario(self)
        head = sc.head()
        missing = sc.scratch / "no-such-message.txt"
        proc = _run_closed_stdin(sc, ["--message-file", str(missing), "a.py"])
        gone = json.loads(proc.stdout)
        self.assertEqual(gone.get("status"), "refused", gone)
        self.assertEqual(gone.get("reason_code"), "policy_message_not_found")
        self.assertIn(str(missing), gone.get("reason") or "")

        write_message(sc, "\n   \n\n  \n")
        proc = _run_closed_stdin(sc, ["--message-file", str(sc.message_file), "a.py"])
        blank = json.loads(proc.stdout)
        self.assertEqual(blank.get("status"), "refused", blank)
        self.assertEqual(blank.get("reason_code"), "policy_message_empty")
        self.assertIn(str(sc.message_file), blank.get("reason") or "")

        self.assertEqual(sc.head(), head, "a commit was recorded")
        self.assertEqual(sc.staged_names(), [])
        # control: a real message does commit, so the refusals were about the message
        write_message(sc, "feat: real message\n")
        control = json.loads(_run_closed_stdin(sc, ["--message-file", str(sc.message_file), "a.py"]).stdout)
        self.assertEqual(control.get("status"), "committed", control)

    def test_refusal_never_opens_an_editor_or_waits_for_input(self):
        # covers: BO-4500a-2-i
        # angle: boundary
        """AC BO-4500a-2-i: GIT_EDITOR sentinel never runs; step answers promptly with stdin closed."""
        sc = scenario(self)
        sentinel = sc.scratch / "editor_ran"
        editor = sc.scratch / "editor.sh"
        editor.write_text(f"#!/bin/sh\ntouch '{sentinel}'\n", encoding="utf-8")
        editor.chmod(0o755)
        sc.env["GIT_EDITOR"] = str(editor)
        sc.env["EDITOR"] = str(editor)
        sc.env["VISUAL"] = str(editor)
        blank = sc.scratch / "blank.txt"
        blank.write_text("  \n\n", encoding="utf-8")
        cases = [
            ["a.py"],
            ["--message-file", str(sc.scratch / "absent.txt"), "a.py"],
            ["--message-file", str(blank), "a.py"],
        ]
        for argv in cases:
            with self.subTest(argv=argv):
                proc = _run_closed_stdin(sc, argv)
                answer = json.loads(proc.stdout)
                self.assertEqual(answer.get("status"), "refused", answer)
                self.assertTrue(str(answer.get("reason_code", "")).startswith("policy_message_"), answer)
                self.assertFalse(sentinel.exists(), "an editor was opened")


if __name__ == "__main__":
    unittest.main()
