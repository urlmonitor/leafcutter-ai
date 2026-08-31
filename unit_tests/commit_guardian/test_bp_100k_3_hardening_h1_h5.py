"""
MODULE: unit_tests/commit_guardian/test_bp_100k_3_hardening_h1_h5.py
GOAL: Round-2 adversarial-review hardening for check_output_drift.py and
    check_build_drift.py (BP-100k-3 / BP-100k-5) — the H-1 and H-5 HIGH
    findings, split into their own file (alongside
    test_bp_100k_3_hardening_b1.py and test_bp_100k_3_hardening_b2.py) to
    stay under the 400-line check-file-size limit.
BUSINESS CONTEXT: See /tmp/review_code_round2.md for the original
    reproductions. Findings covered here:
      1. H-1 (HIGH) — a manifest that EXISTS but is corrupt (unparseable
         JSON, or a missing/malformed ``output_mappings`` section) was
         treated exactly like a genuinely absent manifest (fresh clone) —
         exit 0 — instead of INDETERMINATE.
      2. H-5 (HIGH) — check_build_drift.py never read
         ``output_mappings_error``, contradicting write_build_manifest()'s
         own docstring/DECISION HISTORY, which claimed both drift gates
         honour it.

HARD CONSTRAINT (repo standing rule, "Gate / Workflow ACs — Verify
    Behaviorally, Not by Grep"): every test below EXECUTES the real,
    unmodified-by-this-file gate module as a subprocess against a synthesized
    manifest fixture, and asserts on the process's actual exit status and
    emitted RESULT/BLOCKED/INDETERMINATE lines — never a grep of the gate's
    source.

RED BASELINE (captured 2026-08-26, before this round's fix, against the real
    template source at templates/scripts/commit_guardian/): each class below
    states the specific pre-fix behaviour its test pins in its own docstring.
"""

from __future__ import annotations

import hashlib
import json
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


# ---------------------------------------------------------------------------
# Shared helpers (mirrors test_bp_100k_3.py's fixture idiom, duplicated
# rather than imported — small, self-contained fixtures per file is the
# established convention in this test suite).
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


# ===========================================================================
# H-1 (HIGH): a manifest that EXISTS but is corrupt must be INDETERMINATE,
# never treated the same as a genuinely absent manifest.
# ===========================================================================


class TestCorruptManifestIsIndeterminateNotAcleanPass(unittest.TestCase):
    """H-1: both drift gates must distinguish "no manifest yet" (fresh clone,
    fail-open, exit 0) from "a manifest exists but is corrupt or has no
    valid output_mappings section" (a broken build artifact — INDETERMINATE,
    exit 2).

    RED BASELINE (pre-fix): both gates called ``_load_output_mappings()`` /
    inline manifest loading, which returned ``None`` for BOTH conditions
    identically, and both callers did ``return 0`` on ``None`` — a corrupt
    manifest with real drift present exited 0 exactly like a fresh clone.
    """

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.pkg_root = _build_synthetic_workspace(self.workspace)
        self.deployed_dir = _deploy_commit_guardian_dir(self.workspace)

    def _write_corrupt_manifest(self) -> None:
        manifest_path = self.workspace / ".build_manifest.json"
        manifest_path.write_text("{ this is not valid json and never parses ", encoding="utf-8")

    def _write_manifest_with_bad_section(self) -> None:
        # Present, valid JSON, but output_mappings is the wrong type.
        manifest_path = self.workspace / ".build_manifest.json"
        manifest_path.write_text(
            json.dumps({"output_mappings": "not-a-dict", "package_root": "leafcutter-ai"}),
            encoding="utf-8",
        )

    def test_output_drift_corrupt_manifest_is_indeterminate(self) -> None:
        # covers: BP-100k-3
        self._write_corrupt_manifest()
        hook = self.deployed_dir / "check_output_drift.py"
        result = _run_hook(hook, self.workspace)
        combined = result.stdout + result.stderr
        self.assertEqual(
            2,
            result.returncode,
            msg=(
                "A present-but-corrupt manifest must exit 2 (INDETERMINATE), "
                f"never 0. Output:\n{combined}"
            ),
        )
        self.assertIn("INDETERMINATE", combined, msg=f"Output:\n{combined}")

    def test_build_drift_corrupt_manifest_is_indeterminate(self) -> None:
        # covers: BP-100k-3
        self._write_corrupt_manifest()
        hook = self.deployed_dir / "check_build_drift.py"
        result = _run_hook(hook, self.workspace)
        combined = result.stdout + result.stderr
        self.assertEqual(
            2,
            result.returncode,
            msg=(
                "A present-but-corrupt manifest must exit 2 (INDETERMINATE), "
                f"never 0. Output:\n{combined}"
            ),
        )
        self.assertIn("INDETERMINATE", combined, msg=f"Output:\n{combined}")

    def test_output_drift_malformed_output_mappings_section_is_indeterminate(self) -> None:
        # covers: BP-100k-3
        self._write_manifest_with_bad_section()
        hook = self.deployed_dir / "check_output_drift.py"
        result = _run_hook(hook, self.workspace)
        combined = result.stdout + result.stderr
        self.assertEqual(
            2,
            result.returncode,
            msg=(
                "A manifest whose output_mappings section is not a dict must "
                f"exit 2 (INDETERMINATE), never 0. Output:\n{combined}"
            ),
        )
        self.assertIn("INDETERMINATE", combined, msg=f"Output:\n{combined}")

    def test_genuinely_absent_manifest_still_fails_open(self) -> None:
        # covers: BP-100k-3
        """Sanity/regression guard: the fresh-clone case (no manifest
        anywhere) must remain non-blocking — this round's fix must not
        collapse the absent case into the corrupt case."""
        hook = self.deployed_dir / "check_output_drift.py"
        result = _run_hook(hook, self.workspace)
        combined = result.stdout + result.stderr
        self.assertEqual(
            0,
            result.returncode,
            msg=f"A genuinely absent manifest must fail-open (exit 0). Output:\n{combined}",
        )


