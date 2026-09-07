"""
MODULE: unit_tests/commit_guardian/test_bp_100n_1.py
GOAL: BP-100n-1 — a deployed output (or source template) the build recorded
    as having been written, but which is absent from disk, must be named,
    counted, and must fail the run. Deletion is the most complete form of
    drift there is, and today it is the only kind the gate ignores.
BUSINESS CONTEXT: In check_output_drift.py's ``_scan_output_files()``, the
    comparison loop iterates over ``output_files`` — the list returned by
    ``_collect_output_files()``, itself built from ``Path.rglob("*")`` over
    the scan directories. A file that has been deleted from disk simply
    never appears in that rglob result, so a manifest-recorded key whose
    file was deleted is not merely mis-handled by the existing
    ``if not out_path.exists(): ... continue`` branch inside the loop — it
    never reaches the loop body at all. It is not counted verified, not
    counted uncomparable, not counted as a gap, and has no effect on exit
    status. check_build_drift.py's ``_scan_templates()`` has the identical
    structure on the template side. Deleting a deployed artifact (or a
    hashed template) therefore passes both gates silently.
    See docs/acceptance-criteria/build_pipeline/BP-100-reliable-builds/
    BP-100n-1.yaml.

OUTPUT + EXIT-CODE CONTRACT SPECIFIED BY THIS TEST FILE (the target for
    python-coder — mirrors the existing BP-100k-3 contract style in
    test_bp_100k_3.py): a manifest-recorded artifact (template OR deployed
    output) whose file is absent from disk must produce exactly one line:

      "UNCOMPARABLE: MISSING <key> reason=recorded but not found on disk"

    counted in a NEW, fifth field appended to the existing RESULT summary
    line (never folded into ``uncomparable``, which BP-100k-3 already
    defines as gaps + declared exemptions — a deliberately-declared
    exemption and a deleted, still-recorded artifact demand different
    remedies and must stay distinguishable):

      "<gate-name>: RESULT verified=<N> uncomparable=<M> exempt=<E> "
      "gaps=<G> drifted=<D> missing=<X>"

    A non-zero ``missing`` count must never be counted in ``verified`` and
    must never let the run exit 0 (clean); both check_build_drift.py and
    check_output_drift.py must emit this identical verdict shape (AC's own
    "the missing-artifact verdict must be shared" constraint) — a
    ``drift_gate_missing_output_verdict`` behaviour honoured by one gate and
    ignored by its sibling would reproduce the ambiguity BP-100k-3 removed.

ARCHITECTURE / EXERCISE STRATEGY: every test below EXECUTES the real,
    unmodified-by-this-file gate module(s) as a subprocess against a
    synthesized, self-hosted deployed layout (consumer layout: package_root
    == workspace/leafcutter-ai) — the same pattern proven in
    test_bp_100k_3.py — never a grep of the gate's source. Each fixture
    registers TWO artifacts (one that stays present throughout, one that
    gets deleted) so the pre-existing, UNRELATED "verified == 0" floor in
    ``check_output_drift()`` (a safety net for "compared nothing at all
    against a non-empty manifest") can never fire and be mistaken for the
    missing-artifact verdict this AC actually specifies — deleting the
    tracked artifact must leave the OTHER, still-present artifact verified,
    so any non-clean verdict this test observes is provably caused by the
    missing-artifact handling under test, not by that unrelated floor.

RED BASELINE (expected, captured before any production-code change): every
    test in this file is RED — no "UNCOMPARABLE: MISSING" line and no
    "missing=" RESULT field exist in the current implementation, which
    (per the BUSINESS CONTEXT above) silently omits a deleted, recorded
    artifact from the scan entirely and always exits as though it were not
    there.
"""

from __future__ import annotations

import hashlib
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

