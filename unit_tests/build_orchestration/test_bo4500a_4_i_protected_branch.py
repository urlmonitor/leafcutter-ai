"""
MODULE: unit_tests/build_orchestration/test_bo4500a_4_i_protected_branch.py
GOAL: BO-4500a-4-i -- the shared commit step (templates/scripts/commit_changes.py)
      refuses to commit onto main, master, the origin-reported default branch, or
      no branch at all, and does so BEFORE any staging or check.

Every test runs the REAL script as a subprocess against a REAL scratch git
repository, with a real pre-commit hook that appends to a log file so "no check
ran" is observed, not assumed. Nothing is mocked.

To go green the coder must make commit_changes.py read the current branch first
and answer refused with reason_code policy_protected_branch (reason naming the
branch) or policy_detached_head (reason stating the workspace is on no branch).
"""

from __future__ import annotations

import unittest

from unit_tests.build_orchestration._commit_step_support import StepScenario

_HOOK_LOG_BODY = 'echo ran >> "$(git rev-parse --git-dir)/check_log"\nexit 0\n'


def _prepare(case: unittest.TestCase, branch: str | None) -> StepScenario:
    """Scratch repo on *branch* (None = detached) with a logging hook and a.py modified."""
    sc = StepScenario(case, branch="trunk-seed")
    sc.seed_and_commit({"a.py": "x = 1\n"})
    if branch is None:
        sc.git("checkout", "-q", "--detach")
    elif branch != "trunk-seed":
        sc.git("checkout", "-q", "-b", branch)
    sc.install_hook(_HOOK_LOG_BODY)
    sc.write("a.py", "x = 2\n")
    return sc


def _check_runs(sc: StepScenario) -> int:
    log = sc.repo / ".git" / "check_log"
    return len(log.read_text().splitlines()) if log.exists() else 0


def _assert_refused_untouched(case: unittest.TestCase, sc: StepScenario, answer: dict, before: str) -> None:
    case.assertEqual(answer["status"], "refused", answer)
    case.assertEqual(sc.head(), before, "a refused call must record no commit")
    case.assertEqual(sc.staged_names(), [], "a refused call must not stage a.py")
    case.assertEqual(_check_runs(sc), 0, "a refused call must run no check")
    case.assertEqual(sc.read("a.py"), b"x = 2\n", "working tree must be untouched")


class TestProtectedBranchRefusal(unittest.TestCase):
    def test_main_and_master_are_refused_before_any_check_runs(self):
        # covers: BO-4500a-4-i
        # angle: criterion
        """On main and master: refused, policy_protected_branch naming the branch, nothing changed."""
        for branch in ("main", "master"):
            with self.subTest(branch=branch):
                sc = _prepare(self, branch)
                before = sc.head()
                answer = sc.run_step(["a.py"])
                _assert_refused_untouched(self, sc, answer, before)
                self.assertEqual(answer["reason_code"], "policy_protected_branch", answer)
                self.assertIn(branch, answer["reason"])
                self.assertIsNone(answer["sha"])

    def test_origin_default_branch_trunk_is_refused(self):
        # covers: BO-4500a-4-i
        # angle: criterion
        """With origin's recorded default branch = trunk, a call on trunk is refused naming trunk."""
        sc = _prepare(self, "trunk")
        sc.git("update-ref", "refs/remotes/origin/trunk", "HEAD")
        sc.git("symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/trunk")
        before = sc.head()
        answer = sc.run_step(["a.py"])
        _assert_refused_untouched(self, sc, answer, before)
        self.assertEqual(answer["reason_code"], "policy_protected_branch", answer)
        self.assertIn("trunk", answer["reason"])

    def test_detached_checkout_is_refused(self):
        # covers: BO-4500a-4-i
        # angle: failure
        """A detached checkout answers refused with policy_detached_head and changes nothing."""
        sc = _prepare(self, None)
        before = sc.head()
        answer = sc.run_step(["a.py"])
        _assert_refused_untouched(self, sc, answer, before)
        self.assertEqual(answer["reason_code"], "policy_detached_head", answer)
        self.assertIn("no branch", answer["reason"].lower())

    def test_main_followup_is_allowed(self):
        # covers: BO-4500a-4-i
        # angle: discrimination
        """main-followup commits normally; the same run on main is refused (paired control row).

        Catches a prefix match that refuses every branch starting with main, and
        equally a version that never refuses at all.
        """
        control = _prepare(self, "main")
        control_before = control.head()
        refused = control.run_step(["a.py"])
        _assert_refused_untouched(self, control, refused, control_before)
        self.assertEqual(refused["reason_code"], "policy_protected_branch", refused)

        sc = _prepare(self, "main-followup")
        before = sc.head()
        answer = sc.run_step(["a.py"])
        self.assertEqual(answer["status"], "committed", answer)
        self.assertNotEqual(sc.head(), before)
        self.assertEqual(answer["sha"], sc.head())
        self.assertEqual(sc.head_files(), ["a.py"])
        self.assertEqual(_check_runs(sc), 1, "the checks must run exactly once on an allowed branch")


if __name__ == "__main__":
    unittest.main()
