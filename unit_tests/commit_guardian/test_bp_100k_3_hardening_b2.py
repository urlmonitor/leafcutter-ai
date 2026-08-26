"""
MODULE: unit_tests/commit_guardian/test_bp_100k_3_hardening_b2.py
GOAL: Round-2 adversarial-review hardening for check_output_drift.py
    (BP-100k-3's "uncomparable must never be silent" charter) — the B-2
    BLOCKER finding, split into its own file (alongside
    test_bp_100k_3_hardening_b1.py and test_bp_100k_3_hardening_h1_h5.py) to
    stay under the 400-line check-file-size limit.
BUSINESS CONTEXT: See /tmp/review_code_round2.md for the original
    reproduction. B-2 (BLOCKER) — an unreadable, recorded output (e.g.
    ``chmod 000``) landed in NO bucket at all (not verified, not a gap, not
    missing) and the run reported clean, identical to a hash-matched pass.
    Unified with a reconciliation-invariant finding: a manifest-recorded key
    whose file has been replaced by a DIRECTORY is neither deleted
    (``.exists()`` is True for a directory too) nor hashable, and must also
    land in the same ``unreadable`` bucket rather than in none.

HARD CONSTRAINT (repo standing rule, "Gate / Workflow ACs — Verify
    Behaviorally, Not by Grep"): every test below EXECUTES the real,
    unmodified-by-this-file gate module as a subprocess against a synthesized
    manifest/deployed-output fixture, and asserts on the process's actual
    exit status and emitted RESULT/UNCOMPARABLE lines — never a grep of the
    gate's source.

RED BASELINE (captured 2026-08-26, before this round's fix, against the real
    template source at templates/scripts/commit_guardian/): each class below
    states the specific pre-fix behaviour its test pins in its own docstring.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TEMPLATES_DIR = _REPO_ROOT / "templates"
_CG_TEMPLATES_SRC = _TEMPLATES_DIR / "scripts" / "commit_guardian"

_SUBPROCESS_TIMEOUT_SECONDS = 15

_RESULT_LINE_RE = re.compile(
    r"(check-build-drift|check-output-drift):\s*RESULT\s+"
    r"verified=(\d+)\s+uncomparable=(\d+)\s+exempt=(\d+)\s+gaps=(\d+)\s+"
    r"drifted=(\d+)\s+missing=(\d+)(?:\s+unreadable=(\d+))?",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Shared helpers (mirrors test_bp_100k_3.py / test_bp_100k_6.py's fixture
# idiom, duplicated rather than imported — small, self-contained fixtures per
# file is the established convention in this test suite).
# ---------------------------------------------------------------------------


def _sha256_bytes(data: bytes) -> str:
    """Return the SHA-256 hex digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def _build_synthetic_workspace(workspace: Path) -> Path:
    """Build a minimal synthetic consumer-install layout under ``workspace``.

    Returns:
        Absolute path to the synthetic package root
        (``<workspace>/leafcutter-ai``).
    """
    pkg_root = workspace / "leafcutter-ai"
    (pkg_root / "templates" / "agents").mkdir(parents=True)
    (pkg_root / "templates" / "scripts" / "commit_guardian").mkdir(parents=True)
    (workspace / ".claude" / "agents").mkdir(parents=True)
    return pkg_root


def _write_manifest(pkg_root: Path, manifest: dict) -> Path:
    """Write .build_manifest.json via the real JSON serializer.

    Returns:
        Absolute path to the manifest written.
    """
    manifest.setdefault("package_root", pkg_root.name)
    manifest_path = pkg_root.parent / ".build_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def _deploy_commit_guardian_dir(workspace: Path) -> Path:
    """Copy the REAL, unmodified templates/scripts/commit_guardian/ tree.

    Returns:
        Absolute path to the deployed commit_guardian directory.
    """
    deployed_dir = workspace / ".leafcutter" / "scripts" / "commit_guardian"
    shutil.copytree(
        _CG_TEMPLATES_SRC, deployed_dir, ignore=shutil.ignore_patterns("__pycache__")
    )
    return deployed_dir


