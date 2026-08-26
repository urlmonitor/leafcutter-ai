"""
MODULE: unit_tests/build_guards/test_bp_100k_1.py
GOAL: BP-100k-1 — write_build_manifest() must record a comparable fingerprint
    for EVERY template family the build treats as managed (not only
    templates/agents/*.md), so check_build_drift.py never reports a
    non-agent managed template (e.g. a commit-guardian hook script) as
    "not in manifest" — the absent-from-manifest verdict that reads as a
    clean run while drift in that template goes undetected forever.
BUSINESS CONTEXT: write_build_manifest() in scripts/build_helpers.py
    currently populates its flat template_hashes section from
    ``package_root/templates/agents/*.md`` only (build_helpers.py:183-195).
    check_build_drift.py, however, scans TWO template trees
    (templates/agents/*.md AND templates/scripts/commit_guardian/*.py — see
    that module's own SCOPE docstring) and looks each one up in the same
    manifest. Every commit-guardian template is therefore permanently
    "not in manifest" and can never be drift-checked, no matter how many
    times build.py runs. See docs/acceptance-criteria/build_pipeline/
    BP-100-reliable-builds/BP-100k-1.yaml.
ARCHITECTURE / EXERCISE STRATEGY:
    - Direction A (template_hashes) does not depend on target_root/config
      (see write_build_manifest's own signature — those two params only
      gate the separate output_mappings/Direction-B section). So these
      tests build a MINIMAL synthetic package root containing REAL, copied
      (not paraphrased) templates/agents/ and templates/scripts/
      commit_guardian/ trees, then call the REAL, unmodified
      ``build_helpers.write_build_manifest()`` imported straight from this
      worktree's own scripts/ directory (the exact module python-coder will
      edit) — never a re-implementation of its logic.
    - The drift-gate tests then deploy a REAL, byte-identical copy of
      templates/scripts/commit_guardian/check_build_drift.py (plus its
      sibling _resolve_root.py) into a synthesized deployed layout and
      invoke it as a subprocess exactly as pre-commit does — the same
      pattern proven in unit_tests/commit_guardian/
      test_ge_118b_drift_manifest_resolution.py. This satisfies the
      it_requirements constraint: "Verify behaviorally — run the build,
      then execute the template-drift gate against a real staged template
      outside the agent-template family and assert the gate emits a
      match/drift verdict rather than an absent-from-manifest notice; do
      not grep the manifest writer's source."
    - test_manifest_coverage_equals_the_build_copy_set derives the expected
      key set directly by walking the same two source directories the drift
      gate scans, rather than hand-listing file names or a fixed count —
      count-agnostic, so it stays meaningful however many templates exist
      in either family.

RED BASELINE (captured 2026-08-18, before any production-code change):
    - test_manifest_records_a_fingerprint_for_a_non_agent_template_family
      FAILS: the manifest key for the picked commit-guardian template is
      absent (write_build_manifest only scans templates/agents/).
    - test_drift_gate_emits_match_then_drift_for_that_template FAILS on
      both legs: the "match" leg fails because check_build_drift.py prints
      "... not in manifest ..." for the unmodified template instead of
      staying silent; the "drift" leg fails because the mutated copy is
      STILL reported as absent (exit 0) instead of BLOCKED (exit 1).
    - test_gate_never_reports_a_managed_template_as_absent_from_manifest
      FAILS: "not in manifest" is present in stderr.
    - test_manifest_coverage_equals_the_build_copy_set FAILS: the manifest's
      recorded key set is a strict subset of the expected set (missing
      every commit-guardian template key).
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

# ---------------------------------------------------------------------------
# Path setup — import the REAL, in-place build_helpers.py (the module under
# review) directly, exactly as build.py does. Direction A (template_hashes)
# never touches target_root/config, so no synthetic scripts/ copy is needed
# for these tests (only templates/ is synthesized as the data under test).
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_TEMPLATES_DIR = _REPO_ROOT / "templates"
_CG_TEMPLATES_SRC = _TEMPLATES_DIR / "scripts" / "commit_guardian"

# Top-level manifest keys that are METADATA, not template-path -> hash entries.
# The manifest is a flat dict of template keys plus a few reserved names, so a
# coverage comparison has to subtract the reserved ones or it counts metadata as
# a missing template. Keep this in step with write_build_manifest().
# Top-level manifest keys that are METADATA, not template-hash entries. Any new
# key added to the manifest by write_build_manifest() must be listed here or it
# is mistaken for a recorded template path.
_MANIFEST_METADATA_KEYS = frozenset(
    {
        "output_mappings",
        "package_root",
        "output_mappings_error",
        "output_mappings_skipped_sections",
    }
)
_RESOLVE_ROOT_SRC = _CG_TEMPLATES_SRC / "_resolve_root.py"
_CHECK_BUILD_DRIFT_SRC = _CG_TEMPLATES_SRC / "check_build_drift.py"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import build_helpers  # noqa: E402 — after sys.path setup; the real module under review

_SUBPROCESS_TIMEOUT_SECONDS = 15


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _build_synthetic_pkg(workspace: Path) -> Path:
    """Build a minimal synthetic package root under ``workspace``.

    Copies the REAL ``templates/agents/`` and
    ``templates/scripts/commit_guardian/`` trees (byte-for-byte, via
    ``shutil.copytree`` — never a paraphrase) into
    ``<workspace>/leafcutter-ai/templates/...``, mirroring the relative
    depth ``write_build_manifest()`` assumes (``package_root.parent`` is the
    repo root used to form manifest keys).

    Args:
        workspace: Temp directory to build the synthetic layout inside.

    Returns:
        Absolute path to the synthetic package root
        (``<workspace>/leafcutter-ai``).
    """
    pkg_root = workspace / "leafcutter-ai"
    shutil.copytree(
        _TEMPLATES_DIR / "agents",
        pkg_root / "templates" / "agents",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    shutil.copytree(
        _CG_TEMPLATES_SRC,
        pkg_root / "templates" / "scripts" / "commit_guardian",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    return pkg_root


def _pick_non_agent_template(pkg_root: Path) -> Path:
    """Return a deterministic, real commit-guardian template file.

    Picks the alphabetically-first non-underscore-prefixed ``.py`` file
    under the synthesized ``templates/scripts/commit_guardian/`` tree —
    derived from whatever is actually on disk rather than a hardcoded
    filename, so the test keeps working if commit-guardian templates are
    renamed or reorganised.

    Args:
        pkg_root: Synthetic package root built by ``_build_synthetic_pkg``.

    Returns:
        Absolute path to the picked template file.
    """
    cg_dir = pkg_root / "templates" / "scripts" / "commit_guardian"
    candidates = sorted(
        f for f in cg_dir.glob("*.py") if not f.name.startswith("_")
    )
    return candidates[0]


def _deploy_hook(base: Path, hook_src: Path) -> Path:
    """Copy the real check_build_drift.py into a synthesized deployed layout.

    Mirrors the real deployed relative depth
    (``<base>/.leafcutter/scripts/commit_guardian/check_build_drift.py``) —
    the exact pattern proven in
    unit_tests/commit_guardian/test_ge_118b_drift_manifest_resolution.py.
    ``_resolve_root.py`` is copied alongside so the hook's import resolves
    without extra sys.path plumbing.

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


