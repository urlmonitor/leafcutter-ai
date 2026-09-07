"""
MODULE: test_ge120c1i_setup_failure_reporting
AC: GE-120c-1-i — "The harness reports its own setup failure instead of
    passing vacuously"
GOAL: TDD red-baseline tests for the GE-120c-1 out-of-process check harness's
    OWN error handling. GE-120c-1 (a separate, not-yet-implemented ticket)
    delivers a harness that stands up a real second working copy of this
    repository and runs the deployed commit_guardian checks against it out of
    process. This AC guards the harness's failure path: if the harness cannot
    finish standing up that second copy — for example the copy exists but
    `python scripts/build.py --target-dir <copy>` was never run inside it, so
    the deployed layout (`.leafcutter/scripts/commit_guardian/`) is absent —
    the harness must FAIL LOUDLY and NAME the missing setup step, rather than
    silently reporting a clean sweep having exercised zero checks.

WHY THIS MUST BE EXERCISED FOR REAL, NOT STUBBED (per the AC's own
    it_requirements): "Do not simulate it by stubbing the harness's own
    counter or by raising a synthetic exception — a stub reproduces the
    author's belief about how setup half-fails, and a harness that stands up
    infrastructure has far more ways to half-fail than a check does." Every
    test below therefore creates a REAL second working copy via
    `git worktree add` and deliberately never builds it — this is the actual
    incomplete-setup condition, not a mock of it.

CONTRACT THIS TEST FILE ESTABLISHES for whoever implements GE-120c-1
    (`unit_tests/portability/_deployed_check_harness.py`, a test-only support
    module — HOME is unit_tests/portability/ per GE-120c-1's it_requirements,
    deliberately not scripts/ or templates/scripts/commit_guardian/, since
    this harness is verification apparatus, never shipped to consumers):

    class HarnessResult:
        success: bool                  # False whenever setup did not complete
        checks_exercised: int          # 0 when the sweep never reached the
                                        # per-check execution loop
        manifest_check_count: int      # size of the expected set, read from
                                        # templates/scripts/commit_guardian/
                                        # commit_guardian.json -> hooks_manifest
                                        # .hooks[] (GE-120c-3) — NOT a constant
        message: str                   # human-readable report; must surface
                                        # checks_exercised and
                                        # manifest_check_count in TEXT, so a
                                        # reader sees "0 of N" without reading
                                        # any assertion
        failed_setup_step: str | None  # None on success; on a setup failure,
                                        # names the SPECIFIC missing artifact/
                                        # step (e.g. "build.py did not produce
                                        # .leafcutter/scripts/commit_guardian
                                        # in <copy>") — never a generic
                                        # "setup failed" message

    class DeployedCheckHarness:
        def __init__(self, repo_root: Path) -> None: ...
        def run_sweep(self, second_copy_dir: Path) -> HarnessResult:
            # Verify second_copy_dir has the deployed layout the checks need
            # (.leafcutter/scripts/commit_guardian/ inside it). If that layout
            # is incomplete, return a HarnessResult with success=False,
            # checks_exercised=0, and failed_setup_step naming the specific
            # gap — do NOT proceed to execute any check. If the layout is
            # present, proceed to the per-check execution loop (GE-120c-1's
            # own scope).
            ...

====================================================================
DECISION HISTORY
====================================================================
- 2026-08-25 [EPIC-TrustThatAGreenCheckActuallyChecked/17, GE-120c-1-i]:
  Initial TDD red-baseline. Written BEFORE GE-120c-1's harness
  (`_deployed_check_harness.py`) exists at all — that module is a separate
  ticket's deliverable. Every test in this file is expected to fail with
  ImportError-turned-self.fail() (see `_HARNESS_OK` guard below) until that
  module is authored AND implements the setup-failure contract documented
  above. This is a valid, intentional RED state — see CLAUDE.md "TDD Order —
  test-writer Must Precede python-coder".
====================================================================
"""
# @ac-tag: GE-120c-1-i

from __future__ import annotations

import json
import logging
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path setup — make this test's sibling support module importable, and locate
# the real repository root (this worktree) for the git-worktree fixture and
# the manifest read.
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent.parent  # unit_tests/portability/ -> worktree root
_MANIFEST_PATH = (
    _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "commit_guardian.json"
)

sys.path.insert(0, str(_THIS_DIR))

try:
    import _deployed_check_harness as dch  # type: ignore[import]  # noqa: E402
    _HARNESS_OK = True
except ImportError:
    dch = None  # type: ignore[assignment]
    _HARNESS_OK = False

