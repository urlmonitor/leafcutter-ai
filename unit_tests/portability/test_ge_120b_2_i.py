"""
MODULE: test_ge_120b_2_i
AC: GE-120b-2-i — "Main-checkout verdicts are unchanged by the shared
    resolution path"
GOAL: TDD red-baseline tests proving that adopting the shared
    prerequisite-resolution facility (GE-120b-2, a separate, not-yet-started
    ticket at the time this file is written) does not change what any check
    in hooks_manifest.hooks[] finds against a fixed, violation-provoking
    fixture — verdict-for-verdict, by check id, never in aggregate.

WHY THIS DEPENDS ON TWO NOT-YET-BUILT PIECES (documented per CLAUDE.md
    "TDD Order — test-writer Must Precede python-coder" and the sibling
    precedent at unit_tests/portability/test_ge120c1i_setup_failure_reporting.py):

    1. GE-120c-1 (ticket 12 in this epic, assigned to test-writer, not yet
       started) delivers the out-of-process harness
       (`unit_tests/portability/_deployed_check_harness.py`,
       `DeployedCheckHarness`). Per this AC's own it_requirements ("CAPTURE
       IT WITH THE GE-120c-1 HARNESS, not with an ad-hoc script written by
       the agent performing the migration"), the baseline capture and the
       after-adoption re-run MUST go through that harness. This test file
       does not invent a substitute.
    2. GE-120b-2 (ticket 09, also not yet started) is the migration itself.
       Its contract (per expects_from) is "the shared prerequisite-resolution
       facility, adopted across the check family."

    Both are out of scope for test-writer to build. This file therefore
    establishes the CONTRACT the AC's assigned agent (python-coder, per this
    AC's own `assigned_agent` field) must satisfy, and every test below is
    expected to fail via the `_MISSING_MSG` guards until that contract is
    implemented. A guard-triggered self.fail() (ImportError-turned-failure)
    is the valid RED state here, exactly as established by the sibling
    GE-120c-1-i test file in this same directory.

CONTRACT THIS TEST FILE ESTABLISHES, for whoever implements GE-120b-2-i:

    Module: scripts/commit_guardian/ge120b2i_verify_unchanged.py
        A CLI entry point (this AC's production entry point — see the
        reachability test below) with two subcommands:

        capture --repo-root PATH --baseline-path PATH
            Uses unit_tests.portability._deployed_check_harness
            .DeployedCheckHarness to build a real second working copy at the
            CURRENT commit (i.e. run BEFORE GE-120b-2's first line lands),
            stages the shared provoking fixture (see below) in it, runs
            every check in hooks_manifest.hooks[] against the DEPLOYED copy
            (.leafcutter/scripts/commit_guardian/ inside it — never
            templates/, per this AC's own it_requirements and ADR-001), and
            writes a JSON baseline to --baseline-path shaped as:
                {
                  "captured_at_sha": "<git rev-parse HEAD of the pre-sweep tree>",
                  "checks": {
                    "<check-id>": {"status": "clean"|"violation"|"could_not_check",
                                    "output": "<text the check wrote>"},
                    ...  # one entry per hooks_manifest.hooks[] id
                  }
                }

        verify --repo-root PATH --baseline-path PATH
            Re-stages the SAME shared provoking fixture in a FRESH second
            working copy of the CURRENT tree, runs every manifest check
            again through the same harness, and compares each check's
            verdict against the recorded baseline BY CHECK ID (never
            aggregated). Exits 0 only if every check's status is unchanged.
            Exits 1 and prints, per mismatching check id, both the recorded
            and the current status and output text, so a disagreement is
            readable directly. Every check id present in the baseline must
            also be reported in this run's output text (so "was this check
            still exercised" is visible without reading source).

    Module: unit_tests/portability/_ge120_provoking_fixture.py
        SHARED with GE-120b-4 per both ACs' own it_requirements ("build it
        once and own it in one place"). Exposes:
            def stage(working_copy_dir: Path) -> None:
                Stages a fixed set of files into working_copy_dir that
                provokes a genuine violation for EVERY check in
                templates/scripts/commit_guardian/commit_guardian.json's
                hooks_manifest.hooks[] (55 entries as of this writing — read
                the real count, never hard-code it). A fixture that leaves
                even one check clean makes that check's agreement
                uninformative (it could have silently stopped running).

DECISION HISTORY
====================================================================
- 2026-08-25 [EPIC-TrustThatAGreenCheckActuallyChecked/10, GE-120b-2-i]:
  Initial TDD red-baseline. Written BEFORE GE-120c-1's harness and BEFORE
  GE-120b-2's migration exist. Every test below is expected to fail via a
  self.fail() guard (module/artifact absent) until:
    (a) GE-120c-1 lands (`_deployed_check_harness.py`),
    (b) this AC's own production module is implemented and RUN to capture a
        real baseline BEFORE GE-120b-2's first commit, and
    (c) GE-120b-2 lands and the same module is re-run in `verify` mode.
  This is a valid, intentional RED state — see CLAUDE.md "TDD Order —
  test-writer Must Precede python-coder" and the sibling precedent at
  test_ge120c1i_setup_failure_reporting.py (same epic, same reasoning).
====================================================================
"""
# @ac-tag: GE-120b-2-i

