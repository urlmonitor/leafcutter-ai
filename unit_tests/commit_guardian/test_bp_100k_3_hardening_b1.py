"""
MODULE: unit_tests/commit_guardian/test_bp_100k_3_hardening_b1.py
GOAL: Round-2 adversarial-review hardening for check_output_drift.py /
    build_helpers.py (BP-100k-3 / BP-100k-5's "uncomparable must never be
    silent" charter) — the B-1 BLOCKER finding, split into its own file
    (alongside test_bp_100k_3_hardening_b2.py and
    test_bp_100k_3_hardening_h1_h5.py) to stay under the 400-line
    check-file-size limit.
BUSINESS CONTEXT: See /tmp/review_code_round2.md for the original
    reproduction. Findings covered here:
      1. B-1(a) — an empty ``output_mappings`` was a clean exit-0 pass: the
         ``verified == 0`` floor was gated on ``output_mappings`` being
         truthy, so a well-formed manifest recording ZERO output mappings
         (now reachable in practice via build_helpers.py's per-section
         existence gates) skipped the floor entirely.
      2. B-1(b) — every per-file existence gate added to
         ``_compute_output_mappings()`` recorded NOTHING when it fired (a
         bare ``continue``); "the phase did not write it" must reach the
         manifest as DATA (``output_mappings_unwritten``), even though (per
         the ticket's own instruction) this data is deliberately NOT wired
         into either gate's verdict — see that field's own docstring in
         build_helpers.py for why.

HARD CONSTRAINT (repo standing rule, "Gate / Workflow ACs — Verify
    Behaviorally, Not by Grep"): every test below EXECUTES the real,
    unmodified-by-this-file gate module (or ``write_build_manifest()``
    itself) against a synthesized manifest/deployed-output fixture, and
    asserts on the process's actual exit status / emitted RESULT/BLOCKED
    lines or the written manifest's actual content — never a grep of the
    gate's source.

RED BASELINE (captured 2026-08-26, before this round's fix, against the real
    template source at templates/scripts/commit_guardian/ and
    scripts/build_helpers.py): each class below states the specific pre-fix
    behaviour its test pins in its own docstring.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TEMPLATES_DIR = _REPO_ROOT / "templates"
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_CONFIG_DIR = _REPO_ROOT / "config"
_CG_TEMPLATES_SRC = _TEMPLATES_DIR / "scripts" / "commit_guardian"

_SUBPROCESS_TIMEOUT_SECONDS = 15

sys.path.insert(0, str(_SCRIPTS_DIR))
import build_helpers  # noqa: E402  (must follow the sys.path insert above)

_RESULT_LINE_RE = re.compile(
    r"(check-build-drift|check-output-drift):\s*RESULT\s+"
    r"verified=(\d+)\s+uncomparable=(\d+)\s+exempt=(\d+)\s+gaps=(\d+)\s+"
    r"drifted=(\d+)\s+missing=(\d+)(?:\s+unreadable=(\d+))?",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Shared helpers (mirrors test_bp_100k_3.py / test_bp_100n_1.py's fixture
# idiom, duplicated rather than imported — small, self-contained fixtures per
# file is the established convention in this test suite).
# ---------------------------------------------------------------------------


def _build_synthetic_workspace(workspace: Path) -> Path:
    """Build a minimal synthetic consumer-install layout under ``workspace``.

    Mirrors the layout ``_resolve_manifest_path`` discovers in real consumer
    installs: ``<workspace>/leafcutter-ai`` is the package root (holds
    ``templates/`` and the manifest); deployed outputs live directly under
    ``<workspace>/.claude/...`` (repo-root == workspace).

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

    The manifest lands in the WORKSPACE root (``pkg_root.parent``), matching
    the real invariant both gates rely on: manifest_path.parent is the base
    every key was computed relative to.

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
# B-1(a) (BLOCKER): an empty output_mappings must not be a clean exit-0 pass.
# ===========================================================================


class TestEmptyOutputMappingsIsNotAcleanPass(unittest.TestCase):
    """B-1(a): a well-formed manifest recording ZERO output mappings (the
    exact shape build_helpers.py's own per-section existence gates can now
    produce) must not report a clean run just because there was nothing to
    scan either.

    RED BASELINE (pre-fix): the ``verified == 0`` floor in
    ``check_output_drift()`` was gated on ``if output_mappings and
    result.verified == 0`` — ``{}`` is falsy, so the floor never fired, and
    the hook printed ``RESULT verified=0 ... drifted=0 missing=0`` and
    exited 0. This test asserts the OPPOSITE: exit != 0 (specifically 2,
    INDETERMINATE-style BLOCKED) and the RESULT line still shows
    verified=0.
    """

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        # Deliberately do NOT create ANY deployed output directories
        # (.claude/agents etc.) — this reproduces the reviewer's exact
        # fixture: a manifest recording zero output mappings, scanned
        # against a tree where the floor directories don't exist either
        # (e.g. a target-dir mismatch between the deploy phases and the
        # manifest write), so the scan finds nothing to report as a GAP.
        pkg_root = _build_synthetic_workspace(self.workspace)
        shutil.rmtree(self.workspace / ".claude")
        _write_manifest(
            pkg_root,
            {
                "output_mappings": {},
                "output_mappings_error": "",
                "output_mappings_skipped_sections": [],
            },
        )
        self.hook = _deploy_commit_guardian_dir(self.workspace) / "check_output_drift.py"

    def test_empty_output_mappings_does_not_exit_zero(self) -> None:
        # covers: BP-100k-3
        result = _run_hook(self.hook, self.workspace)
        combined = result.stdout + result.stderr
        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "check-output-drift exited 0 (clean) on a manifest recording "
                f"ZERO output mappings. Output:\n{combined}"
            ),
        )

    def test_empty_output_mappings_result_line_shows_verified_zero(self) -> None:
        # covers: BP-100k-3
        result = _run_hook(self.hook, self.workspace)
        combined = result.stdout + result.stderr
        match = _RESULT_LINE_RE.search(combined)
        self.assertIsNotNone(match, f"No RESULT summary line. Output:\n{combined}")
        self.assertEqual(0, int(match.group(2)), f"verified must be 0. Output:\n{combined}")

    def test_empty_output_mappings_blocked_message_names_zero_mappings(self) -> None:
        # covers: BP-100k-3
        result = _run_hook(self.hook, self.workspace)
        combined = result.stdout + result.stderr
        self.assertIn(
            "ZERO output mappings",
            combined,
            msg=f"BLOCKED message must name the zero-mappings cause. Output:\n{combined}",
        )