# ===========================================================================
# H-5 (HIGH): check_build_drift must honour output_mappings_error, exactly
# as write_build_manifest()'s own docstring claims.
# ===========================================================================


class TestBuildDriftHonoursOutputMappingsError(unittest.TestCase):
    """H-5: check_build_drift.py must refuse to report a clean run while
    ``output_mappings_error`` is non-blank, mirroring check_output_drift.py
    and matching write_build_manifest()'s own documented contract.

    RED BASELINE (pre-fix): check_build_drift.py's main() read
    ``output_mappings_skipped_sections`` but never ``output_mappings_error``
    — a healthy Direction A scan (template hashes match) with
    ``output_mappings_error`` set exited 0.
    """

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.pkg_root = _build_synthetic_workspace(self.workspace)

        agents_dir = self.pkg_root / "templates" / "agents"
        self._content = b"# healthy_template.md\nmatches the manifest\n"
        tpl = agents_dir / "healthy_template.md"
        tpl.write_bytes(self._content)
        self._key = tpl.relative_to(self.workspace).as_posix()

        _write_manifest(
            self.pkg_root,
            {
                self._key: _sha256_bytes(self._content),
                "output_mappings": {},
                "output_mappings_error": (
                    "RuntimeError: Direction B computation crashed outright"
                ),
                "output_mappings_skipped_sections": [],
            },
        )
        self.hook = _deploy_commit_guardian_dir(self.workspace) / "check_build_drift.py"

    def test_output_mappings_error_blocks_an_otherwise_healthy_direction_a_scan(self) -> None:
        # covers: BP-100k-5
        result = _run_hook(self.hook, self.workspace)
        combined = result.stdout + result.stderr
        self.assertEqual(
            2,
            result.returncode,
            msg=(
                "check-build-drift must not report a clean run while "
                f"output_mappings_error is non-blank. Output:\n{combined}"
            ),
        )
        self.assertIn(
            "Direction B computation crashed outright",
            combined,
            msg=f"BLOCKED message must name the recorded cause. Output:\n{combined}",
        )

    def test_healthy_manifest_without_the_error_field_still_passes(self) -> None:
        # covers: BP-100k-5
        """Sanity/regression guard: removing output_mappings_error from an
        otherwise-identical healthy manifest must restore a clean exit — the
        fix must not make the gate block unconditionally."""
        _write_manifest(
            self.pkg_root,
            {
                self._key: _sha256_bytes(self._content),
                "output_mappings": {},
                "output_mappings_error": "",
                "output_mappings_skipped_sections": [],
            },
        )
        result = _run_hook(self.hook, self.workspace)
        combined = result.stdout + result.stderr
        self.assertEqual(
            0,
            result.returncode,
            msg=f"A healthy manifest with no error field must exit 0. Output:\n{combined}",
        )


if __name__ == "__main__":
    unittest.main()
