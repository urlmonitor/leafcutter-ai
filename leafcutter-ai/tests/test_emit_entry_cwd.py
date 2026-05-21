"""
MODULE: test_emit_entry_cwd
GOAL: CWD-independence acceptance tests for emit_entry.py.
BUSINESS CONTEXT: Verifies that emit_entry resolves its output directory from
    the script's own __file__ location rather than the calling process's CWD.
    Covers Acceptance Scenarios 1 and 4 from
    TICKET-20260518-EmitEntry_CWD_SelfLocation. Separated from test_emit_entry.py
    to keep both files within the 400-line limit.
ARCHITECTURE: Pure unit tests using unittest.TestCase with os.chdir() and
    tempfile.TemporaryDirectory for filesystem isolation. CWD is always
    restored in finally blocks. No database, no network, no project-tree writes
    except to changelogs/ which are cleaned up immediately.
    All tests must complete in < 5 seconds.
"""

from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


# ---------------------------------------------------------------------------
# Bootstrap: resolve emit_entry module without relying on installed package
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_EMIT_ENTRY_PATH = _REPO_ROOT / "leafcutter" / "scripts" / "changelog" / "emit_entry.py"

spec = importlib.util.spec_from_file_location("emit_entry", _EMIT_ENTRY_PATH)
_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_mod)

emit_entry = _mod.emit_entry


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _base_payload(**overrides) -> dict:
    """Return a valid minimal payload with optional field overrides."""
    payload = {
        "title": "Test Entry Title",
        "date": "2026-05-18",
        "time": "14:15",
        "type": "manual",
        "components": ["infrastructure"],
        "summary": "A test change for CWD independence verification.",
        "description": "CWD independence test changelog entry.",
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestEmitEntryCwdIndependence(unittest.TestCase):
    """Acceptance Scenario 1 & 4: output resolves from __file__, not CWD."""

    def test_output_resolves_from_file_not_cwd(self):
        """Scenario 1: file lands in repo_root/changelogs/ even when CWD is a tempdir.

        Changes the process CWD to a temporary directory that is NOT the repo
        root, calls emit_entry with changelog_dir=None, and verifies the written
        file's parent is <repo_root>/changelogs/ — not <tempdir>/changelogs/.
        """
        expected_repo_root = _REPO_ROOT
        expected_changelogs = expected_repo_root / "changelogs"

        original_cwd = os.getcwd()
        written = None
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                os.chdir(tmpdir)

                payload = _base_payload(
                    title="cwd-independence-test",
                    time="14:15",
                )
                written = emit_entry(payload, None)

                # File must land under <repo_root>/changelogs/, not <tmpdir>/
                self.assertEqual(
                    written.parent.resolve(),
                    expected_changelogs.resolve(),
                    f"Expected file under {expected_changelogs}, got {written.parent}",
                )

                # File must NOT land under tmpdir
                self.assertFalse(
                    str(written).startswith(tmpdir),
                    f"File should not be under tmpdir {tmpdir}, but got {written}",
                )
            finally:
                os.chdir(original_cwd)
                if written is not None and written.exists():
                    written.unlink()

    def test_explicit_absolute_changelog_dir_override(self):
        """Scenario 4: explicit absolute --changelog-dir writes to the supplied path.

        When an absolute path is passed as changelog_dir, it is used directly
        and the config-derived default is not consulted.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            explicit_dir = Path(tmpdir) / "explicit_subdir"
            payload = _base_payload(
                title="explicit-dir-test",
                time="14:20",
            )
            written = emit_entry(payload, explicit_dir)

            # File must be under the explicit absolute dir
            self.assertEqual(written.parent.resolve(), explicit_dir.resolve())
            self.assertTrue(written.exists())

    def test_explicit_relative_changelog_dir_resolves_against_repo_root(self):
        """When a relative path is passed, it resolves against repo root, not CWD.

        This differs from the old CWD-relative behaviour and is the
        documented intent for all three call sites that still pass
        --changelog-dir explicitly.
        """
        expected_repo_root = _REPO_ROOT
        original_cwd = os.getcwd()
        written = None

        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                os.chdir(tmpdir)

                payload = _base_payload(
                    title="relative-dir-test",
                    time="14:25",
                )
                # Pass a relative path — should resolve against repo root
                written = emit_entry(payload, "changelogs")

                expected_dir = (expected_repo_root / "changelogs").resolve()
                self.assertEqual(
                    written.parent.resolve(),
                    expected_dir,
                    f"Relative path should resolve against repo root {expected_repo_root}",
                )

                # File must NOT land under tmpdir
                self.assertFalse(
                    str(written.resolve()).startswith(tmpdir),
                    f"File should not be under CWD {tmpdir}",
                )
            finally:
                os.chdir(original_cwd)
                if written is not None and written.exists():
                    written.unlink()


if __name__ == "__main__":
    unittest.main()
