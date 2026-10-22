"""
MODULE: unit_tests/build_orchestration/test_bo4500a_4_vii_slow_check_not_awaiting_input.py
GOAL: BO-4500a-4-vii -- a slow (silent) pre-commit check is not "waiting for input".
      The supervised commit's stdin is already /dev/null, so silence only means
      slow. The silence timer is replaced by an overall wall-clock backstop
      (reported under its own step_ code, never check_awaited_input), and the
      commit's environment closes the remaining interactive paths.

Every test runs the REAL step as a subprocess against a REAL scratch git
repository and reads the result back from the answer and from git.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bo4500a3_support import PACKAGE_CONFIG, install_checks, scenario3  # noqa: E402
from _bo4500a4_support import write_config_copy  # noqa: E402
from _commit_step_support import STEP  # noqa: E402

RUN_ID = "quick-fix-bo-4500a-4-vii"
SILENCE_S = 2
SLOW_S = 5

# A check that says nothing at all for SLOW_S seconds, then succeeds. pre-commit
# buffers a hook's output until it finishes, so a slow hook looks exactly like this.
SLOW_SILENT_CHECK = f"sleep {SLOW_S}\nexit 0\n"
QUICK_CHECK = "exit 0\n"
HUNG_CHECK = "sleep 25\nexit 0\n"
ENV_PROBE_CHECK = (
    'printf "%s" "$GIT_TERMINAL_PROMPT" > "$S/prompt_env"\n'
    'printf "%s" "$GIT_EDITOR" > "$S/editor_env"\n'
    "exit 0\n"
)


def _answer(case: unittest.TestCase, proc: subprocess.CompletedProcess) -> dict:
    try:
        answer = json.loads(proc.stdout)
    except json.JSONDecodeError:
        case.fail(f"stdout was not one JSON object: rc={proc.returncode} "
                  f"stdout={proc.stdout!r} stderr={proc.stderr[-400:]!r}")
    return answer


def _silence_limited_config(sc) -> None:
    """Shrink the OLD silence limit (if the package still has one) below SLOW_S."""
    config = json.loads(PACKAGE_CONFIG.read_text(encoding="utf-8"))
    if "input_wait_limit_seconds" in config:
        write_config_copy(sc, input_wait_limit_seconds=SILENCE_S)


class TestSlowCheckIsNotAwaitingInput(unittest.TestCase):
    def _supervised(self, sc, timeout: int = 60) -> dict:
        proc = subprocess.run(
            [sys.executable, str(STEP),
             "--message-file", str(sc.message_file), "--supervised", "--run", RUN_ID, "a.py"],
            cwd=sc.repo, env=sc.env, stdin=subprocess.DEVNULL, capture_output=True,
            text=True, timeout=timeout, check=False,
        )
        return _answer(self, proc)

    def test_ac1_slow_silent_check_is_committed_not_refused(self):
        # covers: BO-4500a-4-vii
        # angle: discrimination
        """AC: a check silent for longer than the old wait limit still commits.

        must_catch: a silence timer that kills a correct commit as 'awaiting input'.
        Control: the same call with a quick check commits, so the refusal below
        cannot come from the fixture.
        """
        control = scenario3(self)
        install_checks(control, QUICK_CHECK)
        _silence_limited_config(control)
        self.assertEqual(self._supervised(control)["status"], "committed")

        sc = scenario3(self)
        install_checks(sc, SLOW_SILENT_CHECK)
        _silence_limited_config(sc)
        before = sc.commit_count()
        answer = self._supervised(sc)
        self.assertNotEqual(answer.get("reason_code"), "check_awaited_input", answer)
        self.assertEqual(answer["status"], "committed", answer)
        self.assertEqual(sc.commit_count(), before + 1)
        self.assertEqual(answer["sha"], sc.head())

    def test_ac2_hung_commit_is_ended_by_wall_clock_backstop_not_awaited_input(self):
        # covers: BO-4500a-4-vii
        # angle: failure
        """AC: a commit still running past the configured time limit is ended.

        Reported under a step_ reason code, never check_awaited_input; nothing committed.
        """
        sc = scenario3(self)
        install_checks(sc, HUNG_CHECK)
        write_config_copy(sc, commit_time_limit_seconds=SILENCE_S)
        before = sc.commit_count()
        started = time.monotonic()
        answer = self._supervised(sc, timeout=50)
        elapsed = time.monotonic() - started
        self.assertNotEqual(answer["status"], "committed", answer)
        self.assertNotEqual(answer["reason_code"], "check_awaited_input", answer)
        self.assertTrue(str(answer["reason_code"]).startswith("step_"), answer)
        self.assertLess(elapsed, 20, "the backstop must end the commit near the configured limit")
        self.assertEqual(sc.commit_count(), before, "no commit may be recorded")

    def test_ac3_commit_environment_closes_interactive_paths(self):
        # covers: BO-4500a-4-vii
        # angle: criterion
        """AC: checks see GIT_TERMINAL_PROMPT=0 and GIT_EDITOR=':' in a supervised commit."""
        sc = scenario3(self)
        install_checks(sc, ENV_PROBE_CHECK)
        answer = self._supervised(sc)
        self.assertEqual(answer["status"], "committed", answer)
        self.assertEqual((sc.scratch / "prompt_env").read_text(), "0")
        self.assertEqual((sc.scratch / "editor_env").read_text(), ":")


if __name__ == "__main__":
    unittest.main()