_HARNESS_MISSING_MSG = (
    "unit_tests/portability/_deployed_check_harness.py does not exist yet "
    "(or does not define DeployedCheckHarness). This module is GE-120c-1's "
    "deliverable — GE-120c-1-i (this file) additionally requires that its "
    "run_sweep() reports a named setup failure with checks_exercised == 0 "
    "and success is False when the second copy's deployed layout was never "
    "built. See the module docstring above for the full contract."
)


def _read_manifest_check_count() -> int:
    """Read the expected check count from the real manifest (GE-120c-3's
    source of truth) — never a hard-coded constant, per GE-120c-1-i's own
    it_requirements ("Compare the count against the manifest set (GE-120c-3)
    rather than against a constant")."""
    try:
        raw = _MANIFEST_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Could not read commit_guardian manifest at %s: %s",
                        _MANIFEST_PATH, exc)
        raise
    data = json.loads(raw)
    return len(data.get("hooks_manifest", {}).get("hooks", []))


def _create_incomplete_second_copy(target_dir: Path) -> None:
    """Stand up a REAL second working copy of this repository via
    `git worktree add`, and deliberately do NOT run `scripts/build.py`
    inside it — this is the actual incomplete-setup condition the AC
    describes, not a stub of it."""
    try:
        subprocess.run(
            ["git", "worktree", "add", "--detach", str(target_dir), "HEAD"],
            cwd=str(_REPO_ROOT),
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (subprocess.CalledProcessError, OSError) as exc:
        logger.warning("Failed to create incomplete second copy at %s: %s",
                        target_dir, exc)
        raise


def _remove_second_copy(target_dir: Path) -> None:
    """Tear down the real worktree created for the test, unconditionally —
    a worktree shares the git object store with this repo, so it must not be
    left behind even when the test itself failed."""
    try:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(target_dir)],
            cwd=str(_REPO_ROOT),
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except OSError as exc:
        logger.warning("Failed to remove second copy worktree at %s: %s",
                        target_dir, exc)


