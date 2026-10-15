"""
MODULE: unit_tests/build_orchestration/test_bo4500a_3_check_sequence.py
GOAL: BO-4500a-3 -- the project's checks run first over the named files, a fixing
      check's rewrite is taken in and the checks re-run, a judging check's failure
      gets no second run, and the working tree keeps the fixer's edits.

REACHABILITY ENTRY POINT: the real script `templates/scripts/commit_changes.py`
run as a subprocess against a real scratch git repository whose pre-commit hook
counts its own invocations. Assertions read the invocation log and git.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bo4500a3_support import as_list, install_checks, run_count, run_lines, scenario3  # noqa: E402

_FORMATTER = """
if [ "$n" = "1" ]; then
  ran format-py
  echo 'formatted' > a.py
  report format-py Failed
  echo '- files were modified by this hook'
  exit 1
fi
ran format-py
exit 0
"""


class TestCheckSequence(unittest.TestCase):
    def test_checks_run_once_over_named_files_before_any_commit(self):
        # covers: BO-4500a-3
        # angle: criterion
        """Passing checks run exactly once over a.py and notes.md, before the commit exists."""
        sc = scenario3(self)
        install_checks(sc, "ran check-a\nran check-b\nexit 0\n")
        baseline = sc.head()

        answer = sc.run_step(["a.py", "notes.md"])

        self.assertEqual(answer.get("status"), "committed", answer)
        self.assertEqual(run_count(sc), 1, "the checks must run exactly once")
        line = run_lines(sc)[0]
        self.assertIn(f"head={baseline}", line, "the checks ran after a commit already existed")
        self.assertIn("staged=a.py notes.md", line, "the checks did not run over exactly the named files")
        self.assertNotEqual(sc.head(), baseline)
        self.assertEqual(sc.head_files(), ["a.py", "notes.md"])
        self.assertIn("autofixed", answer, "the answer contract carries autofixed on every outcome")
        self.assertEqual(answer["autofixed"], [], "nothing was fixed, so autofixed must be the empty list")

    def test_fixing_check_rewrite_is_taken_in_and_checks_run_exactly_once_more(self):
        # covers: BO-4500a-3
        # angle: criterion
        """A formatter rewrites a.py on run 1; run 2 passes; the commit holds the rewrite."""
        sc = scenario3(self)
        install_checks(sc, _FORMATTER)

        answer = sc.run_step(["a.py", "notes.md"])

        self.assertEqual(answer.get("status"), "committed", answer)
        self.assertEqual(run_count(sc), 2, "a fixer's rewrite earns exactly one more run here")
        self.assertEqual(sc.committed_text("a.py"), "formatted\n")
        self.assertEqual(sc.committed_text("notes.md"), "notes changed\n")
        fixed = as_list(answer.get("autofixed"))
        self.assertEqual(len(fixed), 1, answer)
        self.assertEqual(fixed[0].get("hook_name"), "format-py", answer)
        self.assertEqual(sorted(fixed[0].get("files", [])), ["a.py"], answer)

    def test_judging_failure_gets_no_second_run_and_answers_hook_failed(self):
        # covers: BO-4500a-3
        # angle: discrimination
        """A judging check that fails notes.md once (and would pass on a re-run) is not retried.

        Wrong versions caught: retrying the checks after a judging failure (the flaky
        judge passes run 2 and a commit appears); the step fixing notes.md itself.
        """
        sc = scenario3(self)
        install_checks(
            sc,
            'if [ "$n" = "1" ]; then\n'
            "  ran judge-notes\n"
            "  report judge-notes Failed\n"
            "  echo '- hook id: judge-notes'\n"
            "  echo\n"
            "  echo 'notes.md: needs a human decision'\n"
            "  exit 1\n"
            "fi\n"
            "exit 0\n",
        )
        baseline_commits = sc.commit_count()
        a_before, notes_before = sc.read("a.py"), sc.read("notes.md")

        answer = sc.run_step(["a.py", "notes.md"])

        self.assertEqual(answer.get("status"), "hook_failed", answer)
        self.assertEqual(answer.get("hook_name"), "judge-notes", answer)
        self.assertEqual(answer.get("failing_files"), ["notes.md"], answer)
        self.assertEqual(answer.get("reason_code"), "check_failed", answer)
        self.assertEqual(run_count(sc), 1, "a judging failure must not be re-run")
        self.assertEqual(sc.commit_count(), baseline_commits, "a commit was recorded")
        self.assertEqual(sc.staged_names(), [], "the call left files staged")
        self.assertEqual((sc.read("a.py"), sc.read("notes.md")), (a_before, notes_before))
        self.assertFalse(as_list(answer.get("autofixed")), "the step must not autofix a judging failure")

    def test_working_tree_keeps_fixer_edits_after_hook_failed(self):
        # covers: BO-4500a-3
        # angle: boundary
        """Fixer rewrote a.py on run 1, a judging check then failed notes.md on run 2."""
        sc = scenario3(self)
        install_checks(
            sc,
            'if [ "$n" = "1" ]; then\n'
            "  ran format-py\n"
            "  echo 'formatted' > a.py\n"
            "  report format-py Failed\n"
            "  echo '- files were modified by this hook'\n"
            "  exit 1\n"
            "fi\n"
            "ran judge-notes\n"
            "report judge-notes Failed\n"
            "echo '- hook id: judge-notes'\n"
            "echo\n"
            "echo 'notes.md: needs a human decision'\n"
            "exit 1\n",
        )
        baseline_commits = sc.commit_count()
        notes_before = sc.read("notes.md")

        answer = sc.run_step(["a.py", "notes.md"])

        self.assertEqual(answer.get("status"), "hook_failed", answer)
        self.assertEqual(answer.get("hook_name"), "judge-notes", answer)
        self.assertEqual(answer.get("failing_files"), ["notes.md"], answer)
        self.assertEqual(run_count(sc), 2)
        self.assertEqual(sc.read("a.py"), b"formatted\n", "the fixer's edit was lost")
        self.assertEqual(sc.read("notes.md"), notes_before, "notes.md changed")
        self.assertEqual(sc.commit_count(), baseline_commits)
        self.assertEqual(sc.staged_names(), [], "the call left files staged")


if __name__ == "__main__":
    unittest.main()
