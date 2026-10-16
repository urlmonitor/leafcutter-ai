"""
MODULE: unit_tests/build_orchestration/test_bo4500a_1_iv_path_validation.py
GOAL: RED tests for BO-4500a-1-iv -- a named file that is missing, outside the
      workspace or unchanged gets a precise answer, never a guess.

Production target: templates/scripts/commit_changes.py (does not exist yet).
Every test runs the real script on a scratch repo and asserts status, reason_code
and git state together.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _commit_step_support import StepScenario  # noqa: E402


def _scenario(case: unittest.TestCase) -> StepScenario:
    sc = StepScenario(case)
    sc.seed_and_commit({"a.py": "a\n", "b.py": "b\n", "gone.py": "gone\n"})
    sc.write("a.py", "a changed\n")
    return sc


class TestNamedPathValidation(unittest.TestCase):
    def test_path_outside_workspace_refuses_the_whole_call(self):
        # covers: BO-4500a-1-iv
        # angle: failure
        """AC BO-4500a-1-iv: a.py + ../other-repo/z.py -> refused, policy_path_outside_workspace."""
        sc = _scenario(self)
        other = sc.parent / "other-repo"
        other.mkdir()
        (other / "z.py").write_text("z\n", encoding="utf-8")
        head = sc.head()
        answer = sc.run_step(["a.py", "../other-repo/z.py"])
        self.assertEqual(answer.get("status"), "refused", answer)
        self.assertEqual(answer.get("reason_code"), "policy_path_outside_workspace")
        self.assertIn("../other-repo/z.py", answer.get("reason") or "")
        self.assertEqual(sc.head(), head, "a commit was recorded")
        self.assertEqual(sc.staged_names(), [], "a.py was left staged by the call")
        self.assertEqual(sc.porcelain().get("a.py"), " M")

    def test_never_existed_path_is_refused_not_nothing_to_commit(self):
        # covers: BO-4500a-1-iv
        # angle: discrimination
        """AC BO-4500a-1-iv: a.py + never-existed.py -> refused, policy_path_not_found.

        Wrong versions this must catch: skipping the missing path and committing
        a.py; answering nothing_to_commit for a misspelt path.
        """
        sc = _scenario(self)
        head = sc.head()
        answer = sc.run_step(["a.py", "never-existed.py"])
        self.assertEqual(answer.get("status"), "refused", answer)
        self.assertEqual(answer.get("reason_code"), "policy_path_not_found")
        self.assertIn("never-existed.py", answer.get("reason") or "")
        self.assertEqual(sc.head(), head, "a.py was committed despite the bad entry")
        self.assertEqual(sc.staged_names(), [])
        # control: the very same call without the bad entry does commit a.py
        control = sc.run_step(["a.py"])
        self.assertEqual(control.get("status"), "committed", control)
        self.assertEqual(sc.head_files(), ["a.py"])

    def test_unchanged_tracked_file_answers_nothing_to_commit(self):
        # covers: BO-4500a-1-iv
        # angle: boundary
        """AC BO-4500a-1-iv: only unchanged b.py -> nothing_to_commit, nothing_changed, paths [], sha null."""
        sc = _scenario(self)
        head = sc.head()
        answer = sc.run_step(["b.py"])
        self.assertEqual(answer.get("status"), "nothing_to_commit", answer)
        self.assertEqual(answer.get("reason_code"), "nothing_changed")
        self.assertEqual(answer.get("paths"), [])
        self.assertIsNone(answer.get("sha"))
        self.assertEqual(sc.head(), head)
        self.assertEqual(sc.porcelain().get("a.py"), " M", "unnamed a.py must stay dirty")

    def test_deleted_tracked_file_commits_as_a_deletion(self):
        # covers: BO-4500a-1-iv
        # angle: criterion
        """AC BO-4500a-1-iv: a tracked file deleted from disk commits as a deletion, in paths."""
        sc = _scenario(self)
        os.remove(sc.repo / "gone.py")
        answer = sc.run_step(["gone.py"])
        self.assertEqual(answer.get("status"), "committed", answer)
        self.assertEqual(answer.get("paths"), ["gone.py"])
        self.assertEqual(sc.head_name_status(), ["D\tgone.py"])
        self.assertEqual(sc.porcelain().get("a.py"), " M", "unnamed a.py must stay dirty")


if __name__ == "__main__":
    unittest.main()
