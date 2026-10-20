"""
MODULE: unit_tests/build_orchestration/test_bo4500a_4_v_step_failures.py
GOAL: BO-4500a-4-v -- when the shared commit step (templates/scripts/commit_changes.py)
      itself cannot finish, the answer is refused with a step_ reason_code (never a
      policy_ code, never committed, never nothing_to_commit, never hook_failed).

Every test runs the REAL script as a subprocess against a REAL scratch git
repository and reads the outcome back from git. Nothing is mocked.

To go green the coder must make the step:
  * answer refused + step_index_locked, quoting git's own error text, when the
    workspace's index (.git/index.lock) is held by another process -- recording no
    commit and leaving the lock file it did not create alone;
  * answer refused + step_vcs_error, quoting git's error, when recording the commit
    fails AFTER every check passed (here: a reference-transaction hook declines the
    branch-ref update, so a commit object is written but the ref never moves) -- not
    hook_failed, not committed, not nothing_to_commit.
"""

from __future__ import annotations

import json
import unittest

from unit_tests.build_orchestration._bo4500a4_support import (
    CONFIG_ENV,
    StepScenario,
    install_checks,
    load_vocabulary,
    scenario3,
)

_PASSING_CHECKS = "ran passing-check\nexit 0\n"
_DECLINE_REF_UPDATE = (
    "#!/bin/sh\n"
    "cat >/dev/null\n"
    'if [ "$1" = "prepared" ]; then echo "fixture: ref update declined" >&2; exit 1; fi\n'
    "exit 0\n"
)


def _hold_index(sc: StepScenario) -> None:
    """Another version-control process holds the workspace index."""
    (sc.repo / ".git" / "index.lock").write_text("", encoding="utf-8")


def _break_recording(sc: StepScenario) -> None:
    """Checks pass, then recording the commit (the ref update) fails."""
    install_checks(sc, _PASSING_CHECKS)
    hook = sc.repo / ".git" / "hooks" / "reference-transaction"
    hook.write_text(_DECLINE_REF_UPDATE, encoding="utf-8")
    hook.chmod(0o755)


def _run(sc: StepScenario, paths: list[str]):
    proc = sc.run_raw(["--message-file", str(sc.message_file), *paths])
    try:
        answer = json.loads(proc.stdout)
    except json.JSONDecodeError:
        sc.case.fail(f"stdout was not exactly one JSON object: {proc.stdout!r} stderr={proc.stderr[-300:]!r}")
    return proc, answer


class TestIndexLockedIsAStepFailure(unittest.TestCase):
    def test_held_index_lock_is_refused_with_step_index_locked(self):
        # covers: BO-4500a-4-v
        # angle: criterion
        """Held .git/index.lock: refused + step_index_locked, git's text quoted, nothing recorded.

        Control row: the identical scenario without the lock commits normally, so the
        refusal is caused by the lock and by nothing else.
        """
        control = scenario3(self)
        install_checks(control, _PASSING_CHECKS)
        _, control_answer = _run(control, ["a.py"])
        self.assertEqual(control_answer["status"], "committed", control_answer)

        sc = scenario3(self)
        install_checks(sc, _PASSING_CHECKS)
        before = sc.head()
        _hold_index(sc)
        proc, answer = _run(sc, ["a.py"])
        self.assertEqual(answer["status"], "refused", answer)
        self.assertEqual(answer["reason_code"], "step_index_locked", answer)
        self.assertIsNone(answer["sha"])
        self.assertEqual(answer["paths"], [])
        self.assertIn("index.lock", answer["reason"], "reason must quote git's own error text")
        self.assertIn("File exists", answer["reason"])
        self.assertNotEqual(proc.returncode, 0, "a refused call must exit non-zero")
        self.assertEqual(sc.head(), before, "no commit may be recorded")
        self.assertEqual(sc.commit_count(), 1, "only the baseline commit may exist")
        self.assertEqual(sc.read("a.py"), b"a changed\n", "a.py working tree must be unchanged")
        self.assertTrue((sc.repo / ".git" / "index.lock").exists(), "a lock the step did not create must stay")


