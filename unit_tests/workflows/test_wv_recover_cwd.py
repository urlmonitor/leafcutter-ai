"""
MODULE: unit_tests/workflows/test_wv_recover_cwd.py
GOAL: Prove the wrong-version ``recover`` step no longer depends on the directory its executor happens to run in.
BUSINESS CONTEXT: ``wrong_version_runner.py recover`` used to find the repository from the process cwd. A drive
    started from a session outside the workspace ran it in a directory that is not a repository, got
    ``ok: false`` and halted before dispatching any ticket. The step now names the worktree with ``--test-root``
    and every route (build-feature, build-ticket, build-epic, fast lane) passes it.
ARCHITECTURE: Part 1 runs the REAL runner script as a subprocess from a non-git cwd. Part 2 drives each route
    TEMPLATE under the E2 workflow harness and reads the command it dispatches to ``command-step-runner``.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

import workflows._tq500g1v_fixtures as lane  # noqa: E402
import workflows._tq500g1vi_fixtures as vi  # noqa: E402
import workflows._tq500g1viii_fixtures as epic  # noqa: E402

RUNNER = lane.REPO_ROOT / "scripts" / "build_orchestration" / "wrong_version_runner.py"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, timeout=30)


def _recover(cwd: Path, *extra: str) -> tuple[int, dict]:
    proc = subprocess.run([sys.executable, str(RUNNER), "recover", *extra], cwd=cwd, capture_output=True,
                          text=True, timeout=30, check=False)
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    return proc.returncode, json.loads(lines[-1]) if lines else {"stderr": proc.stderr}


class RecoverRunsFromAnyCwd(unittest.TestCase):
    """The real ``recover`` subcommand, run as a process from a directory that is not a repository."""

    def test_recover_with_test_root_succeeds_from_non_git_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, elsewhere = Path(tmp) / "repo", Path(tmp) / "elsewhere"
            repo.mkdir()
            elsewhere.mkdir()
            _git(repo, "init", "-q")
            code, payload = _recover(elsewhere, "--test-root", str(repo))
        self.assertEqual(code, 0, payload)
        self.assertIs(payload["ok"], True, payload)
        self.assertEqual(payload["restored"], [])

    def test_recover_with_missing_test_root_still_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, payload = _recover(Path(tmp), "--test-root", str(Path(tmp) / "no-such-repo"))
        self.assertEqual(code, 1, payload)
        self.assertIs(payload["ok"], False, payload)

    def test_recover_with_test_root_that_is_not_a_repository_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, payload = _recover(Path(tmp), "--test-root", tmp)
        self.assertEqual(code, 1, payload)
        self.assertIs(payload["ok"], False, payload)


class RoutesPassTheWorktreeToRecover(unittest.TestCase):
    """Each route template's dispatched recover command names the worktree, so the executor cwd is moot."""

    def _assert_names(self, command: str, root: str, where: str) -> None:
        self.assertIn(f'recover --test-root "{root}"', command, f"{where}: {command}")

    def test_build_feature_and_build_ticket(self):
        for route in vi.ROUTES:
            with self.subTest(route=route.script_name):
                result = vi.run_route(route)
                recover = vi.calls(result, route.recover)
                self.assertEqual(len(recover), 1, vi.labels_of(result))
                self._assert_names(vi.command_of(recover[0]), vi.WT, route.script_name)

    def test_build_epic(self):
        result = epic.run_epic([[epic.ticket(1)]])
        recover = epic.calls(result, epic.RECOVER)
        self.assertEqual(len(recover), 1, epic.labels_of(result))
        self._assert_names(epic.command_of(recover[0]), epic.WT, "build-epic.js")

    def test_fast_lane_resumed_drive(self):
        result = lane.run_lane({}, created=False)
        recover = lane.calls(result, lane.RECOVER)
        self.assertEqual(len(recover), 1, lane.labels_of(result))
        self._assert_names(lane.command_of(recover[0]), lane.WORKTREE, "fast-lane-ship.js")


if __name__ == "__main__":
    unittest.main()