# ---------------------------------------------------------------------------
# AC-1 / AC-3 (BP-100k-1): manifest yields a fingerprint for a non-agent
# template family, looked up by its repo-relative template path.
# ---------------------------------------------------------------------------


class TestManifestRecordsNonAgentTemplateFingerprint(unittest.TestCase):
    """AC-1: the manifest yields a recorded fingerprint for a commit-guardian
    hook template (a family other than templates/agents/*.md)."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.pkg_root = _build_synthetic_pkg(self.workspace)

    def test_manifest_records_a_fingerprint_for_a_non_agent_template_family(self) -> None:
        # covers: BP-100k-1
        target_tpl = _pick_non_agent_template(self.pkg_root)

        build_helpers.write_build_manifest(self.pkg_root, dry_run=False)

        manifest_path = self.pkg_root / ".build_manifest.json"
        self.assertTrue(
            manifest_path.exists(),
            f"write_build_manifest() did not write a manifest at {manifest_path}",
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        # Keys are relative to the manifest's own directory. This test calls
        # write_build_manifest(pkg_root) with no target_root, so the manifest
        # falls back to pkg_root and that is the base (BP-100k-3).
        repo_root = self.pkg_root
        expected_key = target_tpl.relative_to(repo_root).as_posix()

        self.assertIn(
            expected_key,
            manifest,
            msg=(
                f"write_build_manifest() did not record a fingerprint for "
                f"{expected_key!r} (a commit-guardian hook template — a "
                "template family other than templates/agents/*.md). Today's "
                "implementation only hashes templates/agents/*.md, so every "
                "other template family the build copies is invisible to the "
                "manifest (BP-100k-1). Manifest keys sample: "
                f"{sorted(k for k in manifest if k != 'output_mappings')[:5]}"
            ),
        )
        expected_hash = hashlib.sha256(target_tpl.read_bytes()).hexdigest()
        self.assertEqual(
            manifest.get(expected_key),
            expected_hash,
            msg=f"Recorded fingerprint for {expected_key!r} does not match its real content hash.",
        )


# ---------------------------------------------------------------------------
# AC-2 (BP-100k-1): the executed template-drift gate emits match-then-drift
# for that template, never absent-from-manifest.
# ---------------------------------------------------------------------------


class TestDriftGateEmitsMatchThenDrift(unittest.TestCase):
    """AC-2: check_build_drift.py must compare, not skip, the non-agent template."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.pkg_root = _build_synthetic_pkg(self.workspace)

    def test_drift_gate_emits_match_then_drift_for_that_template(self) -> None:
        # covers: BP-100k-1
        target_tpl = _pick_non_agent_template(self.pkg_root)
        original_content = target_tpl.read_bytes()

        build_helpers.write_build_manifest(self.pkg_root, dry_run=False)
        hook_path = _deploy_hook(self.workspace, _CHECK_BUILD_DRIFT_SRC)

        # Keys are relative to the manifest's own directory. This test calls
        # write_build_manifest(pkg_root) with no target_root, so the manifest
        # falls back to pkg_root and that is the base (BP-100k-3).
        repo_root = self.pkg_root
        key = target_tpl.relative_to(repo_root).as_posix()

        # --- Leg 1: unmodified staged copy must yield a MATCH verdict ---
        result_match = _run_hook(hook_path, self.workspace)
        self.assertEqual(
            0,
            result_match.returncode,
            msg=(
                "An unmodified, correctly-covered template must not block the "
                f"commit. stdout:\n{result_match.stdout}\nstderr:\n{result_match.stderr}"
            ),
        )
        self.assertNotIn(
            f"{key} not in manifest",
            result_match.stderr,
            msg=(
                "check_build_drift.py reported the non-agent template as absent "
                "from the manifest instead of yielding a match verdict — the "
                f"exact BP-100k-1 symptom. stderr:\n{result_match.stderr}"
            ),
        )

        # --- Leg 2: mutate the staged copy — must now yield a DRIFT verdict ---
        target_tpl.write_bytes(original_content + b"\n# BP-100k-1 drift probe\n")
        result_drift = _run_hook(hook_path, self.workspace)

        self.assertEqual(
            1,
            result_drift.returncode,
            msg=(
                "check_build_drift.py must detect drift in a mutated non-agent "
                "template once it is properly covered by the manifest. "
                f"stdout:\n{result_drift.stdout}\nstderr:\n{result_drift.stderr}"
            ),
        )
        combined = result_drift.stdout + result_drift.stderr
        self.assertIn("BLOCKED", combined, msg=f"No BLOCKED message printed. Output:\n{combined}")
        self.assertIn(key, combined, msg=f"BLOCKED output does not name {key!r}. Output:\n{combined}")


