"""
MODULE: unit_tests/build_guards/test_bp_100k_5_partial_output_mappings.py
GOAL: BP-100k-5 — a PARTIAL output_mappings enumeration failure (one section,
    e.g. the agents/commands/workflows/hooks family, fails to enumerate while
    the rest of the manifest computes normally) must be recorded as manifest
    DATA, never silently swallowed. The manifest must name which section was
    skipped and why, and both drift gates must refuse to report a clean run
    while that record is non-empty.
BUSINESS CONTEXT: ``_compute_output_mappings()`` in scripts/build_helpers.py
    wraps its ``_load_build_phases_module`` / ``_compute_phase_mappings``
    call in a ``try/except`` that, on failure (e.g. a ``package_root`` whose
    ``scripts/`` tree is missing ``build_phases.py``), printed a build-time
    warning and continued with an EMPTY ``phase_mappings`` list — leaving
    ``output_mappings`` looking like a normal, complete dict with that
    section's entries simply absent. Nothing downstream (the written
    manifest, or either drift gate reading it later from a completely
    separate process on a consumer machine, long after the warning scrolled
    off a build log) could tell "this build genuinely has no workflow-JS/
    agents/commands/hooks outputs" apart from "that whole family silently
    failed to enumerate". A gate that cannot check a section must not act as
    though it did — the exact BP-100k-3/-5 phantom-pass shape, one level
    down from the whole-manifest ``output_mappings_error`` field.
ARCHITECTURE / EXERCISE STRATEGY:
    Mirrors unit_tests/build_guards/test_bp_100k_2.py's
    ``_build_synthetic_full_package()`` pattern: build a synthetic package
    root at the same relative depth self-hosting production uses
    (``package_root.parent`` == the workspace/target root passed to
    ``build.py --target-dir``), copying the REAL ``templates/``, ``scripts/``,
    and ``config/`` trees — then delete the ONE file
    (``scripts/build_phases.py``) whose absence is exactly the reproduce
    scenario this fix addresses, so ``_load_build_phases_module`` raises
    ``FileNotFoundError`` (an ``OSError`` subclass) for that section alone
    while ``template_compiler`` and its dependencies (still present) let the
    rest of ``_compute_output_mappings`` run to completion.

    No deploy phase is run in this fixture at all — with nothing under
    ``output_root`` yet, every OTHER section of ``_compute_output_mappings``
    degrades via its own per-file existence check to registering nothing
    (not an error), which isolates the one behaviour under test: whether the
    single caught exception in the agents/commands/workflows/hooks section is
    recorded as manifest DATA rather than only a transient build-time
    warning.

    The gate-behavioral test then deploys a REAL, byte-identical copy of
    check_output_drift.py (plus _resolve_root.py) into a synthesized deployed
    layout and invokes it as a subprocess exactly as pre-commit does — the
    same pattern proven in test_bp_100k_2.py and
    unit_tests/commit_guardian/test_ge_118b_drift_manifest_resolution.py.
    This is a behavioral check (the gate is actually executed and its real
    exit code asserted), not a grep of either module's source, per this
    repo's "Gate / Workflow ACs — Verify Behaviorally, Not by Grep" rule.
"""

from __future__ import annotations

import json
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
_RESOLVE_ROOT_SRC = _CG_TEMPLATES_SRC / "_resolve_root.py"
_CHECK_OUTPUT_DRIFT_SRC = _CG_TEMPLATES_SRC / "check_output_drift.py"

_SUBPROCESS_TIMEOUT_SECONDS = 20

sys.path.insert(0, str(_SCRIPTS_DIR))
import build_helpers  # noqa: E402  (must follow the sys.path insert above)


