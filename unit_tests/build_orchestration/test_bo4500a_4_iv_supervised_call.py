"""
MODULE: unit_tests/build_orchestration/test_bo4500a_4_iv_supervised_call.py
GOAL: BO-4500a-4-iv -- a supervised call to the shared commit step names the run
      (or criterion) it commits for, and never waits for a person.

CONTRACT PINNED FOR THE CODER (none of it exists in the step yet):

  * CLI flags on templates/scripts/commit_changes.py:
        --supervised          explicit input, never inferred from the environment
        --run RUN_ID          free-text attribution, echoed in the answer's "run"
        --ac-id AC_ID         free-text attribution, echoed in the answer's "ac_id"
  * A supervised call naming neither is refused with
    reason_code policy_unattributed_supervised_call BEFORE anything is staged;
    the reason says a supervised call must name the run or the criterion.
  * In supervised mode the checks run with no terminal input attached; silence is
    never "waiting" (BO-4500a-4-vii). A commit still running after the wall-clock
    limit is ended, nothing is committed, and the answer is refused / step_timed_out.
  * The limit is config/commit_step.json key commit_time_limit_seconds
    (package default 1800), overridable through LEAFCUTTER_COMMIT_STEP_CONFIG.

Every test runs the REAL step as a subprocess against a REAL scratch git
repository and reads the result back from the answer and from git.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bo4500a3_support import PACKAGE_CONFIG, install_checks, run_count, scenario3  # noqa: E402
from _bo4500a4_support import write_config_copy  # noqa: E402
from _commit_step_support import STEP, StepScenario  # noqa: E402

RUN_ID = "plan-bo-4500-20261012"
AC_ID = "BO-4500a-1"
WAIT_LIMIT_S = 2
SLOW_S = 4
HANG_CHECK = (
    "i=0\n"
    'until read line; do\n'
    "  i=$((i+1))\n"
    '  [ "$i" -gt 30 ] && exit 0\n'
    "  sleep 1\n"
    "done\n"
    'echo got > "$S/got_input"\n'
    "exit 0\n"
)


def _answer(case: unittest.TestCase, proc: subprocess.CompletedProcess) -> dict:
    try:
        answer = json.loads(proc.stdout)
    except json.JSONDecodeError:
        case.fail(f"stdout was not exactly one JSON object: rc={proc.returncode} "
                  f"stdout={proc.stdout!r} stderr={proc.stderr[-400:]!r}")
    case.assertIsInstance(answer, dict)
    return answer


class TestSupervisedCall(unittest.TestCase):
    def _call(self, sc: StepScenario, *flags: str) -> dict:
        proc = sc.run_raw(["--message-file", str(sc.message_file), *flags, "a.py"])
        return _answer(self, proc)

    def test_supervised_call_naming_a_run_is_committed_and_echoes_the_run(self):
        # covers: BO-4500a-4-iv
        # angle: criterion
        """AC: supervised + run, no AC id -> committed, run echoed, ac_id null."""
        sc = scenario3(self)
        before = sc.commit_count()
        answer = self._call(sc, "--supervised", "--run", RUN_ID)
        self.assertEqual(answer["status"], "committed", answer)
        self.assertEqual(answer["run"], RUN_ID)
        self.assertIsNone(answer["ac_id"], "no AC id was named, so none may be echoed")
        self.assertEqual(sc.commit_count(), before + 1)
        self.assertEqual(answer["sha"], sc.head())

    def test_supervised_call_naming_an_ac_is_committed_and_echoes_the_ac(self):
        # covers: BO-4500a-4-iv
        # angle: criterion
        """AC: supervised + AC id, no run -> committed, ac_id echoed, run null."""
        sc = scenario3(self)
        before = sc.commit_count()
        answer = self._call(sc, "--supervised", "--ac-id", AC_ID)
        self.assertEqual(answer["status"], "committed", answer)
        self.assertEqual(answer["ac_id"], AC_ID)
        self.assertIsNone(answer["run"], "no run was named, so none may be echoed")
        self.assertEqual(sc.commit_count(), before + 1)
        self.assertEqual(answer["sha"], sc.head())

    def test_supervised_call_naming_neither_is_refused(self):
        # covers: BO-4500a-4-iv
        # angle: failure
        """AC: supervised with no run and no AC id -> refused, nothing staged or committed."""
        sc = scenario3(self)
        install_checks(sc, "ran\nexit 0\n")
        before = sc.commit_count()
        answer = self._call(sc, "--supervised")
        self.assertEqual(answer["status"], "refused", answer)
        self.assertEqual(answer["reason_code"], "policy_unattributed_supervised_call")
        reason = (answer["reason"] or "").lower()
        self.assertIn("supervised", reason)
        self.assertIn("run", reason)
        self.assertIn("criterion", reason)
        self.assertIsNone(answer["sha"])
        self.assertEqual(sc.commit_count(), before, "a refused call must record no commit")
        self.assertEqual(sc.staged_names(), [], "refusal happens before anything is staged")
        self.assertEqual(run_count(sc), 0, "the checks must not run for a refused call")

    def test_slow_silent_check_is_committed_not_reported_as_waiting(self):
        # covers: BO-4500a-4-iv
        # angle: discrimination
        """AC (amended by BO-4500a-4-vii): a check silent for a while is slow, not waiting.

        must_catch: a silence timer that ends a correct commit. The check says nothing
        for longer than the old two-second limit, then passes; the call commits.
        """
        sc = scenario3(self)
        install_checks(sc, f"sleep {SLOW_S}\nexit 0\n")
        write_config_copy(sc, commit_time_limit_seconds=30)
        before = sc.commit_count()
        answer = self._call(sc, "--supervised", "--run", RUN_ID)
        self.assertEqual(answer["status"], "committed", answer)
        self.assertEqual(sc.commit_count(), before + 1)

    def test_hung_commit_gets_no_input_and_is_ended_as_step_timed_out(self):
        # covers: BO-4500a-4-iv
        # angle: discrimination
        """AC (amended by BO-4500a-4-vii): a hung commit is ended at the wall-clock limit.

        must_catch: inheriting the caller's terminal so the check blocks forever.
        The caller's stdin is a pipe that stays OPEN and silent for the whole call,
        so a step that lets the check inherit it never sees the check end.
        """
        sc = scenario3(self)
        install_checks(sc, HANG_CHECK)
        write_config_copy(sc, commit_time_limit_seconds=WAIT_LIMIT_S)
        before = sc.commit_count()
        read_fd, write_fd = os.pipe()
        self.addCleanup(os.close, write_fd)
        self.addCleanup(os.close, read_fd)
        started = time.monotonic()
        try:
            proc = subprocess.run(
                [sys.executable, str(STEP), "--message-file", str(sc.message_file),
                 "--supervised", "--run", RUN_ID, "a.py"],
                cwd=sc.repo, env=sc.env, stdin=read_fd, capture_output=True, text=True,
                timeout=40, check=False,
            )
        except subprocess.TimeoutExpired:
            self.fail("the step blocked on a check waiting for input; the wait was never ended")
        elapsed = time.monotonic() - started
        answer = _answer(self, proc)
        self.assertEqual(answer["status"], "refused", answer)
        self.assertEqual(answer["reason_code"], "step_timed_out")
        self.assertGreaterEqual(elapsed, WAIT_LIMIT_S - 0.5, "ended before the limit elapsed")
        self.assertLess(elapsed, 25, "the wait must end near the configured limit")
        self.assertEqual(sc.commit_count(), before, "no commit may be recorded")
        self.assertFalse((sc.scratch / "got_input").exists(), "the step must not supply input")

    def test_time_limit_is_config_with_a_default_of_1800_seconds(self):
        # covers: BO-4500a-4-iv
        # angle: criterion
        """IT req: the limit is read from project config, default 1800 s, not hard-coded."""
        config = json.loads(PACKAGE_CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(config.get("commit_time_limit_seconds"), 1800)
        self.assertNotIn("input_wait_limit_seconds", config)

    def test_unsupervised_call_without_attribution_commits(self):
        # covers: BO-4500a-4-iv
        # angle: boundary
        """AC: an unsupervised call naming neither run nor AC commits normally.

        Control pair: the identical call with --supervised is refused, so a step
        that refuses every unattributed call cannot pass.
        """
        sc = scenario3(self)
        before = sc.commit_count()
        answer = self._call(sc)
        self.assertEqual(answer["status"], "committed", answer)
        self.assertIsNone(answer["run"])
        self.assertIsNone(answer["ac_id"])
        self.assertEqual(sc.commit_count(), before + 1)
        twin = scenario3(self)
        refused = self._call(twin, "--supervised")
        self.assertEqual(refused["reason_code"], "policy_unattributed_supervised_call", refused)


if __name__ == "__main__":
    unittest.main()