# ---------------------------------------------------------------------------
# AC-3 second half (BP-100k-1): the not-in-manifest branch must never be
# taken for any template family the build copies.
# ---------------------------------------------------------------------------


class TestGateNeverReportsManagedTemplateAbsent(unittest.TestCase):
    """AC-3: no managed template family may ever be reported as absent."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.pkg_root = _build_synthetic_pkg(self.workspace)

    def test_gate_never_reports_a_managed_template_as_absent_from_manifest(self) -> None:
        # covers: BP-100k-1
        build_helpers.write_build_manifest(self.pkg_root, dry_run=False)
        hook_path = _deploy_hook(self.workspace, _CHECK_BUILD_DRIFT_SRC)

        result = _run_hook(hook_path, self.workspace)

        self.assertNotIn(
            "not in manifest",
            result.stderr,
            msg=(
                "check_build_drift.py emitted an 'absent from manifest' notice "
                "for at least one managed template family, even though every "
                "template under templates/agents/ and "
                "templates/scripts/commit_guardian/ should be covered "
                f"(BP-100k-1). stderr:\n{result.stderr}"
            ),
        )


# ---------------------------------------------------------------------------
# AC-3 core (BP-100k-1): manifest template coverage equals the build's
# actual copy set — derived, not enumerated by hand.
# ---------------------------------------------------------------------------


class TestManifestCoverageEqualsBuildCopySet(unittest.TestCase):
    """AC-3: recorded key set == the real set of files the build copies."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.pkg_root = _build_synthetic_pkg(self.workspace)

    def test_manifest_coverage_equals_the_build_copy_set(self) -> None:
        # covers: BP-100k-1
        build_helpers.write_build_manifest(self.pkg_root, dry_run=False)

        manifest_path = self.pkg_root / ".build_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        recorded_keys = {k for k in manifest if k not in _MANIFEST_METADATA_KEYS}

        # Keys are relative to the manifest's own directory. This test calls
        # write_build_manifest(pkg_root) with no target_root, so the manifest
        # falls back to pkg_root and that is the base (BP-100k-3).
        repo_root = self.pkg_root
        expected_keys: set[str] = set()
        for f in (self.pkg_root / "templates" / "agents").rglob("*.md"):
            expected_keys.add(f.relative_to(repo_root).as_posix())
        for f in (self.pkg_root / "templates" / "scripts" / "commit_guardian").rglob("*.py"):
            if "__pycache__" in f.parts:
                continue
            expected_keys.add(f.relative_to(repo_root).as_posix())

        self.assertTrue(expected_keys, "setup bug: no source template files found to compare against")

        missing = expected_keys - recorded_keys
        extra = recorded_keys - expected_keys
        self.assertEqual(
            expected_keys,
            recorded_keys,
            msg=(
                "The manifest's recorded template key set does not equal the "
                "set of template files the build actually copies (agents/*.md "
                "+ commit-guardian templates). "
                f"Missing from manifest: {sorted(missing)[:10]}. "
                f"Unexpected extra keys: {sorted(extra)[:10]}. "
                "Coverage must be derived from the same inventory the build "
                "copies, not a second hardcoded list (BP-100k-1)."
            ),
        )


if __name__ == "__main__":
    unittest.main()
