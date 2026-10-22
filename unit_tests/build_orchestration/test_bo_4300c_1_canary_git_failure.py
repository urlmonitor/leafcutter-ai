"""
MODULE: unit_tests/build_orchestration/test_bo_4300c_1_canary_git_failure.py
AC: BO-4300c-1-ii -- when git cannot be run or fails, the stage canary fails CLOSED (non-zero exit,
named failure on stderr) and never prints PRECOMMIT_CANARY_REJECTED, because the readiness probe
counts only that marker as proof a stage fired.

DECISION HISTORY
====================================================================
- 2026-10-09 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05]: Created for the
  check-exception-handling autofix (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05).
====================================================================
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CANARY = Path(__file__).resolve().parents[2] / "templates" / "scripts" / "commit_guardian" / "precommit_canary.py"
MARK = "PRECOMMIT_CANARY_REJECTED"


def _run(stage: str, cwd: Path, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(CANARY), "--stage", stage], cwd=str(cwd),
                          env=env, capture_output=True, text=True, check=False)


class TestGitFailureFailsClosed(unittest.TestCase):
    def _assert_closed(self, ran: subprocess.CompletedProcess) -> None:
        self.assertNotEqual(ran.returncode, 0)
        self.assertNotIn(MARK, ran.stdout + ran.stderr)
        self.assertIn("git failed", ran.stderr)

    def test_git_missing_from_path(self):
        # covers: BO-4300c-1-ii
        # angle: error
        with tempfile.TemporaryDirectory() as td:
            env = {k: v for k, v in os.environ.items() if k.upper() != "PATH"}
            env["PATH"] = td
            self._assert_closed(_run("post-merge", Path(td), env))

    def test_subprocess_error_from_git_fails_closed(self):
        # covers: BO-4300c-1-ii
        # angle: error
        import importlib.util
        from contextlib import redirect_stderr, redirect_stdout
        from io import StringIO
        from unittest import mock

        spec = importlib.util.spec_from_file_location("precommit_canary_under_test", CANARY)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        out, err = StringIO(), StringIO()
        with mock.patch.object(mod, "declared_spec", return_value={"path": "x"}),                 mock.patch.object(mod.subprocess, "run", side_effect=subprocess.TimeoutExpired("git", 1)),                 redirect_stdout(out), redirect_stderr(err):
            code = mod.run_stage("pre-commit", [])
        self.assertNotEqual(code, 0)
        self.assertNotIn(MARK, out.getvalue() + err.getvalue())
        self.assertIn("git failed", err.getvalue())


if __name__ == "__main__":
    unittest.main()