def _run_hook(hook_path: Path, cwd: Path) -> subprocess.CompletedProcess:
    """Execute a deployed gate module as a subprocess, exactly as pre-commit does."""
    return subprocess.run(
        [sys.executable, str(hook_path)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


class TestUnreadableOutputCannotBypassDriftDetection(unittest.TestCase):
    """B-2: chmod 000'ing a drifted, manifest-recorded output must not turn a
    caught violation into a clean pass.

    RED BASELINE (pre-fix): readable+drifted -> exit 1, RESULT
    ``verified=2 gaps=0 drifted=1``. Same fixture, only the file's
    permission bit changed to 000 -> exit 0, RESULT ``verified=1 gaps=0
    drifted=0`` — chmod 000 was a working bypass. This test pins the fixed
    behaviour: the chmod-000 case must ALSO be non-clean, and the new
    ``unreadable`` RESULT field must count it.
    """

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.pkg_root = _build_synthetic_workspace(self.workspace)
        self.agents_dir = self.workspace / ".claude" / "agents"

        good_content = b"# good.md\nmatches the manifest\n"
        self.good_path = self.agents_dir / "good.md"
        self.good_path.write_bytes(good_content)
        good_key = self.good_path.relative_to(self.workspace).as_posix()

        self.bad_path = self.agents_dir / "bad.md"
        self.bad_path.write_bytes(b"# bad.md\nORIGINAL, will drift\n")
        bad_key = self.bad_path.relative_to(self.workspace).as_posix()
        # Manifest records a DIFFERENT hash than what is currently on disk
        # -> a genuine drift violation, matching the reviewer's control case.
        drifted_expected_hash = _sha256_bytes(b"# bad.md\nDRIFTED already, differs\n")

        _write_manifest(
            self.pkg_root,
            {
                "output_mappings": {
                    good_key: {
                        "template": "templates/agents/good.md",
                        "expected_output_hash": _sha256_bytes(good_content),
                    },
                    bad_key: {
                        "template": "templates/agents/bad.md",
                        "expected_output_hash": drifted_expected_hash,
                    },
                },
                "output_mappings_error": "",
                "output_mappings_skipped_sections": [],
            },
        )
        self.hook = _deploy_commit_guardian_dir(self.workspace) / "check_output_drift.py"

    def test_readable_and_drifted_blocks_as_control(self) -> None:
        # covers: BP-100k-3
        """Control case: readable + drifted must block (exit 1) — proves the
        fixture itself is a genuine drift case before the permission bit is
        touched."""
        result = _run_hook(self.hook, self.workspace)
        combined = result.stdout + result.stderr
        self.assertEqual(
            1, result.returncode, msg=f"Control case must exit 1. Output:\n{combined}"
        )

    def test_chmod_000_cannot_turn_the_violation_into_a_clean_pass(self) -> None:
        # covers: BP-100k-3
        os.chmod(self.bad_path, 0o000)
        self.addCleanup(os.chmod, self.bad_path, 0o644)
        try:
            result = _run_hook(self.hook, self.workspace)
        finally:
            os.chmod(self.bad_path, 0o644)
        combined = result.stdout + result.stderr
        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "chmod 000 on a drifted, manifest-recorded output must not "
                f"produce a clean exit. Output:\n{combined}"
            ),
        )

    def test_chmod_000_is_counted_as_unreadable_not_silently_dropped(self) -> None:
        # covers: BP-100k-3
        os.chmod(self.bad_path, 0o000)
        self.addCleanup(os.chmod, self.bad_path, 0o644)
        try:
            result = _run_hook(self.hook, self.workspace)
        finally:
            os.chmod(self.bad_path, 0o644)
        combined = result.stdout + result.stderr
        match = _RESULT_LINE_RE.search(combined)
        self.assertIsNotNone(match, f"No RESULT summary line. Output:\n{combined}")
        unreadable = match.group(8)
        self.assertIsNotNone(
            unreadable,
            msg=f"RESULT line must carry an 'unreadable=' field. Output:\n{combined}",
        )
        self.assertEqual(
            1,
            int(unreadable),
            msg=(
                "Exactly one artifact (bad.md) is unreadable; it must be "
                f"counted, not silently dropped. Output:\n{combined}"
            ),
        )
        self.assertIn(
            "UNCOMPARABLE: UNREADABLE",
            combined,
            msg=f"The unreadable artifact must be individually named. Output:\n{combined}",
        )
        # The OTHER, readable+matching artifact must still verify — proves
        # the unreadable bucket did not eat every artifact indiscriminately.
        self.assertEqual(1, int(match.group(2)), f"verified must be 1 (good.md). Output:\n{combined}")


class TestOutputReplacedByDirectoryIsUnreadableNotInvisible(unittest.TestCase):
    """Reconciliation-invariant regression (unified with B-2): a
    manifest-recorded key whose on-disk path has been replaced by a
    DIRECTORY is neither deleted (``.exists()`` is True for a directory
    too, so the pre-existing MISSING sweep could not see it) nor a normal
    file to hash — it must land in the ``unreadable`` bucket, never in
    neither.
    """

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        pkg_root = _build_synthetic_workspace(self.workspace)
        agents_dir = self.workspace / ".claude" / "agents"

        # Recorded as a file in the manifest, but ACTUALLY a directory (left
        # empty deliberately — a file nested inside it would itself surface
        # as an unrelated GAP via Pass 1's real-file scan, which is not what
        # this test is pinning).
        replaced_path = agents_dir / "replaced.md"
        replaced_path.mkdir()
        replaced_key = replaced_path.relative_to(self.workspace).as_posix()

        _write_manifest(
            pkg_root,
            {
                "output_mappings": {
                    replaced_key: {
                        "template": "templates/agents/replaced.md",
                        "expected_output_hash": _sha256_bytes(b"whatever"),
                    },
                },
                "output_mappings_error": "",
                "output_mappings_skipped_sections": [],
            },
        )
        self.hook = _deploy_commit_guardian_dir(self.workspace) / "check_output_drift.py"

    def test_path_replaced_by_a_directory_is_not_a_clean_pass(self) -> None:
        # covers: BP-100k-3
        result = _run_hook(self.hook, self.workspace)
        combined = result.stdout + result.stderr
        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "A manifest key whose file was replaced by a directory must "
                f"not produce a clean exit. Output:\n{combined}"
            ),
        )
        match = _RESULT_LINE_RE.search(combined)
        self.assertIsNotNone(match, f"No RESULT summary line. Output:\n{combined}")
        self.assertEqual(0, int(match.group(2)), f"verified must be 0. Output:\n{combined}")
        self.assertEqual(0, int(match.group(7)), f"missing must be 0 (path exists). Output:\n{combined}")
        unreadable = match.group(8)
        self.assertIsNotNone(unreadable, f"RESULT line must carry 'unreadable='. Output:\n{combined}")
        self.assertEqual(1, int(unreadable), f"unreadable must be 1. Output:\n{combined}")


if __name__ == "__main__":
    unittest.main()