class TestRecordingFailureIsAStepFailure(unittest.TestCase):
    def test_error_while_recording_is_a_step_failure_not_success(self):
        # covers: BO-4500a-4-v
        # angle: discrimination
        """Recording fails after the checks pass: refused + step_vcs_error, branch ref unmoved.

        Wrong versions caught: reporting nothing_to_commit or committed when the commit
        command fails; coding the runtime failure with a policy_ code; and mapping any
        failed `git commit` to hook_failed although every check passed.
        """
        sc = scenario3(self)
        _break_recording(sc)
        before = sc.head()
        count = sc.commit_count()
        proc, answer = _run(sc, ["a.py"])
        self.assertEqual(answer["status"], "refused", answer)
        self.assertEqual(answer["reason_code"], "step_vcs_error", answer)
        self.assertFalse(str(answer["reason_code"]).startswith("policy_"))
        self.assertIsNone(answer["sha"])
        self.assertIsNone(answer["hook_name"])
        self.assertEqual(answer["failing_files"], [])
        self.assertTrue(answer["reason"], "a refused answer carries a reason")
        self.assertIn("ref update declined", answer["reason"], "reason must quote the error text")
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(sc.head(), before, "the branch ref must not move")
        self.assertEqual(sc.commit_count(), count, "no partial commit may be reachable from the branch")
        self.assertEqual(sc.read("a.py"), b"a changed\n", "a.py working tree must be unchanged")


class TestStepAndPolicyRefusalsAreDistinguishable(unittest.TestCase):
    def test_step_and_policy_refusals_are_distinguishable_by_code_alone(self):
        # covers: BO-4500a-4-v
        # angle: seam
        """Every refused fixture's code is a member of exactly the family its cause belongs to.

        Membership is checked against the published enumeration in config/commit_step.json,
        never a hand-typed list, and the families must be disjoint.
        """
        vocab = load_vocabulary(self)
        policy = set(vocab["reason_codes"]["policy"])
        step = set(vocab["reason_codes"]["step"])
        self.assertFalse(policy & step, "families must be disjoint")

        disallowed: list[dict] = []
        sc = scenario3(self)
        _, answer = _run(sc, [])  # no explicit paths
        disallowed.append(answer)
        sc = scenario3(self)
        sc.git("checkout", "-q", "-b", "main")
        _, answer = _run(sc, ["a.py"])  # protected branch
        disallowed.append(answer)
        sc = scenario3(self)
        sc.message_file.unlink()
        _, answer = _run(sc, ["a.py"])  # message file missing
        disallowed.append(answer)

        failed: list[dict] = []
        sc = scenario3(self)
        _hold_index(sc)
        _, answer = _run(sc, ["a.py"])
        failed.append(answer)
        sc = scenario3(self)
        _break_recording(sc)
        _, answer = _run(sc, ["a.py"])
        failed.append(answer)
        sc = scenario3(self)
        sc.env[CONFIG_ENV] = str(sc.scratch / "does-not-exist.json")
        _, answer = _run(sc, ["a.py"])
        failed.append(answer)

        for answer in disallowed:
            self.assertEqual(answer["status"], "refused", answer)
            self.assertIn(answer["reason_code"], policy, answer)
            self.assertNotIn(answer["reason_code"], step, answer)
        for answer in failed:
            self.assertEqual(answer["status"], "refused", answer)
            self.assertIn(answer["reason_code"], step, answer)
            self.assertNotIn(answer["reason_code"], policy, answer)
        self.assertEqual(
            sorted(a["reason_code"] for a in failed),
            ["step_config_unreadable", "step_index_locked", "step_vcs_error"],
        )


if __name__ == "__main__":
    unittest.main()
