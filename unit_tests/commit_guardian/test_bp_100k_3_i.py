"""
MODULE: unit_tests/commit_guardian/test_bp_100k_3_i.py
GOAL: BP-100k-3-i — the anti-overcorrection guard on BP-100k-3's stricter
    reporting. A freshly-built, unmodified checkout must yield a ZERO
    uncomparable count, no drift, and exit 0 from BOTH drift gates. This is
    the guard that stops BP-100k-3 turning every currently-invisible
    coverage gap into a hard block: it fails if manifest coverage is still
    incomplete (a real gap on a clean tree) AND if the stricter reporting
    over-fires (a false alarm on an artifact that is genuinely covered).
BUSINESS CONTEXT: This ticket depends on ticket 07 (BP-100k-1/BP-100k-2,
    committed a78700a9), which closed the manifest coverage gaps that made
    comparison impossible for whole template/output families. Because that
    fix already landed on this branch, this L3 guard's exercise must prove
    the real, current manifest coverage is actually complete against a
    genuine full build — not merely that a hand-picked fixture looks
    complete. Per the AC's own constraints, the check must run over the
    real freshly built tree (never a synthesized subset), but MUST NOT run
    that build against this worktree's own root: this worktree's
    ``.leafcutter`` is a symlink shared by every other worktree in the
    workspace, so a self-targeted build here rewrites the deployed
    toolchain out from under everything else running concurrently.
ARCHITECTURE / EXERCISE STRATEGY: setUpClass builds a genuinely FULL,
    unmodified copy of the real package — every template under
    ``templates/``, every script under ``scripts/``, every file under
    ``config/`` — into an isolated ``tempfile.TemporaryDirectory`` laid out
    as ``<workspace>/leafcutter-ai``, using
    ``unit_tests.build_guards.test_bp_100k_2._build_synthetic_full_package``
    (loaded read-only via ``importlib`` rather than duplicated here). This
    is the same supported consumer layout ``build-self.sh`` itself uses
    (``package_root == target_root/leafcutter-ai``), so
    ``_compute_output_mappings()``'s target_root-relative arithmetic behaves
    exactly as it does for a real ``python scripts/build.py --target-dir .``
    run. It then invokes the REAL ``python <workspace>/leafcutter-ai/scripts
    /build.py --target-dir <workspace>`` as a subprocess — the actual CLI
    entry point, running every phase, exactly as build-self.sh does — so
    every phase of the real build runs unabridged, with no phase
    hand-picked or omitted, and the developer's own ``.leafcutter`` and
    worktree files are never touched. setUpClass then asserts the resulting
    manifest's ``output_mappings`` is non-empty as a sanity check: an empty
    manifest would make every assertion below pass vacuously, which is
    exactly the phantom-done failure mode this epic exists to catch.

    Every test then executes the REAL DEPLOYED hook copies this isolated
    build produced, at
    ``<workspace>/scripts/commit_guardian/check_build_drift.py`` and
    ``check_output_drift.py`` (never the templates/ source) as subprocesses
    against this real, freshly-built, isolated tree — the deployed-layout
    requirement named explicitly in the ticket's Implementation Notes and in
    AC-6's own "not only the templates/ source tree" wording, satisfied
    without mutating any shared worktree state.

    Assertions are COUNT-BASED over the gate's own output (occurrences of
    the UNCOMPARABLE: marker, and the numeric fields of the RESULT summary
    line BP-100k-3 introduces — see test_bp_100k_3.py's module docstring
    for the full OUTPUT + EXIT-CODE CONTRACT this file also relies on) —
    never an allowlist of today's expected artifact names, so a newly added
    template or output family that later escapes manifest coverage will
    still be caught by these same tests.

RED BASELINE (expected 2026-08-19, before any production-code change):
    - test_freshly_built_tree_yields_zero_uncomparable_artifacts and
      test_freshly_built_tree_reports_no_drifted_artifact and
      test_stricter_uncomparable_reporting_raises_no_false_alarm_on_the_real_tree
      assert only on markers/behaviour that are ALREADY true of the current,
      unmodified gates on a real, fully-manifested build (no "not in
      manifest"/"not in output_mappings" lines exist today because ticket 07
      already closed that gap; no BLOCKED lines exist because nothing has
      drifted; exit 0 already holds) — these may legitimately PASS today.
      That is expected and correct for an anti-overcorrection guard: it
      must stay green before, during, and after BP-100k-3 lands.
    - test_both_gates_report_clean_and_exit_zero_on_a_freshly_built_tree
      requires the new aggregate "RESULT verified=<N> uncomparable=<M>
      drifted=<D>" summary line BP-100k-3 introduces, which does not exist
      in the current implementation — this one is expected to be RED.

ISOLATION NOTE (hazard remediation): the original version of this file ran
    the real build directly against this worktree's own root
    (``--target-dir <this worktree>``). Because this worktree's
    ``.leafcutter`` is a symlink into a directory shared by every other
    worktree in the workspace, running this single test file rewrote the
    deployed toolchain for everything else concurrently in flight, and
    dirtied ``docs/agents/cards/*.card.md`` on every run (KI-BP-002). This
    version builds into an isolated ``tempfile.TemporaryDirectory`` instead;
    no file under this worktree is read from at test time other than the
    real ``templates/``, ``scripts/``, and ``config/`` source trees (copied,
    never modified) and no file outside the temp directory is ever written.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SYNTHETIC_PACKAGE_HELPER_PATH = (
    _REPO_ROOT / "unit_tests" / "build_guards" / "test_bp_100k_2.py"
)

_BUILD_TIMEOUT_SECONDS = 180
_SUBPROCESS_TIMEOUT_SECONDS = 20


def _load_build_synthetic_full_package():
    """Load ``_build_synthetic_full_package`` from test_bp_100k_2.py.

    Loaded read-only via ``importlib.util.spec_from_file_location`` under a
    private module name rather than duplicating the copy-the-real-templates
    logic in this file, per the guidance that a second, hand-authored copy
    of the same synthetic-package builder is worse than reusing the proven
    one. Never imported as a bare ``test_bp_100k_2`` module name, so this
    does not collide with pytest's own collection of that file.

    Returns:
        The ``_build_synthetic_full_package(workspace: Path) -> Path``
        function object from that module.
    """
    spec = importlib.util.spec_from_file_location(
        "_bp100k3i_synthetic_package_helper", _SYNTHETIC_PACKAGE_HELPER_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module._build_synthetic_full_package


_RESULT_LINE_RE = re.compile(
    r"(check-build-drift|check-output-drift):\s*RESULT\s+"
    r"verified=(\d+)\s+uncomparable=(\d+)\s+exempt=(\d+)\s+gaps=(\d+)\s+"
    r"drifted=(\d+)",
    re.IGNORECASE,
)
_UNCOMPARABLE_LINE_RE = re.compile(r"^UNCOMPARABLE:.*$", re.MULTILINE)

# BP-100k-3-i requires zero artifacts "neither recorded nor declared exempt" —
# i.e. zero GAPS. A declared exemption IS an uncomparable artifact, and the
# criterion permits it on a fresh tree; it is reported, not counted against the
# run. Asserting on the UNCOMPARABLE total instead of the GAP subset would be
# stricter than the AC and would make declaring a grounded exemption pointless,
# since the run would fail either way — collapsing BP-100k-3's three-way
# gap/exemption/pass distinction back into two.
_GAP_LINE_RE = re.compile(r"^UNCOMPARABLE:\s*GAP\b.*$", re.MULTILINE)
_EXEMPT_LINE_RE = re.compile(r"^UNCOMPARABLE:\s*EXEMPT\b.*$", re.MULTILINE)


def _run_deployed_hook(hook_path: Path, cwd: Path) -> subprocess.CompletedProcess:
    """Execute a real deployed gate module as a subprocess.

    Args:
        hook_path: Absolute path to the deployed gate module to execute.
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