def _build_synthetic_package_missing_build_phases(workspace: Path) -> Path:
    """Copy the REAL templates/, scripts/, and config/ trees, then delete
    scripts/build_phases.py to reproduce the exact enumeration failure.

    Mirrors test_bp_100k_2.py's ``_build_synthetic_full_package()`` layout
    (``package_root.parent == target_root``) so ``_compute_output_mappings``'s
    relative-path arithmetic behaves exactly as it does for a real
    ``python scripts/build.py --target-dir .`` run.

    Args:
        workspace: Temp directory to build the synthetic layout inside.

    Returns:
        Absolute path to the synthetic package root
        (``<workspace>/leafcutter-ai``), with ``scripts/build_phases.py``
        absent.
    """
    pkg_root = workspace / "leafcutter-ai"
    shutil.copytree(_TEMPLATES_DIR, pkg_root / "templates", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(_SCRIPTS_DIR, pkg_root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(_CONFIG_DIR, pkg_root / "config", ignore=shutil.ignore_patterns("__pycache__"))
    (pkg_root / "scripts" / "build_phases.py").unlink()
    return pkg_root


def _deploy_hook(base: Path, hook_src: Path) -> Path:
    """Copy the real check_output_drift.py into a synthesized deployed layout.

    Args:
        base: Temp directory to build the fake deployment inside.
        hook_src: Absolute path to the real hook module to copy.

    Returns:
        Absolute path to the copied hook module.
    """
    deployed_dir = base / ".leafcutter" / "scripts" / "commit_guardian"
    deployed_dir.mkdir(parents=True, exist_ok=True)
    dest = deployed_dir / hook_src.name
    shutil.copy(hook_src, dest)
    if _RESOLVE_ROOT_SRC.exists():
        shutil.copy(_RESOLVE_ROOT_SRC, deployed_dir / "_resolve_root.py")
    return dest


def _run_hook(hook_path: Path, cwd: Path) -> subprocess.CompletedProcess:
    """Invoke a deployed hook copy as a subprocess, exactly as pre-commit does.

    Args:
        hook_path: Absolute path to the (copied) hook module to execute.
        cwd: Working directory to run the subprocess in.

    Returns:
        The completed subprocess result (returncode, stdout, stderr captured).
    """
    return subprocess.run(
        [sys.executable, str(hook_path)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


class TestPartialOutputMappingsEnumerationRecordedAsData(unittest.TestCase):
    """BP-100k-5: a partial (per-section) output_mappings failure must be
    recorded as manifest data and must block both drift gates from
    reporting a clean run."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.pkg_root = _build_synthetic_package_missing_build_phases(self.workspace)

    def test_manifest_records_which_section_was_skipped_and_why(self) -> None:
        # covers: BP-100k-5
        build_helpers.write_build_manifest(
            self.pkg_root, target_root=self.workspace, config={}, dry_run=False
        )

        manifest_path = self.workspace / ".build_manifest.json"
        self.assertTrue(
            manifest_path.exists(), "setup bug: write_build_manifest() wrote no manifest"
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        skipped = manifest.get("output_mappings_skipped_sections")
        self.assertTrue(
            skipped,
            msg=(
                "manifest has no non-empty 'output_mappings_skipped_sections' "
                "entry even though scripts/build_phases.py was deleted from "
                "the synthetic package, which must make the agents/commands/"
                "workflows/hooks enumeration raise. A manifest that silently "
                "drops a whole section without recording why it was dropped "
                f"is the BP-100k-5 defect. Full manifest keys: {sorted(manifest.keys())}"
            ),
        )
        self.assertTrue(
            any("build_phases" in entry or "deploy-phase" in entry for entry in skipped),
            msg=(
                "output_mappings_skipped_sections does not name the "
                f"deploy-phase enumeration as the skipped section: {skipped}"
            ),
        )
        # The whole-computation field must stay empty — this is a PARTIAL
        # failure (one section), not a total one; conflating the two would
        # make it impossible for a reader to tell which manifest shape they
        # are looking at.
        self.assertEqual(
            manifest.get("output_mappings_error"), "",
            msg=(
                "output_mappings_error must remain empty for a partial, "
                "per-section failure — only output_mappings_skipped_sections "
                "should record it."
            ),
        )

    def test_output_drift_gate_does_not_exit_clean_on_a_partial_manifest(self) -> None:
        # covers: BP-100k-5
        build_helpers.write_build_manifest(
            self.pkg_root, target_root=self.workspace, config={}, dry_run=False
        )

        hook_path = _deploy_hook(self.workspace, _CHECK_OUTPUT_DRIFT_SRC)
        result = _run_hook(hook_path, self.workspace)

        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "check_output_drift.py exited 0 (clean) against a manifest "
                "that records a skipped output_mappings section — a gate "
                "that could not check a whole section must not report the "
                f"run as clean. stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            ),
        )
        combined = result.stdout + result.stderr
        self.assertIn(
            "BLOCKED",
            combined,
            msg=f"No BLOCKED message printed for the partial manifest. Output:\n{combined}",
        )


if __name__ == "__main__":
    unittest.main()
