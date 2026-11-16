"""
MODULE: unit_tests/commit_guardian/bp_100k_3/test_bp_100k_3_build_drift_reporting.py
GOAL: AC-1 to AC-4 of BP-100k-3, each executing the deployed
    check_build_drift.py over a synthesized tree: a declared exemption is
    reported as exempt and names its ground (AC-1), an unrecorded and
    undeclared artifact is reported as a coverage gap naming the registering
    action (AC-2), the run summary carries a non-zero uncomparable count
    (AC-3), and "could not compare" differs from "compared and matched" in
    both the verified count and the exit status (AC-4).
CONTRACT: the output and exit-code contract these tests hold the gate to is
    stated in the module docstring of ``_support.py`` in this package.

DECISION HISTORY:
- 2026-11-16 [split-oversized-tests]: Moved here unchanged from
  unit_tests/commit_guardian/test_bp_100k_3.py when that file was split.
  AC-1/2/3 share their setUp through BuildDriftScenarioTestCase, and AC-3/4
  narrow each RESULT-line match with an isinstance assertion after the
  existing assertIsNotNone, for the type checker.
"""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from unit_tests.commit_guardian.bp_100k_3._support import (
    _DEFAULT_GROUND,
    _RESULT_LINE_RE,
    BuildDriftScenarioTestCase,
    _deploy_commit_guardian_dir,
    _exemption_config,
    _make_all_matched_scenario,
    _make_build_drift_scenario,
    _run_hook,
)


# ---------------------------------------------------------------------------
# AC-1: declared exemption reported as exempt, naming its ground.
# ---------------------------------------------------------------------------


class TestDeclaredExemptionReportedWithGround(BuildDriftScenarioTestCase):
    """AC-1: a declared-exempt hand-maintained artifact is reported as
    exempt and its ground is named."""

    def test_declared_exemption_is_reported_as_exempt_and_names_its_ground(self) -> None:
        # covers: BP-100k-3
        config = _exemption_config(
            [{"path": self.scenario["exempt_key"], "ground": _DEFAULT_GROUND}]
        )
        result = _run_hook(self.hook, self.workspace, exemption_config=config)
        combined = result.stdout + result.stderr

        self.assertIn(
            f"UNCOMPARABLE: EXEMPT {self.scenario['exempt_key']}",
            combined,
            msg=(
                "The declared-exempt hand-maintained artifact was not reported "
                f"as an exemption. Output:\n{combined}"
            ),
        )
        self.assertIn(
            _DEFAULT_GROUND,
            combined,
            msg=f"The declared exemption's ground was not named in the output. Output:\n{combined}",
        )


# ---------------------------------------------------------------------------
# AC-2: unrecorded, undeclared artifact reported as a coverage gap.
# ---------------------------------------------------------------------------


class TestUnrecordedUndeclaredArtifactIsCoverageGap(BuildDriftScenarioTestCase):
    """AC-2: an artifact neither recorded in the manifest nor declared
    exempt is reported as a coverage gap naming the artifact and the
    registering action."""

    def test_unrecorded_undeclared_artifact_is_reported_as_a_coverage_gap(self) -> None:
        # covers: BP-100k-3
        config = _exemption_config(
            [{"path": self.scenario["exempt_key"], "ground": _DEFAULT_GROUND}]
        )
        result = _run_hook(self.hook, self.workspace, exemption_config=config)
        combined = result.stdout + result.stderr

        self.assertIn(
            f"UNCOMPARABLE: GAP {self.scenario['orphan_key']}",
            combined,
            msg=(
                "The unrecorded, undeclared artifact was not reported as a "
                f"coverage gap. Output:\n{combined}"
            ),
        )
        self.assertIn(
            "build.py",
            combined,
            msg=f"The coverage-gap report does not name the registering action. Output:\n{combined}",
        )


# ---------------------------------------------------------------------------
# AC-3: run summary carries a non-zero uncomparable count.
# ---------------------------------------------------------------------------