# ===========================================================================
# B-1(b): every per-file existence-gate skip in _compute_output_mappings()
# must reach the manifest as DATA, never a silent continue.
# ===========================================================================


def _build_synthetic_full_package_no_deploy(workspace: Path) -> Path:
    """Copy the REAL templates/, scripts/, and config/ trees verbatim.

    Mirrors test_bp_100k_5_partial_output_mappings.py's
    ``_build_synthetic_package_missing_build_phases()`` layout
    (``package_root.parent == target_root``) but does NOT delete anything —
    every deploy phase's real source tree is present. Deliberately runs NO
    deploy phase at all (nothing under ``output_root``), so EVERY per-file
    existence gate in ``_compute_output_mappings()`` fires uniformly,
    isolating exactly the behaviour under test: whether each gate now
    records what it skipped as manifest DATA instead of silently dropping
    it.

    Returns:
        Absolute path to the synthetic package root
        (``<workspace>/leafcutter-ai``).
    """
    pkg_root = workspace / "leafcutter-ai"
    shutil.copytree(_TEMPLATES_DIR, pkg_root / "templates", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(_SCRIPTS_DIR, pkg_root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(_CONFIG_DIR, pkg_root / "config", ignore=shutil.ignore_patterns("__pycache__"))
    return pkg_root


class TestUnwrittenOutputsRecordedAsManifestData(unittest.TestCase):
    """B-1(b): "the phase did not write it" must reach the manifest as DATA.

    RED BASELINE (pre-fix): ``_compute_output_mappings()`` had no
    ``unwritten`` parameter at all, and ``write_build_manifest()`` never
    wrote an ``output_mappings_unwritten`` key — every one of the six
    existence-gated ``continue`` statements recorded nothing. On a tree with
    NO deploy phase run (nothing under ``output_root``), every family's
    existence gate fires, yet the manifest carried zero evidence of it.
    """

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.pkg_root = _build_synthetic_full_package_no_deploy(self.workspace)

    def test_manifest_records_unwritten_outputs_as_data(self) -> None:
        # covers: BP-100k-5
        build_helpers.write_build_manifest(
            self.pkg_root, target_root=self.workspace, config={}, dry_run=False
        )
        manifest_path = self.workspace / ".build_manifest.json"
        self.assertTrue(
            manifest_path.exists(), "setup bug: write_build_manifest() wrote no manifest"
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        unwritten = manifest.get("output_mappings_unwritten")
        self.assertIsNotNone(
            unwritten,
            msg=(
                "manifest has no 'output_mappings_unwritten' key at all. On a "
                "tree with no deploy phase run, every family's existence gate "
                "fires — this must be recorded as manifest DATA, not silently "
                f"dropped. Full manifest keys: {sorted(manifest.keys())}"
            ),
        )
        self.assertTrue(
            unwritten,
            msg=(
                "output_mappings_unwritten is present but empty even though "
                "no deploy phase ran (every existence gate should have "
                "fired at least once)."
            ),
        )

    def test_unwritten_is_not_wired_into_either_gate_verdict(self) -> None:
        # covers: BP-100k-5
        """Deliberate design constraint (documented, not an oversight): this
        round's own instruction warned against blocking on a condition this
        function cannot cleanly distinguish from a legitimate narrow
        fixture/disabled-platform case. This test proves
        output_mappings_unwritten carries no independent blocking power —
        i.e. removing it from an otherwise-identical manifest (simulating
        the pre-fix shape) produces the IDENTICAL verdict.
        """
        build_helpers.write_build_manifest(
            self.pkg_root, target_root=self.workspace, config={}, dry_run=False
        )
        manifest_path = self.workspace / ".build_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertTrue(manifest.get("output_mappings_unwritten"))

        hook = _deploy_commit_guardian_dir(self.workspace) / "check_output_drift.py"
        result = _run_hook(hook, self.workspace)
        combined = result.stdout + result.stderr
        without_unwritten = dict(manifest)
        without_unwritten.pop("output_mappings_unwritten", None)
        manifest_path.write_text(json.dumps(without_unwritten), encoding="utf-8")
        result_without = _run_hook(hook, self.workspace)
        self.assertEqual(
            result.returncode,
            result_without.returncode,
            msg=(
                "Removing output_mappings_unwritten from the manifest changed "
                "the gate's verdict — it must be visibility-only DATA, never "
                f"itself gate-blocking. With: {combined}\nWithout: "
                f"{result_without.stdout + result_without.stderr}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