from __future__ import annotations

import json
import logging
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path setup.
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent.parent  # unit_tests/portability/ -> worktree root
_MANIFEST_PATH = (
    _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "commit_guardian.json"
)
_ENTRY_POINT = _REPO_ROOT / "scripts" / "commit_guardian" / "ge120b2i_verify_unchanged.py"
_BASELINE_PATH = (
    _THIS_DIR / "fixtures" / "ge_120b_2_i" / "main_checkout_verdict_baseline.json"
)

sys.path.insert(0, str(_THIS_DIR))

try:
    import _deployed_check_harness as dch  # type: ignore[import]  # noqa: E402
    _HARNESS_OK = True
except ImportError:
    dch = None  # type: ignore[assignment]
    _HARNESS_OK = False

try:
    import _ge120_provoking_fixture as provoking_fixture  # type: ignore[import]  # noqa: E402
    _FIXTURE_OK = True
except ImportError:
    provoking_fixture = None  # type: ignore[assignment]
    _FIXTURE_OK = False

_HARNESS_MISSING_MSG = (
    "unit_tests/portability/_deployed_check_harness.py does not exist yet "
    "(GE-120c-1's deliverable, ticket 12 in this epic). GE-120b-2-i's own "
    "it_requirements are explicit: capture the baseline WITH the GE-120c-1 "
    "harness, not with an ad-hoc script — so this test cannot be satisfied "
    "until GE-120c-1 lands."
)
_FIXTURE_MISSING_MSG = (
    "unit_tests/portability/_ge120_provoking_fixture.py does not exist yet. "
    "This module is shared with GE-120b-4 and must stage files that provoke "
    "a genuine violation for every check in hooks_manifest.hooks[] — see "
    "this file's module docstring for the exact contract expected."
)
_ENTRY_POINT_MISSING_MSG = (
    f"{_ENTRY_POINT} does not exist yet. This is GE-120b-2-i's production "
    "entry point (assigned_agent: python-coder) — a CLI with 'capture' and "
    "'verify' subcommands that runs every hooks_manifest check against the "
    "shared provoking fixture via the GE-120c-1 harness and diffs verdicts "
    "per check id. See this file's module docstring for the exact CLI "
    "contract."
)
_BASELINE_MISSING_MSG = (
    f"{_BASELINE_PATH} does not exist yet. Per this AC's own it_requirements "
    "('THE BASELINE IS AN ARTIFACT, captured by EXECUTION before the first "
    "line of GE-120b-2 is written'), this file must be produced by actually "
    "running 'python scripts/commit_guardian/ge120b2i_verify_unchanged.py "
    "capture' against the current (pre-GE-120b-2) tree — never hand-authored "
    "or reconstructed from the check sources. A hand-typed baseline would "
    "agree with the change by construction, which is exactly the failure "
    "mode this AC's coverage note forbids."
)


def _read_manifest_check_ids() -> list[str]:
    """Read the real manifest's check ids — never a hard-coded set, per this
    AC's own 'assert PER CHECK BY ID' requirement and the shared-fixture
    requirement to cover every entry."""
    try:
        raw = _MANIFEST_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Could not read commit_guardian manifest at %s: %s",
                        _MANIFEST_PATH, exc)
        raise
    data = json.loads(raw)
    return [hook["id"] for hook in data.get("hooks_manifest", {}).get("hooks", [])]


def _load_baseline() -> dict:
    """Load the recorded pre-adoption baseline artifact. Raises FileNotFoundError
    if it has not been captured yet — callers must guard with _BASELINE_PATH.exists()
    and self.fail(_BASELINE_MISSING_MSG) first, per this file's established pattern."""
    raw = _BASELINE_PATH.read_text(encoding="utf-8")
    return json.loads(raw)


def _run_verify_entry_point(baseline_path: Path) -> subprocess.CompletedProcess:
    """Invoke the real production entry point as a SUBPROCESS — the
    reachability requirement this AC's Test Requirements table mandates.
    Never imports ge120b2i_verify_unchanged's functions directly."""
    return subprocess.run(  # noqa: S603
        [
            sys.executable,
            str(_ENTRY_POINT),
            "verify",
            "--repo-root", str(_REPO_ROOT),
            "--baseline-path", str(baseline_path),
        ],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )


class TestMainCheckoutVerdictsMatchBaseline(unittest.TestCase):
    """GE-120b-2-i AC-1/AC-2: a recorded pre-adoption baseline exists, and
    every check executed in the main checkout after adoption produces the
    same verdict as that recorded baseline, compared per check id."""

    def test_ge120b2i_main_checkout_verdicts_match_recorded_baseline(self) -> None:
        # covers: GE-120b-2-i
        if not _HARNESS_OK:
            self.fail(_HARNESS_MISSING_MSG)
        if not _FIXTURE_OK:
            self.fail(_FIXTURE_MISSING_MSG)
        if not _ENTRY_POINT.exists():
            self.fail(_ENTRY_POINT_MISSING_MSG)
        if not _BASELINE_PATH.exists():
            self.fail(_BASELINE_MISSING_MSG)

        baseline = _load_baseline()
        manifest_ids = _read_manifest_check_ids()
        self.assertTrue(
            set(manifest_ids).issubset(set(baseline.get("checks", {}).keys())),
            "Recorded baseline is missing entries for some manifest checks — "
            "the baseline must cover every id in hooks_manifest.hooks[].",
        )

        result = _run_verify_entry_point(_BASELINE_PATH)
        self.assertEqual(
            result.returncode,
            0,
            "verify must exit 0 when every check's verdict is unchanged from "
            f"the recorded baseline. stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )

        # Per-check-id assertion, never aggregate: every manifest id must be
        # named in the verify output text.
        for check_id in manifest_ids:
            with self.subTest(check_id=check_id):
                self.assertIn(
                    check_id,
                    result.stdout,
                    f"Check '{check_id}' from the manifest is not mentioned "
                    "in the verify output — a check silently dropped from "
                    "the sweep must be visible, not invisible.",
                )


class TestNoCheckLosesPrerequisiteResolution(unittest.TestCase):
    """GE-120b-2-i AC-3: no check that previously located its prerequisites
    now fails to locate them."""

    def test_ge120b2i_no_check_loses_prerequisite_resolution(self) -> None:
        # covers: GE-120b-2-i
        if not _HARNESS_OK:
            self.fail(_HARNESS_MISSING_MSG)
        if not _BASELINE_PATH.exists():
            self.fail(_BASELINE_MISSING_MSG)
        if not _ENTRY_POINT.exists():
            self.fail(_ENTRY_POINT_MISSING_MSG)

        baseline = _load_baseline()
        result = _run_verify_entry_point(_BASELINE_PATH)
        current = json.loads(result.stdout) if result.stdout.strip().startswith("{") else {}

        for check_id, recorded in baseline.get("checks", {}).items():
            with self.subTest(check_id=check_id):
                if recorded.get("status") == "could_not_check":
                    continue  # AC-3 is only about checks that DID resolve before.
                after = current.get("checks", {}).get(check_id, {})
                self.assertNotEqual(
                    after.get("status"),
                    "could_not_check",
                    f"Check '{check_id}' previously resolved its "
                    "prerequisites but now reports could_not_check — this "
                    "is the exact fail-open-on-migration regression this "
                    "AC exists to catch.",
                )


class TestNoCheckDowngradesViolationToClean(unittest.TestCase):
    """GE-120b-2-i AC-4 — the load-bearing clause: no check that previously
    reported a violation against the provoking fixture now reports clean.
    Asserted per check id, never in aggregate — an aggregate pass rate hides
    exactly one check going quiet."""

    def test_ge120b2i_no_check_downgrades_violation_to_clean(self) -> None:
        # covers: GE-120b-2-i
        if not _HARNESS_OK:
            self.fail(_HARNESS_MISSING_MSG)
        if not _FIXTURE_OK:
            self.fail(_FIXTURE_MISSING_MSG)
        if not _BASELINE_PATH.exists():
            self.fail(_BASELINE_MISSING_MSG)
        if not _ENTRY_POINT.exists():
            self.fail(_ENTRY_POINT_MISSING_MSG)

        baseline = _load_baseline()
        manifest_ids = _read_manifest_check_ids()

        # Sanity-check the baseline itself: the provoking fixture must have
        # produced a genuine violation for every manifest check, or an
        # agreement below carries no information (GE-120b-4's own concern,
        # restated here since this test depends on it).
        violation_ids = {
            cid for cid, rec in baseline.get("checks", {}).items()
            if rec.get("status") == "violation"
        }
        missing_violation = set(manifest_ids) - violation_ids
        self.assertFalse(
            missing_violation,
            "The recorded baseline does not show a 'violation' status for "
            f"every manifest check: {sorted(missing_violation)}. The shared "
            "provoking fixture (_ge120_provoking_fixture.stage) must provoke "
            "a genuine violation for every check, or agreement is "
            "uninformative.",
        )

        result = _run_verify_entry_point(_BASELINE_PATH)
        current = json.loads(result.stdout) if result.stdout.strip().startswith("{") else {}

        for check_id in violation_ids:
            with self.subTest(check_id=check_id):
                after = current.get("checks", {}).get(check_id, {})
                self.assertEqual(
                    after.get("status"),
                    "violation",
                    f"Check '{check_id}' previously reported a violation "
                    f"against the provoking fixture but now reports "
                    f"'{after.get('status')}' — a check going silently "
                    "clean is the consolidation bug this AC guards against.",
                )


class TestDifferencesConfinedToPreviouslyFailingCopies(unittest.TestCase):
    """GE-120b-2-i AC-5: the only observable difference between before and
    after is confined to working copies in which resolution previously
    failed. Any main-checkout difference elsewhere is a regression, not an
    improvement, and fails this AC."""

    def test_ge120b2i_differences_confined_to_previously_failing_copies(self) -> None:
        # covers: GE-120b-2-i
        if not _HARNESS_OK:
            self.fail(_HARNESS_MISSING_MSG)
        if not _BASELINE_PATH.exists():
            self.fail(_BASELINE_MISSING_MSG)
        if not _ENTRY_POINT.exists():
            self.fail(_ENTRY_POINT_MISSING_MSG)

        baseline = _load_baseline()
        result = _run_verify_entry_point(_BASELINE_PATH)
        current = json.loads(result.stdout) if result.stdout.strip().startswith("{") else {}

        for check_id, recorded in baseline.get("checks", {}).items():
            after = current.get("checks", {}).get(check_id, {})
            changed = (
                after.get("status") != recorded.get("status")
                or after.get("output") != recorded.get("output")
            )
            if not changed:
                continue
            with self.subTest(check_id=check_id):
                self.assertEqual(
                    recorded.get("status"),
                    "could_not_check",
                    f"Check '{check_id}' changed between the recorded "
                    "baseline and this run, but its recorded baseline "
                    f"status was '{recorded.get('status')}', not "
                    "'could_not_check' — SCOPE OF PERMITTED DIFFERENCE is "
                    "only working copies where resolution previously "
                    "FAILED. Any other main-checkout difference is a "
                    "regression, not an improvement.",
                )


class TestGe120b2iReachableFromEntryPoint(unittest.TestCase):
    """Reachability floor (mandatory per this ticket's Test Requirements):
    invoke the real production entry point as a subprocess — never by
    importing its functions directly — and assert the new behaviour actually
    occurs. Importing ge120b2i_verify_unchanged's internals would not prove
    the CLI is wired to anything real."""

    def test_ge_120b_2_i_reachable_from_entry_point(self) -> None:
        # covers: GE-120b-2-i
        if not _ENTRY_POINT.exists():
            self.fail(_ENTRY_POINT_MISSING_MSG)

        with tempfile.TemporaryDirectory() as tmp:
            # Point --baseline-path at a location inside a tmpdir so this
            # reachability check does not depend on a real captured baseline
            # existing yet; it only asserts the CLI is a real, runnable,
            # dispatchable entry point that reports something observable.
            missing_baseline = Path(tmp) / "no_baseline_here.json"
            result = subprocess.run(  # noqa: S603
                [
                    sys.executable,
                    str(_ENTRY_POINT),
                    "verify",
                    "--repo-root", str(_REPO_ROOT),
                    "--baseline-path", str(missing_baseline),
                ],
                capture_output=True,
                text=True,
                timeout=600,
                check=False,
            )

            # The CLI must be a real dispatchable process (not a stub that
            # silently exits 0 having done nothing): a missing baseline must
            # be reported as a real, named failure.
            self.assertNotEqual(
                result.returncode,
                0,
                "ge120b2i_verify_unchanged.py verify must fail loudly when "
                "--baseline-path does not exist, not exit 0 having done "
                "nothing — a silent success here is the exact vacuous-sweep "
                "shape this epic exists to prevent.",
            )
            combined = f"{result.stdout}\n{result.stderr}"
            self.assertIn(
                str(missing_baseline),
                combined,
                "The failure must name the missing baseline path so a "
                "reader can see which artifact was expected, not a generic "
                f"error. Output was:\n{combined}",
            )


if __name__ == "__main__":
    unittest.main()