class TestRunSummaryCountsUncomparableArtifacts(BuildDriftScenarioTestCase):
    """AC-3: the run summary states a non-zero count of artifacts the gate
    could not compare."""

    def test_run_summary_counts_uncomparable_artifacts_and_is_not_called_clean(self) -> None:
        # covers: BP-100k-3
        config = _exemption_config(
            [{"path": self.scenario["exempt_key"], "ground": _DEFAULT_GROUND}]
        )
        result = _run_hook(self.hook, self.workspace, exemption_config=config)
        combined = result.stdout + result.stderr

        match = _RESULT_LINE_RE.search(combined)
        self.assertIsNotNone(
            match,
            msg=(
                "No RESULT summary line found (expected "
                "'check-build-drift: RESULT verified=<N> uncomparable=<M> "
                f"drifted=<D>'). Output:\n{combined}"
            ),
        )
        assert isinstance(match, re.Match)
        uncomparable = int(match.group(3))
        self.assertGreater(
            uncomparable,
            0,
            msg=(
                "The run summary's uncomparable count is not positive despite "
                f"one exempt and one gap artifact in this run. Output:\n{combined}"
            ),
        )


# ---------------------------------------------------------------------------
# AC-4: uncomparable is distinguishable from compared in output AND exit
# status; an uncomparable artifact is never counted as verified.
# ---------------------------------------------------------------------------


class TestUncomparableDistinguishableFromComparedAndExitDiffers(unittest.TestCase):
    """AC-4: an uncomparable artifact is absent from the verified count, and
    the exit status of an uncomparable run differs from an all-matched run."""

    def setUp(self) -> None:
        self._gap_tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._gap_tmpdir.cleanup)
        self.gap_workspace = Path(self._gap_tmpdir.name)
        self.gap_scenario = _make_build_drift_scenario(self.gap_workspace)
        self.gap_hook = (
            _deploy_commit_guardian_dir(self.gap_workspace) / "check_build_drift.py"
        )

        self._clean_tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._clean_tmpdir.cleanup)
        self.clean_workspace = Path(self._clean_tmpdir.name)
        self.clean_scenario = _make_all_matched_scenario(self.clean_workspace)
        self.clean_hook = (
            _deploy_commit_guardian_dir(self.clean_workspace) / "check_build_drift.py"
        )

    def test_uncomparable_is_distinguishable_from_compared_in_output_and_exit_status(
        self,
    ) -> None:
        # covers: BP-100k-3
        gap_config = _exemption_config(
            [{"path": self.gap_scenario["exempt_key"], "ground": _DEFAULT_GROUND}]
        )
        result_gap = _run_hook(self.gap_hook, self.gap_workspace, exemption_config=gap_config)
        combined_gap = result_gap.stdout + result_gap.stderr

        match_gap = _RESULT_LINE_RE.search(combined_gap)
        self.assertIsNotNone(
            match_gap, msg=f"No RESULT summary line in the uncomparable run. Output:\n{combined_gap}"
        )
        assert isinstance(match_gap, re.Match)
        verified_gap = int(match_gap.group(2))
        uncomparable_gap = int(match_gap.group(3))
        self.assertEqual(
            1,
            verified_gap,
            msg=(
                "The exempt and gap artifacts must never be counted as "
                f"verified. Output:\n{combined_gap}"
            ),
        )
        self.assertGreaterEqual(
            uncomparable_gap,
            2,
            msg=f"Expected both the exempt and the gap artifact to count as uncomparable. Output:\n{combined_gap}",
        )

        result_clean = _run_hook(self.clean_hook, self.clean_workspace, exemption_config=None)
        combined_clean = result_clean.stdout + result_clean.stderr
        match_clean = _RESULT_LINE_RE.search(combined_clean)
        self.assertIsNotNone(
            match_clean, msg=f"No RESULT summary line in the all-matched run. Output:\n{combined_clean}"
        )
        assert isinstance(match_clean, re.Match)
        self.assertEqual(
            0,
            int(match_clean.group(3)),
            msg=f"An all-matched run must have zero uncomparable artifacts. Output:\n{combined_clean}",
        )

        self.assertEqual(
            0,
            result_clean.returncode,
            msg=f"An all-matched, non-drifted run must exit 0. Output:\n{combined_clean}",
        )
        self.assertNotEqual(
            0,
            result_gap.returncode,
            msg=f"A run containing an uncomparable artifact must not exit 0. Output:\n{combined_gap}",
        )
        self.assertNotEqual(
            result_gap.returncode,
            result_clean.returncode,
            msg=(
                "The exit status of a run with an uncomparable artifact must "
                "differ from the exit status of an all-matched run. "
                f"gap={result_gap.returncode} clean={result_clean.returncode}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