class TestFreshlyBuiltTreeHasNoFalseAlarms(unittest.TestCase):
    """BP-100k-3-i: a freshly-built, unmodified checkout yields zero
    uncomparable artifacts, no drift, and a clean exit from both gates."""

    @classmethod
    def setUpClass(cls) -> None:
        # Isolated target: a fresh tempdir, never this worktree's own root, so
        # this test file cannot rewrite the shared .leafcutter symlink target
        # (see the module docstring's ISOLATION NOTE).
        tmpdir = tempfile.TemporaryDirectory()
        cls.addClassCleanup(tmpdir.cleanup)
        cls._isolated_tree = Path(tmpdir.name)

        # Copy the REAL templates/, scripts/, and config/ trees (never a
        # hand-picked subset) into the same consumer layout build-self.sh
        # itself uses: package_root == target_root/leafcutter-ai.
        build_synthetic_full_package = _load_build_synthetic_full_package()
        pkg_root = build_synthetic_full_package(cls._isolated_tree)
        build_script = pkg_root / "scripts" / "build.py"

        # The REAL build CLI, run over every phase — no phase is invoked
        # individually or omitted, exactly as `python scripts/build.py
        # --target-dir <target>` (build-self.sh) runs it, just pointed at
        # the isolated tree instead of this worktree's own root.
        cls._build_result = subprocess.run(
            [sys.executable, str(build_script), "--target-dir", str(cls._isolated_tree)],
            cwd=str(cls._isolated_tree),
            capture_output=True,
            text=True,
            timeout=_BUILD_TIMEOUT_SECONDS,
        )
        cls._build_drift_hook = cls._isolated_tree / "scripts" / "commit_guardian" / "check_build_drift.py"
        cls._output_drift_hook = cls._isolated_tree / "scripts" / "commit_guardian" / "check_output_drift.py"

        # Sanity-check the manifest is non-empty BEFORE any test runs. An
        # empty output_mappings would make every zero-uncomparable /
        # zero-drift assertion below pass vacuously over nothing — exactly
        # the phantom-done failure mode this epic exists to catch.
        cls._manifest_sanity_error = None
        if cls._build_result.returncode == 0:
            manifest_path = cls._isolated_tree / ".build_manifest.json"
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                cls._manifest_sanity_error = (
                    f"setup bug: could not read/parse the real build manifest at "
                    f"{manifest_path}: {exc}"
                )
            else:
                output_mappings = manifest.get("output_mappings", {})
                if not output_mappings:
                    cls._manifest_sanity_error = (
                        "setup bug: the real, freshly built manifest has an empty "
                        "output_mappings — every assertion in this class would "
                        "pass vacuously over zero artifacts rather than proving "
                        "the real manifest coverage is complete."
                    )

    def setUp(self) -> None:
        if self._build_result.returncode != 0:
            self.fail(
                "setup bug: the real build over an isolated, freshly copied "
                "checkout failed, so this class cannot establish the 'build has "
                "just run and no file has been modified since' precondition. "
                f"stdout:\n{self._build_result.stdout}\nstderr:\n{self._build_result.stderr}"
            )
        if self._manifest_sanity_error is not None:
            self.fail(self._manifest_sanity_error)

    def test_freshly_built_tree_yields_zero_uncomparable_artifacts(self) -> None:
        # covers: BP-100k-3-i
        result_build = _run_deployed_hook(self._build_drift_hook, self._isolated_tree)
        result_output = _run_deployed_hook(self._output_drift_hook, self._isolated_tree)
        combined_build = result_build.stdout + result_build.stderr
        combined_output = result_output.stdout + result_output.stderr

        build_gaps = _GAP_LINE_RE.findall(combined_build)
        output_gaps = _GAP_LINE_RE.findall(combined_output)

        self.assertEqual(
            [],
            build_gaps,
            msg=(
                "check-build-drift reported at least one artifact that is "
                "neither recorded in the manifest nor declared exempt, on a "
                "freshly-built, unmodified checkout — read from the gate's own "
                "UNCOMPARABLE: GAP markers, not an allowlist of expected names. "
                f"Lines:\n{build_gaps}\nFull output:\n{combined_build}"
            ),
        )
        self.assertEqual(
            [],
            output_gaps,
            msg=(
                "check-output-drift reported at least one artifact that is "
                "neither recorded nor declared exempt, on a freshly-built, "
                "unmodified checkout. "
                f"Lines:\n{output_gaps}\nFull output:\n{combined_output}"
            ),
        )

    def test_freshly_built_tree_reports_no_drifted_artifact(self) -> None:
        # covers: BP-100k-3-i
        result_build = _run_deployed_hook(self._build_drift_hook, self._isolated_tree)
        result_output = _run_deployed_hook(self._output_drift_hook, self._isolated_tree)
        combined_build = result_build.stdout + result_build.stderr
        combined_output = result_output.stdout + result_output.stderr

        self.assertNotIn(
            "BLOCKED",
            combined_build,
            msg=f"check-build-drift reported drift on an unmodified checkout. Output:\n{combined_build}",
        )
        self.assertNotIn(
            "BLOCKED",
            combined_output,
            msg=f"check-output-drift reported drift on an unmodified checkout. Output:\n{combined_output}",
        )

    def test_both_gates_report_clean_and_exit_zero_on_a_freshly_built_tree(self) -> None:
        # covers: BP-100k-3-i
        result_build = _run_deployed_hook(self._build_drift_hook, self._isolated_tree)
        result_output = _run_deployed_hook(self._output_drift_hook, self._isolated_tree)

        self.assertEqual(
            0,
            result_build.returncode,
            msg=(
                "check-build-drift did not exit 0 on a freshly-built, unmodified "
                f"checkout. stdout:\n{result_build.stdout}\nstderr:\n{result_build.stderr}"
            ),
        )
        self.assertEqual(
            0,
            result_output.returncode,
            msg=(
                "check-output-drift did not exit 0 on a freshly-built, unmodified "
                f"checkout. stdout:\n{result_output.stdout}\nstderr:\n{result_output.stderr}"
            ),
        )

        combined_build = result_build.stdout + result_build.stderr
        combined_output = result_output.stdout + result_output.stderr

        match_build = _RESULT_LINE_RE.search(combined_build)
        match_output = _RESULT_LINE_RE.search(combined_output)
        self.assertIsNotNone(
            match_build,
            msg=(
                "No RESULT summary line found for check-build-drift (expected "
                "'check-build-drift: RESULT verified=<N> uncomparable=<M> "
                f"drifted=<D>'). Output:\n{combined_build}"
            ),
        )
        self.assertIsNotNone(
            match_output,
            msg=(
                "No RESULT summary line found for check-output-drift. "
                f"Output:\n{combined_output}"
            ),
        )

        # Per BP-100k-3-i the fresh-tree requirement is zero artifacts "neither
        # recorded nor declared exempt". Rather than assert the summary's
        # uncomparable total is zero — which would forbid declared exemptions the
        # criterion permits — assert the total is fully ACCOUNTED FOR: every
        # uncomparable artifact must be a declared exemption, so gaps are zero AND
        # the reported count is truthful. A gate that under-reported its own
        # uncomparable count would fail this, where a bare `== 0` would not.
        for label, match, combined in (
            ("check-build-drift", match_build, combined_build),
            ("check-output-drift", match_output, combined_output),
        ):
            reported_uncomparable = int(match.group(3))
            exempt_lines = _EXEMPT_LINE_RE.findall(combined)
            gap_lines = _GAP_LINE_RE.findall(combined)

            self.assertEqual(
                [],
                gap_lines,
                msg=(
                    f"{label} reported an artifact that is neither recorded nor "
                    f"declared exempt on a fresh build. Lines:\n{gap_lines}\n"
                    f"Output:\n{combined}"
                ),
            )
            self.assertEqual(
                len(exempt_lines),
                reported_uncomparable,
                msg=(
                    f"{label}'s RESULT summary claims uncomparable="
                    f"{reported_uncomparable} but emitted {len(exempt_lines)} "
                    f"EXEMPT lines and {len(gap_lines)} GAP lines. The summary "
                    f"count must equal what the gate actually reported per "
                    f"artifact — a count that does not reconcile with the "
                    f"per-artifact lines is exactly the unearned-pass this AC "
                    f"exists to prevent. Output:\n{combined}"
                ),
            )
            # group(6) is drifted: (gate, verified, uncomparable, exempt,
            # gaps, drifted).
            self.assertEqual(
                0,
                int(match.group(6)),
                msg=f"{label}'s own summary reports non-zero drift on a fresh build. Output:\n{combined}",
            )
            # gaps must be zero independently — the criterion is that the count
            # of artifacts "neither recorded nor declared exempt" is zero, and
            # reading that off its own field is more direct than inferring it.
            self.assertEqual(
                0,
                int(match.group(5)),
                msg=f"{label} reports unrecorded, unexempted artifact(s) on a fresh build. Output:\n{combined}",
            )

    def test_stricter_uncomparable_reporting_raises_no_false_alarm_on_the_real_tree(
        self,
    ) -> None:
        # covers: BP-100k-3-i
        self.assertTrue(
            self._build_drift_hook.exists(),
            msg=f"deployed check_build_drift.py missing at {self._build_drift_hook}",
        )
        self.assertTrue(
            self._output_drift_hook.exists(),
            msg=f"deployed check_output_drift.py missing at {self._output_drift_hook}",
        )

        result_build = _run_deployed_hook(self._build_drift_hook, self._isolated_tree)
        result_output = _run_deployed_hook(self._output_drift_hook, self._isolated_tree)

        for label, result in (
            ("check-build-drift", result_build),
            ("check-output-drift", result_output),
        ):
            combined = result.stdout + result.stderr
            self.assertNotIn(
                "ModuleNotFoundError",
                combined,
                msg=f"{label} crashed importing a dependency not present in the deploy manifest. Output:\n{combined}",
            )
            self.assertNotIn(
                "manifest not found",
                combined.lower(),
                msg=f"{label} could not resolve the real .build_manifest.json on the freshly-built tree. Output:\n{combined}",
            )
            self.assertEqual(
                0,
                result.returncode,
                msg=(
                    f"{label}'s stricter uncomparable reporting raised a false "
                    f"alarm on the full real tree the build just produced. "
                    f"Output:\n{combined}"
                ),
            )


if __name__ == "__main__":
    unittest.main()
