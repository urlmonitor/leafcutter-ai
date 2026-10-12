"""
MODULE: tests.kernel.persistence.test_fixb_cross_process
GOAL: Prove `FileRunStore.compare_and_update` is atomic across processes: of two processes racing
    the same revision exactly one wins, and the stored record is the winner's.
BUSINESS CONTEXT: A cancel reported as won must never be overwritten by a concurrent resume
    (Rev 3 section 13.1); cancel and resume are separate processes.
ARCHITECTURE: Two real subprocesses (`cas_child`) race on one run.json; the lock, its timeout and
    its release are also checked in-process.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from kernel.contracts.base import new_id
from kernel.persistence import RunRecord
from kernel.persistence.fsutil import file_lock
from kernel.persistence.run_store import FileRunStore
from tests.kernel.helpers import narrow

ROOT = Path(__file__).resolve().parents[3]


def _spawn(root: Path, run_id: str, label: str, start: float) -> subprocess.Popen:
    """Start one racing child process."""
    return subprocess.Popen(
        [sys.executable, "-m", "tests.kernel.persistence.cas_child", str(root), run_id, label,
         str(start)], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


class TestCrossProcessCompareAndUpdate(unittest.TestCase):
    """One winner, and the winner's record is what is stored."""

    def test_two_processes_racing_one_revision_have_exactly_one_winner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = FileRunStore(Path(tmp))
            record = RunRecord(run_id=new_id("run"), root_task_id=new_id("task"))
            store.create_run(record)
            start = time.time() + 1.5
            procs = {label: _spawn(Path(tmp), record.run_id, label, start)
                     for label in ("cancel", "resume")}
            out = {}
            for label, proc in procs.items():
                stdout, stderr = proc.communicate(timeout=30)
                self.assertEqual(proc.returncode, 0, stderr)
                out[label] = stdout.split()[-1] == "True"
            self.assertEqual(sorted(out.values()), [False, True], out)
            winner = next(label for label, won in out.items() if won)
            stored = store.get_run(record.run_id)
            self.assertEqual(narrow(stored.cancel).by, winner)
            self.assertEqual(stored.state_revision, 1)


class TestFileLock(unittest.TestCase):
    """The lock is exclusive, bounded and released."""

    def test_a_held_lock_times_out_and_is_reusable_after_release(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.lock"
            with file_lock(path), self.assertRaises(TimeoutError):
                with file_lock(path, timeout=0.2):
                    self.fail("the lock was held twice")
            with file_lock(path, timeout=0.5):
                pass


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 20:00 [python-coder]: Regression for review finding R3-3, with real processes and
#   a slowed atomic write so the unguarded check-then-write race is deterministic.
#   (#KernelBootstrapV0/FIXB)
# ====================================================================
