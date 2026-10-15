"""
MODULE: unit_tests/build_orchestration/test_bo4500a_1_explicit_path_staging.py
GOAL: RED tests for BO-4500a-1 -- the shared commit step commits exactly the
      files the caller names and never sweeps up the rest of the workspace.

Production target (does not exist yet; the python-coder builds it):
    templates/scripts/commit_changes.py
CLI: python commit_changes.py --message-file <FILE> [PATH ...]   (cwd = workspace)
Answer: one JSON object on stdout (see _commit_step_support.py).

Every test runs the real script as a subprocess against a scratch git repo and
reads the outcome back from git (commit file list, index, working tree).
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _commit_step_support import StepScenario  # noqa: E402

BASELINE = {
    "a.py": "print('a')\n",
    "b.py": "print('b')\n",
    "docs/c.md": "# c\n",
    "docs/INDEX.md": "# index\n",
    "tickets/t.md": "# t\n",
}
DIRTY = {
    "a.py": "print('a changed')\n",
    "b.py": "print('b changed')\n",
    "docs/c.md": "# c changed\n",
    "docs/INDEX.md": "# index changed\n",
    "tickets/t.md": "# t changed\n",
}
NAMED = ["a.py", "docs/c.md"]
UNNAMED = ["b.py", "docs/INDEX.md", "tickets/t.md"]


def _dirty_scenario(case: unittest.TestCase) -> StepScenario:
    sc = StepScenario(case)
    sc.seed_and_commit(BASELINE)
    for rel, text in DIRTY.items():
        sc.write(rel, text)
    return sc


class TestExplicitPathStaging(unittest.TestCase):
    def test_commit_contains_exactly_the_named_files(self):
        # covers: BO-4500a-1
        # angle: criterion
        """AC BO-4500a-1: the new commit holds exactly a.py and docs/c.md."""
        sc = _dirty_scenario(self)
        before = sc.head()
        answer = sc.run_step(NAMED)
        self.assertEqual(answer.get("status"), "committed", answer)
        self.assertNotEqual(sc.head(), before, "no new commit was recorded")
        self.assertEqual(sc.head_files(), sorted(NAMED))
        self.assertEqual(sc.commit_count(), 2, "exactly one new commit")

    def test_unnamed_changes_stay_modified_unstaged_and_byte_identical(self):
        # covers: BO-4500a-1
        # angle: criterion
        """AC BO-4500a-1: b.py, docs/INDEX.md, tickets/t.md stay modified, unstaged, unchanged."""
        sc = _dirty_scenario(self)
        before_bytes = {rel: sc.read(rel) for rel in UNNAMED}
        answer = sc.run_step(NAMED)
        self.assertEqual(answer.get("status"), "committed", answer)
        status = sc.porcelain()
        for rel in UNNAMED:
            self.assertEqual(status.get(rel), " M", f"{rel} must be modified and NOT staged")
            self.assertEqual(sc.read(rel), before_bytes[rel], f"{rel} content changed")
        self.assertEqual(sc.staged_names(), [], "nothing may be left staged by the call")
        # exact count: only the three unnamed files remain dirty
        self.assertEqual(sorted(status), sorted(UNNAMED))

    def test_committed_answer_lists_exactly_the_named_paths_and_the_new_sha(self):
        # covers: BO-4500a-1
        # angle: criterion
        """AC BO-4500a-1: committed answer carries the new HEAD sha and paths == named."""
        sc = _dirty_scenario(self)
        answer = sc.run_step(NAMED)
        self.assertEqual(answer.get("status"), "committed", answer)
        self.assertEqual(answer.get("sha"), sc.head())
        self.assertRegex(answer.get("sha") or "", re.compile(r"^[0-9a-f]{40}$"))
        self.assertEqual(sorted(answer.get("paths") or []), sorted(NAMED))
        self.assertEqual(len(answer["paths"]), 2)

    def test_no_paths_or_all_request_is_refused_and_stages_nothing(self):
        # covers: BO-4500a-1
        # angle: failure
        """AC BO-4500a-1: no list / 'all changed' / 'all tracked' is refused, nothing staged."""
        requests = {
            "no_paths": [],
            "all_changed": ["--all-changed"],
            "all_tracked": ["--all-tracked"],
            "dash_A": ["-A"],
            "all_flag": ["--all"],
        }
        for label, extra in requests.items():
            with self.subTest(request=label):
                sc = _dirty_scenario(self)
                head = sc.head()
                index = sc.index_entries()
                answer = sc.run_step([], extra=extra)
                self.assertEqual(answer.get("status"), "refused", answer)
                if label == "no_paths":
                    self.assertEqual(answer.get("reason_code"), "policy_no_explicit_paths")
                    self.assertIn("explicit", (answer.get("reason") or "").lower())
                else:
                    self.assertIn(
                        answer.get("reason_code"),
                        {"policy_no_explicit_paths", "policy_unknown_option"},
                    )
                self.assertIsNone(answer.get("sha"))
                self.assertEqual(sc.head(), head, "a commit was recorded")
                self.assertEqual(sc.index_entries(), index, "the call changed the index")
                self.assertEqual(sc.staged_names(), [])

    def test_step_offers_no_mode_that_stages_every_changed_or_tracked_file(self):
        # covers: BO-4500a-1
        # angle: discrimination
        """AC BO-4500a-1: no option sweeps in an unnamed file; dir/glob entries are refused.

        Wrong versions this must catch: a default of `git add -A` when no path is
        given; an --all flag; a directory entry expanded to every file under it.
        """
        control = _dirty_scenario(self)
        usage = control.run_raw(["--help"])
        self.assertEqual(usage.returncode, 0, usage.stderr)
        self.assertIn("--message-file", usage.stdout, "usage text must list --message-file")
        options = sorted(set(re.findall(r"--[A-Za-z][A-Za-z0-9-]*", usage.stdout)))
        exercised = [o for o in options if o not in {"--help", "--message-file"}]

        # Control row: an honest call naming a.py commits exactly a.py (so the
        # sweep assertions below do not pass merely because the step is inert).
        answer = control.run_step(["a.py"])
        self.assertEqual(answer.get("status"), "committed", answer)
        self.assertEqual(control.head_files(), ["a.py"])

        # Every option the usage text lists, exercised alone and next to a.py.
        for option in exercised:
            for named in ([], ["a.py"]):
                with self.subTest(option=option, named=named):
                    sc = _dirty_scenario(self)
                    sc.run_raw(["--message-file", str(sc.message_file), option, *named])
                    committed = set(sc.head_files()) if sc.commit_count() > 1 else set()
                    self.assertLessEqual(committed, set(named), f"{option} swept in files")
                    for rel in UNNAMED:
                        self.assertEqual(sc.porcelain().get(rel), " M", f"{rel} was staged")

        # A directory entry and a glob are refused, never expanded.
        for entry in ("docs", "docs/", "docs/*.md", "."):
            with self.subTest(entry=entry):
                sc = _dirty_scenario(self)
                head = sc.head()
                reply = sc.run_step([entry])
                self.assertEqual(reply.get("status"), "refused", reply)
                self.assertEqual(reply.get("reason_code"), "policy_path_not_a_file", reply)
                self.assertEqual(sc.head(), head)
                self.assertEqual(sc.staged_names(), [])

    def test_second_identical_call_answers_nothing_to_commit(self):
        # covers: BO-4500a-1
        # angle: boundary
        """AC BO-4500a-1: repeating the same call answers nothing_to_commit, no second commit."""
        sc = _dirty_scenario(self)
        first = sc.run_step(NAMED)
        self.assertEqual(first.get("status"), "committed", first)
        head = sc.head()
        count = sc.commit_count()
        second = sc.run_step(NAMED)
        self.assertEqual(second.get("status"), "nothing_to_commit", second)
        self.assertIsNone(second.get("sha"))
        self.assertEqual(second.get("paths"), [])
        self.assertEqual(sc.head(), head)
        self.assertEqual(sc.commit_count(), count)


if __name__ == "__main__":
    unittest.main()