# "missing" is an OPTIONAL trailing group: absent today (the field does not
# exist yet), present once python-coder implements the contract specified in
# this file's module docstring.
_RESULT_LINE_RE = re.compile(
    r"(check-build-drift|check-output-drift):\s*RESULT\s+"
    r"verified=(\d+)\s+uncomparable=(\d+)\s+exempt=(\d+)\s+gaps=(\d+)\s+"
    r"drifted=(\d+)(?:\s+missing=(\d+))?",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Shared helpers (mirrors test_bp_100k_3.py's fixture idiom, duplicated
# rather than imported — small, self-contained fixtures per file is the
# established convention in this test suite; see test_bp_100k_3.py's own
# module docstring).
# ---------------------------------------------------------------------------


def _sha256_bytes(data: bytes) -> str:
    """Return the SHA-256 hex digest of raw bytes.

    Args:
        data: Raw bytes to hash.

    Returns:
        Lowercase hexadecimal SHA-256 digest string.
    """
    return hashlib.sha256(data).hexdigest()


def _build_synthetic_workspace(workspace: Path) -> Path:
    """Build a minimal synthetic consumer-install layout under ``workspace``.

    Mirrors the layout ``_resolve_manifest_path`` discovers in real consumer
    installs: ``<workspace>/leafcutter-ai`` is the package root (holds
    ``templates/`` and the manifest); deployed outputs live directly under
    ``<workspace>/.claude/...`` (repo-root == workspace).

    Args:
        workspace: Temp directory to build the synthetic layout inside.

    Returns:
        Absolute path to the synthetic package root
        (``<workspace>/leafcutter-ai``).
    """
    pkg_root = workspace / "leafcutter-ai"
    (pkg_root / "templates" / "agents").mkdir(parents=True)
    (pkg_root / "templates" / "scripts" / "commit_guardian").mkdir(parents=True)
    (workspace / ".claude" / "agents").mkdir(parents=True)
    return pkg_root


def _write_manifest(pkg_root: Path, template_hashes: dict, output_mappings: dict) -> None:
    """Write .build_manifest.json via the real JSON serializer.

    Args:
        pkg_root: Synthetic package root (``<workspace>/leafcutter-ai``). The
            manifest lands in its parent, alongside the deployed ``.claude/``
            tree, mirroring a real consumer install.
        template_hashes: Flat dict of manifest-key -> sha256 hex string
            (Direction A — check_build_drift.py).
        output_mappings: The output_mappings section (Direction B —
            check_output_drift.py).
    """
    import json

    manifest = dict(template_hashes)
    manifest["output_mappings"] = output_mappings
    manifest["package_root"] = pkg_root.name
    (pkg_root.parent / ".build_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )


def _deploy_commit_guardian_dir(workspace: Path) -> Path:
    """Copy the REAL, unmodified templates/scripts/commit_guardian/ tree.

    Args:
        workspace: Temp directory to build the fake deployment inside.

    Returns:
        Absolute path to the deployed commit_guardian directory.
    """
    deployed_dir = workspace / ".leafcutter" / "scripts" / "commit_guardian"
    shutil.copytree(
        _CG_TEMPLATES_SRC, deployed_dir, ignore=shutil.ignore_patterns("__pycache__")
    )
    return deployed_dir


def _run_hook(hook_path: Path, cwd: Path) -> subprocess.CompletedProcess:
    """Execute a deployed gate module as a subprocess, exactly as pre-commit does.

    Args:
        hook_path: Absolute path to the (copied) gate module to execute.
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


def _make_output_drift_scenario(workspace: Path) -> dict:
    """Build a two-artifact output-drift (Direction B) scenario.

    One artifact (``tracked_output.md``) is the one tests delete; the other
    (``other_output.md``) stays present throughout so ``verified`` never
    drops to exactly zero after the deletion — which would otherwise
    trigger the PRE-EXISTING, unrelated "compared 0 artifacts against a
    non-empty manifest" floor in ``check_output_drift()`` and make a test
    pass for the wrong reason.

    Args:
        workspace: Temp directory to build the synthetic layout inside.

    Returns:
        Dict with pkg_root, both artifacts' paths/keys, and their content.
    """
    pkg_root = _build_synthetic_workspace(workspace)
    agents_dir = workspace / ".claude" / "agents"

    tracked_content = b"# tracked deployed output\nwill be deleted\n"
    tracked_path = agents_dir / "tracked_output.md"
    tracked_path.write_bytes(tracked_content)
    tracked_key = tracked_path.relative_to(workspace).as_posix()

    other_content = b"# other deployed output\nstays present throughout\n"
    other_path = agents_dir / "other_output.md"
    other_path.write_bytes(other_content)
    other_key = other_path.relative_to(workspace).as_posix()

    _write_manifest(
        pkg_root,
        {},
        {
            tracked_key: {
                "template": "templates/agents/tracked_output.md",
                "expected_output_hash": _sha256_bytes(tracked_content),
            },
            other_key: {
                "template": "templates/agents/other_output.md",
                "expected_output_hash": _sha256_bytes(other_content),
            },
        },
    )

    return {
        "pkg_root": pkg_root,
        "tracked_path": tracked_path,
        "tracked_key": tracked_key,
        "tracked_content": tracked_content,
        "other_path": other_path,
        "other_key": other_key,
    }


def _make_combined_missing_scenario(workspace: Path) -> dict:
    """Build a scenario with BOTH a Direction A (template) and a Direction B
    (deployed output) artifact, each paired with an always-present sibling.

    Used only by the shared-verdict test, which needs both gates to have a
    real deleted, recorded artifact to react to.

    Args:
        workspace: Temp directory to build the synthetic layout inside.

    Returns:
        Dict with pkg_root and both families' paths/keys.
    """
    pkg_root = _build_synthetic_workspace(workspace)

    tpl_content = b"# tracked template\nwill be deleted for build-drift\n"
    tpl_path = pkg_root / "templates" / "agents" / "tracked_template.md"
    tpl_path.write_bytes(tpl_content)
    tpl_key = tpl_path.relative_to(workspace).as_posix()

    other_tpl_content = b"# other template\nstays present\n"
    other_tpl_path = pkg_root / "templates" / "agents" / "other_template.md"
    other_tpl_path.write_bytes(other_tpl_content)
    other_tpl_key = other_tpl_path.relative_to(workspace).as_posix()

    agents_dir = workspace / ".claude" / "agents"
    out_content = b"# tracked deployed output\nwill be deleted for output-drift\n"
    out_path = agents_dir / "tracked_output.md"
    out_path.write_bytes(out_content)
    out_key = out_path.relative_to(workspace).as_posix()

    other_out_content = b"# other deployed output\nstays present\n"
    other_out_path = agents_dir / "other_output.md"
    other_out_path.write_bytes(other_out_content)
    other_out_key = other_out_path.relative_to(workspace).as_posix()

    _write_manifest(
        pkg_root,
        {
            tpl_key: _sha256_bytes(tpl_content),
            other_tpl_key: _sha256_bytes(other_tpl_content),
        },
        {
            out_key: {
                "template": "templates/agents/tracked_output.md",
                "expected_output_hash": _sha256_bytes(out_content),
            },
            other_out_key: {
                "template": "templates/agents/other_output.md",
                "expected_output_hash": _sha256_bytes(other_out_content),
            },
        },
    )

    return {
        "pkg_root": pkg_root,
        "tpl_path": tpl_path,
        "tpl_key": tpl_key,
        "out_path": out_path,
        "out_key": out_key,
    }


# ---------------------------------------------------------------------------
# AC-1: deleted recorded output is named and fails the run.
# ---------------------------------------------------------------------------


class TestDeletedRecordedOutputIsNamedAndFailsTheRun(unittest.TestCase):
    """A recorded-but-deleted output is named and terminates with a
    non-zero exit status."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.scenario = _make_output_drift_scenario(self.workspace)
        self.hook = _deploy_commit_guardian_dir(self.workspace) / "check_output_drift.py"

    def test_deleted_recorded_output_is_named_and_fails_the_run(self) -> None:
        # covers: BP-100n-1
        key = self.scenario["tracked_key"]
        self.scenario["tracked_path"].unlink()

        result = _run_hook(self.hook, self.workspace)
        combined = result.stdout + result.stderr

        self.assertIn(
            f"UNCOMPARABLE: MISSING {key}",
            combined,
            msg=(
                f"Deleting the recorded output {key} produced no "
                "'UNCOMPARABLE: MISSING' line naming it — the gate does not "
                f"currently visit a manifest-recorded key whose file was "
                f"deleted at all (BP-100n-1). Output:\n{combined}"
            ),
        )
        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                f"Deleting the recorded output {key} did not fail the run. "
                f"Output:\n{combined}"
            ),
        )


# ---------------------------------------------------------------------------
# AC-2: missing output is counted in the run summary as its own figure.
# ---------------------------------------------------------------------------


class TestMissingOutputIsCountedInTheRunSummary(unittest.TestCase):
    """The run summary reports a non-zero, distinct count for
    recorded-but-absent outputs."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.scenario = _make_output_drift_scenario(self.workspace)
        self.hook = _deploy_commit_guardian_dir(self.workspace) / "check_output_drift.py"

    def test_missing_output_is_counted_in_the_run_summary(self) -> None:
        # covers: BP-100n-1
        self.scenario["tracked_path"].unlink()

        result = _run_hook(self.hook, self.workspace)
        combined = result.stdout + result.stderr

        match = _RESULT_LINE_RE.search(combined)
        self.assertIsNotNone(
            match,
            msg=f"No RESULT summary line found at all. Output:\n{combined}",
        )
        missing_group = match.group(6)
        self.assertIsNotNone(
            missing_group,
            msg=(
                "The RESULT summary line has no 'missing=<X>' field — a "
                "recorded-but-absent output is not counted as its own "
                f"reported condition (BP-100n-1). Output:\n{combined}"
            ),
        )
        self.assertEqual(
            1,
            int(missing_group),
            msg=f"Expected missing=1. Output:\n{combined}",
        )


# ---------------------------------------------------------------------------
# AC-3: missing output is never credited among verified outputs.
# ---------------------------------------------------------------------------


class TestMissingOutputIsNotCountedAmongVerifiedOutputs(unittest.TestCase):
    """The verified count drops by exactly one when the tracked output is
    deleted, and the deletion is independently confirmed via the missing
    count — a coincidental drop from an unrelated cause would not also
    produce missing=1."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.scenario = _make_output_drift_scenario(self.workspace)
        self.hook = _deploy_commit_guardian_dir(self.workspace) / "check_output_drift.py"

    def test_missing_output_is_not_counted_among_verified_outputs(self) -> None:
        # covers: BP-100n-1
        baseline = _run_hook(self.hook, self.workspace)
        baseline_combined = baseline.stdout + baseline.stderr
        baseline_match = _RESULT_LINE_RE.search(baseline_combined)
        self.assertIsNotNone(
            baseline_match,
            msg=f"No RESULT summary line in the baseline run. Output:\n{baseline_combined}",
        )
        baseline_verified = int(baseline_match.group(2))

        self.scenario["tracked_path"].unlink()
        after = _run_hook(self.hook, self.workspace)
        after_combined = after.stdout + after.stderr
        after_match = _RESULT_LINE_RE.search(after_combined)
        self.assertIsNotNone(
            after_match,
            msg=f"No RESULT summary line after deletion. Output:\n{after_combined}",
        )
        after_verified = int(after_match.group(2))

        self.assertEqual(
            baseline_verified - 1,
            after_verified,
            msg=(
                f"verified dropped from {baseline_verified} to "
                f"{after_verified} after deleting one of two tracked "
                "outputs — expected exactly a drop of one. "
                f"Output:\n{after_combined}"
            ),
        )
        after_missing = after_match.group(6)
        self.assertEqual(
            "1",
            after_missing,
            msg=(
                "The verified-count drop must be attributable to the "
                "missing-output verdict, not an unrelated cause — expected "
                f"missing=1 after deletion. Output:\n{after_combined}"
            ),
        )


# ---------------------------------------------------------------------------
# AC-4: a run with a missing output is not described as clean.
# ---------------------------------------------------------------------------


class TestRunWithAMissingOutputIsNotDescribedAsClean(unittest.TestCase):
    """A run containing a recorded-but-absent output must not exit 0, and
    must exit differently from the same tree with every recorded output
    present."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.scenario = _make_output_drift_scenario(self.workspace)
        self.hook = _deploy_commit_guardian_dir(self.workspace) / "check_output_drift.py"

    def test_run_with_a_missing_output_is_not_described_as_clean(self) -> None:
        # covers: BP-100n-1
        baseline = _run_hook(self.hook, self.workspace)
        self.assertEqual(
            0,
            baseline.returncode,
            msg=(
                "setup bug: the untouched, fully-present baseline must "
                f"pass cleanly. stdout:\n{baseline.stdout}\n"
                f"stderr:\n{baseline.stderr}"
            ),
        )

        self.scenario["tracked_path"].unlink()
        after = _run_hook(self.hook, self.workspace)
        combined = after.stdout + after.stderr

        self.assertNotEqual(
            0,
            after.returncode,
            msg=(
                "A run containing a recorded-but-absent output exited 0 "
                f"(clean). Output:\n{combined}"
            ),
        )
        self.assertNotEqual(
            baseline.returncode,
            after.returncode,
            msg=(
                "The exit status of a run with a missing output must "
                "differ from the exit status of a run where every "
                f"recorded output is present. baseline={baseline.returncode} "
                f"after={after.returncode}"
            ),
        )


# ---------------------------------------------------------------------------
# AC-5: restoring the output unchanged returns the run to passing.
# ---------------------------------------------------------------------------


class TestRestoringTheOutputUnchangedReturnsTheRunToPassing(unittest.TestCase):
    """After the deleted output is restored byte-for-byte, the gate reports
    a match and exits 0 — the new verdict raises no lasting false alarm."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.scenario = _make_output_drift_scenario(self.workspace)
        self.hook = _deploy_commit_guardian_dir(self.workspace) / "check_output_drift.py"

    def test_restoring_the_output_unchanged_returns_the_run_to_passing(self) -> None:
        # covers: BP-100n-1
        tracked_path = self.scenario["tracked_path"]
        original_content = self.scenario["tracked_content"]

        tracked_path.unlink()
        deleted_result = _run_hook(self.hook, self.workspace)
        self.assertNotEqual(
            0,
            deleted_result.returncode,
            msg=(
                "Precondition for this restore test: deleting the tracked "
                "output must fail the run (BP-100n-1) so that restoring it "
                "next actually proves the new verdict clears itself rather "
                "than never having fired in the first place. "
                f"Output:\n{deleted_result.stdout + deleted_result.stderr}"
            ),
        )

        tracked_path.write_bytes(original_content)
        restored_result = _run_hook(self.hook, self.workspace)
        combined = restored_result.stdout + restored_result.stderr

        self.assertEqual(
            0,
            restored_result.returncode,
            msg=(
                "Restoring the deleted output byte-for-byte did not return "
                f"the run to passing. Output:\n{combined}"
            ),
        )
        self.assertNotIn(
            "UNCOMPARABLE: MISSING",
            combined,
            msg=(
                "The restored output is still reported as missing. "
                f"Output:\n{combined}"
            ),
        )


# ---------------------------------------------------------------------------
# AC-6: both drift gates emit the same missing-artifact verdict.
# ---------------------------------------------------------------------------


class TestBothGatesEmitTheSameMissingArtifactVerdict(unittest.TestCase):
    """check_build_drift.py (Direction A) and check_output_drift.py
    (Direction B), each facing their own deleted, recorded artifact, must
    report it with the identical 'UNCOMPARABLE: MISSING' verdict — neither
    tolerates an absence the other reports."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.scenario = _make_combined_missing_scenario(self.workspace)
        deployed_dir = _deploy_commit_guardian_dir(self.workspace)
        self.build_hook = deployed_dir / "check_build_drift.py"
        self.output_hook = deployed_dir / "check_output_drift.py"

    def test_both_gates_emit_the_same_missing_artifact_verdict(self) -> None:
        # covers: BP-100n-1
        self.scenario["tpl_path"].unlink()
        self.scenario["out_path"].unlink()

        build_result = _run_hook(self.build_hook, self.workspace)
        output_result = _run_hook(self.output_hook, self.workspace)
        build_combined = build_result.stdout + build_result.stderr
        output_combined = output_result.stdout + output_result.stderr

        self.assertIn(
            f"UNCOMPARABLE: MISSING {self.scenario['tpl_key']}",
            build_combined,
            msg=(
                "check-build-drift did not report its deleted, recorded "
                f"template as missing. Output:\n{build_combined}"
            ),
        )
        self.assertIn(
            f"UNCOMPARABLE: MISSING {self.scenario['out_key']}",
            output_combined,
            msg=(
                "check-output-drift did not report its deleted, recorded "
                f"output as missing. Output:\n{output_combined}"
            ),
        )
        self.assertNotEqual(
            0,
            build_result.returncode,
            msg=f"check-build-drift did not fail on a missing recorded artifact. Output:\n{build_combined}",
        )
        self.assertNotEqual(
            0,
            output_result.returncode,
            msg=f"check-output-drift did not fail on a missing recorded artifact. Output:\n{output_combined}",
        )


if __name__ == "__main__":
    unittest.main()