class TestSetupFailureReportedNotVacuousSuccess(unittest.TestCase):
    """GE-120c-1-i: a harness run against a second copy whose deployed layout
    was never built must report a FAILURE naming the missing step, never a
    vacuous "every check passed" result, and it must show its exercised-check
    count (0) rather than let that number hide inside a passing assertion."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        # Use a uuid-suffixed subdirectory rather than the raw tempdir root:
        # `git worktree add` requires a path that does not yet exist.
        self.second_copy_dir = Path(self._tmp.name) / f"incomplete-copy-{uuid.uuid4().hex[:8]}"
        _create_incomplete_second_copy(self.second_copy_dir)
        # Sanity-check the fixture itself: the deployed layout must genuinely
        # be absent, or this test is not exercising the condition it claims
        # to. If this ever fires, the fixture (not the harness) is broken.
        deployed_layout = self.second_copy_dir / ".leafcutter" / "scripts" / "commit_guardian"
        if deployed_layout.exists():
            self.fail(
                f"Test fixture invalid: {deployed_layout} unexpectedly exists "
                "in a freshly created, never-built worktree. The incomplete-"
                "setup precondition this AC exercises is not actually present."
            )

    def tearDown(self) -> None:
        _remove_second_copy(self.second_copy_dir)
        self._tmp.cleanup()

    # ------------------------------------------------------------------
    def test_ge120c1i_incomplete_setup_reports_failure_not_all_passed(self) -> None:
        """AC-2: it reports a failure rather than reporting that every check
        passed."""
        # covers: GE-120c-1-i
        if not _HARNESS_OK:
            self.fail(_HARNESS_MISSING_MSG)

        harness = dch.DeployedCheckHarness(repo_root=_REPO_ROOT)
        result = harness.run_sweep(self.second_copy_dir)

        self.assertIs(
            result.success,
            False,
            "A harness run against a never-built second copy must report "
            "success is False — reporting True (every check passed) here "
            "is exactly the vacuous-success defect this AC exists to catch.",
        )

    # ------------------------------------------------------------------
    def test_ge120c1i_names_the_setup_step_that_did_not_complete(self) -> None:
        """AC-1: it states that no check was exercised and names the setup
        step that did not complete."""
        # covers: GE-120c-1-i
        if not _HARNESS_OK:
            self.fail(_HARNESS_MISSING_MSG)

        harness = dch.DeployedCheckHarness(repo_root=_REPO_ROOT)
        result = harness.run_sweep(self.second_copy_dir)

        self.assertIsNotNone(
            result.failed_setup_step,
            "failed_setup_step must be populated when setup did not "
            "complete — a bare success=False with no named step sends the "
            "reader to the wrong layer.",
        )
        combined_text = f"{result.failed_setup_step}\n{result.message}"

        # The step must be named SPECIFICALLY: the missing artifact path,
        # not a generic phrase like "setup error".
        self.assertIn(
            ".leafcutter/scripts/commit_guardian",
            combined_text,
            "The failure must name the specific missing deployed-layout "
            "path, e.g. 'build.py did not produce "
            ".leafcutter/scripts/commit_guardian in <copy>' — a generic "
            "setup-error message is not acceptable per GE-120c-1-i.",
        )
        self.assertIn(
            "build.py",
            combined_text,
            "The failure must name build.py as the setup step that did "
            "not complete, since that is the step whose output is missing.",
        )
        self.assertIn(
            str(self.second_copy_dir),
            combined_text,
            "The failure must name WHICH copy the deployed layout is "
            "missing in, not just that some copy somewhere is incomplete.",
        )
        # Reject the generic-message failure mode explicitly.
        self.assertNotEqual(
            result.failed_setup_step.strip().lower(),
            "setup error",
            "A generic 'setup error' string is exactly the failure mode "
            "this AC forbids — the step must be named specifically.",
        )

    # ------------------------------------------------------------------
    def test_ge120c1i_zero_exercised_checks_is_never_a_successful_sweep(self) -> None:
        """AC-3: a run in which zero checks were exercised is never reported
        as a successful sweep, even when no assertion failed.

        This is the core defect shape: the vacuous path produces no failing
        assertion of its own (no check ever ran, so nothing inside a check
        could fail). The only thing that can catch it is a POSITIVE
        assertion on the exercised count, never a wait for a failure that
        structurally cannot occur.
        """
        # covers: GE-120c-1-i
        if not _HARNESS_OK:
            self.fail(_HARNESS_MISSING_MSG)

        harness = dch.DeployedCheckHarness(repo_root=_REPO_ROOT)
        result = harness.run_sweep(self.second_copy_dir)

        self.assertEqual(
            result.checks_exercised,
            0,
            "Setup never completed, so the per-check execution loop must "
            "never have been reached — checks_exercised must be exactly 0.",
        )
        # The defining assertion of this AC: exercised == 0 must NOT be
        # allowed to coexist with success == True. Assert on the pairing
        # directly, not on the absence of some other failure.
        self.assertFalse(
            result.checks_exercised == 0 and result.success is True,
            "VACUOUS SUCCESS DETECTED: zero checks were exercised but the "
            "sweep reported success. This is the exact green-sweep-over-"
            "nothing shape that shipped twice already in this project "
            "(fast-lane-build.js; the phantom-done files_touched hook).",
        )

    # ------------------------------------------------------------------
    def test_ge120c1i_exercised_check_count_present_in_output(self) -> None:
        """AC-4: the count of checks actually exercised appears in the
        harness output, so a reader can see that the number is not zero
        without reading the assertions — and that count is measured against
        the manifest set (GE-120c-3), not a constant."""
        # covers: GE-120c-1-i
        if not _HARNESS_OK:
            self.fail(_HARNESS_MISSING_MSG)

        expected_manifest_count = _read_manifest_check_count()
        self.assertGreater(
            expected_manifest_count,
            0,
            "Test precondition failed: the real commit_guardian manifest "
            "must contain at least one check.",
        )

        harness = dch.DeployedCheckHarness(repo_root=_REPO_ROOT)
        result = harness.run_sweep(self.second_copy_dir)

        # Structured fields: the harness must know both numbers itself.
        self.assertEqual(result.checks_exercised, 0)
        self.assertEqual(
            result.manifest_check_count,
            expected_manifest_count,
            "manifest_check_count must be read from the real manifest "
            f"({_MANIFEST_PATH}), not hard-coded — expected "
            f"{expected_manifest_count} entries.",
        )

        # Textual output: a reader must be able to see "0 exercised" and the
        # manifest size WITHOUT inspecting any assertion or return value.
        self.assertIn(
            "0",
            result.message,
            "The exercised count (0) must be visible in the harness's "
            "printed/returned message text on this run, not only in a "
            "structured field nobody reads.",
        )
        self.assertIn(
            str(expected_manifest_count),
            result.message,
            "The manifest size must also appear in the message so the "
            "reader can see the exercised count relative to the full "
            "expected set, not as a bare unexplained zero.",
        )


if __name__ == "__main__":
    unittest.main()
