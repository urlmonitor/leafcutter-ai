"""
MODULE: unit_tests/build_orchestration/test_bo_4300f_4_i_reentrant_guard.py
AC: BO-4300f-4-i -- running the proof leaves the developer's own project unchanged.
GOAL: Prove the developer-repo guard (ADR-051 decision 8) is re-entrant for the pytest
    sessions a guarded session starts itself, without weakening "any difference fails the
    session": a nested session finishes without waiting on its parent's lock, a change it
    makes is still caught by the outer comparison, and a marker that does not name the held
    lock never lets a session skip the lock or its snapshot.
ARCHITECTURE: Every test builds its own throwaway real git repository standing in for the
    developer's project and runs a REAL nested `python -m pytest` subprocess whose conftest.py
    wires the real guard module -- the shape of test_bo4500a_5_v, whose nested run deadlocked
    on the lock its own parent held before this change.

DECISION HISTORY
====================================================================
- 2026-10-21 [smart-bug-resolver/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/18,
  BO-4300f-4-i]: Created with the user-approved re-entrant guard (2026-10-21).
  (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/18)
====================================================================
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

from unit_tests.build_orchestration._bo_4300a_1_fixtures import run_git
from unit_tests.build_orchestration._developer_repo_guard import (
    HELD_LOCK_ENV,
    DeveloperRepoChangedError,
    developer_repo_guard,
)
from unit_tests.build_orchestration.test_bo_4300f_4_i import _make_stand_in_dev_repo

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_NESTED_LOCK_TIMEOUT_S = 3.0


def _write_suite(dev_repo: Path, test_body: str) -> Path:
    """A nested suite inside *dev_repo* whose conftest wires the REAL guard over *dev_repo*."""
    suite = dev_repo / "suite"
    suite.mkdir()
    (suite / "__init__.py").write_text("", encoding="utf-8")
    (suite / "conftest.py").write_text(textwrap.dedent(f"""
        import sys
        from pathlib import Path
        sys.path.insert(0, {str(REPO_ROOT)!r})
        import pytest
        from unit_tests.build_orchestration._developer_repo_guard import developer_repo_guard

        @pytest.fixture(scope="session", autouse=True)
        def _guard():
            with developer_repo_guard(Path({str(dev_repo)!r}), lock_timeout_s={_NESTED_LOCK_TIMEOUT_S}):
                yield
        """), encoding="utf-8")
    (suite / "test_nested.py").write_text(textwrap.dedent(test_body), encoding="utf-8")
    return suite


def _run_nested(suite: Path, env: dict[str, str]) -> tuple[subprocess.CompletedProcess, float]:
    """Run the nested suite as a real pytest session; return the process and its wall time."""
    start = time.monotonic()
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(suite)],
        cwd=str(suite.parent), env=env, capture_output=True, text=True, timeout=120, check=False,
    )
    return proc, time.monotonic() - start


def _lock_key(dev_repo: Path) -> str:
    return os.path.normcase(str((dev_repo / ".git" / "bo4300-proof-suite.lock").resolve()))


class TestNestedSessionsUnderTheGuard(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="bo4300f4i-reentrant-")
        self.addCleanup(self._tmp.cleanup)
        self.dev_repo = _make_stand_in_dev_repo(Path(self._tmp.name) / "devrepo")
        prior = os.environ.get(HELD_LOCK_ENV)
        self.addCleanup(lambda: os.environ.__setitem__(HELD_LOCK_ENV, prior) if prior is not None
                        else os.environ.pop(HELD_LOCK_ENV, None))

    def test_nested_pytest_from_a_guarded_session_finishes_without_waiting(self):
        # covers: BO-4300f-4-i
        # angle: reachability
        """A nested pytest session started inside a guarded session passes, well inside the
        lock timeout its own guard would otherwise wait out."""
        suite = _write_suite(self.dev_repo, "def test_ok():\n    assert True\n")
        with developer_repo_guard(self.dev_repo):
            self.assertEqual(os.environ.get(HELD_LOCK_ENV), _lock_key(self.dev_repo))
            proc, elapsed = _run_nested(suite, dict(os.environ))
        self.assertEqual(proc.returncode, 0, proc.stdout[-2000:] + proc.stderr[-1000:])
        self.assertLess(elapsed, _NESTED_LOCK_TIMEOUT_S + 30, "the nested session waited on the lock")
        self.assertNotIn("DeveloperRepoLockTimeoutError", proc.stdout + proc.stderr)

    def test_a_nested_runs_change_is_still_caught_by_the_outer_comparison(self):
        # covers: BO-4300f-4-i
        # angle: discrimination
        """The nested session skips its own snapshot, so its leaked branch is reported by the
        OUTER guard's comparison -- 'any difference fails the session' still holds."""
        suite = _write_suite(self.dev_repo, f"""
            import subprocess

            def test_leaks_a_branch():
                subprocess.run(["git", "branch", "nested-leak"], cwd={str(self.dev_repo)!r}, check=True)
            """)
        with self.assertRaises(DeveloperRepoChangedError) as caught:
            with developer_repo_guard(self.dev_repo):
                proc, _ = _run_nested(suite, dict(os.environ))
                self.assertEqual(proc.returncode, 0, proc.stdout[-2000:] + proc.stderr[-1000:])
        self.assertIn("nested-leak", str(caught.exception))

    def test_a_marker_for_a_different_lock_path_does_not_skip_the_lock(self):
        # covers: BO-4300f-4-i
        # angle: failure
        """While this repo's lock is held, a session whose inherited marker names a DIFFERENT
        lock waits and times out, exactly as an unrelated concurrent session must."""
        suite = _write_suite(self.dev_repo, "def test_ok():\n    assert True\n")
        with developer_repo_guard(self.dev_repo):
            env = dict(os.environ)
            env[HELD_LOCK_ENV] = os.path.normcase(str(Path(self._tmp.name) / "other" / "bo4300-proof-suite.lock"))
            proc, _ = _run_nested(suite, env)
        self.assertNotEqual(proc.returncode, 0, proc.stdout[-2000:])
        self.assertIn("DeveloperRepoLockTimeoutError", proc.stdout + proc.stderr)

    def test_a_stale_marker_for_a_free_lock_still_takes_the_lock_and_snapshots(self):
        # covers: BO-4300f-4-i
        # angle: boundary
        """A marker naming this very lock while nobody holds it is stale: the session takes the
        lock and compares as usual, so its own leak is still reported."""
        os.environ[HELD_LOCK_ENV] = _lock_key(self.dev_repo)
        with self.assertRaises(DeveloperRepoChangedError) as caught:
            with developer_repo_guard(self.dev_repo, lock_timeout_s=_NESTED_LOCK_TIMEOUT_S):
                run_git(["branch", "stale-marker-leak"], self.dev_repo)
        self.assertIn("stale-marker-leak", str(caught.exception))
        self.assertEqual(os.environ.get(HELD_LOCK_ENV), _lock_key(self.dev_repo), "marker not restored")


if __name__ == "__main__":
    unittest.main()
