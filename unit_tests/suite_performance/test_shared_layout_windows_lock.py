"""
MODULE: test_shared_layout_windows_lock
GOAL: Prove the shared-layout run lock excludes two real OS processes on
    Windows (msvcrt byte-range lock) and that a platform with no lock
    primitive still raises instead of silently running unlocked.
BUSINESS CONTEXT: BO-4300b-4 Windows proof arm. Hardening ticket 03 routed
    the deployed-maker fixtures through the shared layout producer, whose
    lock was POSIX-only; this guards the Windows implementation.
ARCHITECTURE: Unit tests over scripts/suite_performance/
    _shared_layout_coordination.run_lock; the exclusion test spawns two
    child interpreters and is skipped on POSIX.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "suite_performance"))

import _shared_layout_coordination as coord  # noqa: E402

_CHILD = textwrap.dedent(
    """
    import sys, time
    sys.path.insert(0, sys.argv[1])
    from pathlib import Path
    import _shared_layout_coordination as coord
    with coord.run_lock(Path(sys.argv[2])):
        print("ACQUIRED", flush=True)
        time.sleep(float(sys.argv[3]))
    """
)


class TestUnsupportedPlatform(unittest.TestCase):
    """No fcntl and no msvcrt must raise, never no-op."""

    def test_raises_without_any_primitive(self) -> None:
        with TemporaryDirectory() as tmp:
            with mock.patch.object(coord, "fcntl", None), mock.patch.object(
                coord, "msvcrt", None
            ):
                with self.assertRaises(coord.SharedReferenceLayoutError):
                    with coord.run_lock(Path(tmp)):
                        pass


@unittest.skipUnless(sys.platform == "win32", "Windows msvcrt lock only")
class TestWindowsLockExcludesProcesses(unittest.TestCase):
    """Two real processes must not hold the run lock at the same time."""

    def _spawn(self, run_base: str, hold_s: float) -> subprocess.Popen:
        return subprocess.Popen(
            [sys.executable, "-c", _CHILD, str(REPO_ROOT / "scripts" / "suite_performance"),
             run_base, str(hold_s)],
            stdout=subprocess.PIPE,
            text=True,
        )

    def test_second_process_waits_for_first(self) -> None:
        with TemporaryDirectory() as tmp:
            first = self._spawn(tmp, 2.0)
            try:
                self.assertEqual(first.stdout.readline().strip(), "ACQUIRED")
                held_at = time.monotonic()
                second = self._spawn(tmp, 0.0)
                try:
                    self.assertEqual(second.stdout.readline().strip(), "ACQUIRED")
                    waited = time.monotonic() - held_at
                finally:
                    second.wait(timeout=30)
            finally:
                first.wait(timeout=30)
            self.assertGreaterEqual(waited, 1.0, "second process did not block on the lock")
            self.assertEqual(first.returncode, 0)

    def test_lock_is_released_after_with_block(self) -> None:
        with TemporaryDirectory() as tmp:
            with coord.run_lock(Path(tmp)):
                pass
            with coord.run_lock(Path(tmp)):
                pass


if __name__ == "__main__":
    unittest.main()
