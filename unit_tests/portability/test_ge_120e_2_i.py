"""
MODULE: test_ge_120e_2_i
GOAL: TDD red-baseline tests for AC GE-120e-2-i — "A check whose recorded
    change-set source disagrees with what it actually inspects is named by
    running it, not by believing it."

    GE-120e-2 turns "does this check work out its own change set?" into a
    declared value (`change_set_source`) on each hooks_manifest.hooks[] entry.
    A declaration can be wrong the moment it is written. This AC is the only
    thing in the L1 that tests the claim for the COMPLEMENT of GE-120e-2's
    governed set — every entry recorded as HANDED its files by the commit
    path (i.e. NOT self-deriving). GE-120e-3's differential pair separately
    covers the governed (self-deriving) set; this file must never iterate the
    same entries GE-120e-3 does (see AC notes, "DO NOT DUPLICATE GE-120e-3").

BUSINESS CONTEXT: Ticket 31 of EPIC-TrustThatAGreenCheckActuallyChecked.
    Source AC: GE-120e-2-i. test_spec (AC YAML) is authoritative over the
    ticket body's derived Gherkin and supplies the five test names used below.

ARCHITECTURE / DEPENDENCIES — NOT YET IMPLEMENTED (this is the expected RED
    state at test-writer sign-off time):

    1. GE-120c-1 (ticket 12, "assigned_agent: test-writer" in the AC store —
       verification apparatus, not application code) is expected to land a
       shared out-of-process harness at unit_tests/portability/harness.py.
       This file's CONTRACT EXPECTATION of that harness (record this choice
       for GE-120c-1's implementer):
           harness.build_second_working_copy() -> SecondWorkingCopy
               Creates a real `git worktree add` copy of this repository at
               HEAD, runs `python scripts/build.py --target-dir <copy>`
               inside it, and returns an object exposing:
                 .root: Path                       — the copy's root
                 .stage_carried_in_deletion(rel_path: str) -> None
                     Simulates "carried-in, not authored" content: commits a
                     file on a side branch, merges it into the copy's working
                     branch with NO further author edits, and stages nothing
                     new — i.e. the deletion/content arrives purely via the
                     merge, exactly GE-120e-1's observed case.
                 .cleanup() -> None                — `git worktree remove`
           harness.run_check(copy, check_id, staged_files) -> HarnessResult
               Invokes `.leafcutter/scripts/commit_guardian/run_hook.py
               <check>.py <staged_files>` as a SEPARATE PROCESS from inside
               `copy`, with the source tree scrubbed from PYTHONPATH (per
               GE-120c-1's binding constraints). Returns an object exposing
               `.exit_code: int`, `.stdout: str`, `.stderr: str`.
       Neither the module nor these functions exist yet anywhere in this
       repository (confirmed: no unit_tests/portability/harness.py, no
       out-of-process runner other than the deployed run_hook.py itself).
       Importing them raises ImportError. THIS IS THE VALID RED STATE.

    2. GE-120e-2 (ticket 30, python-coder) is expected to land a manifest
       determination callable. This file's CONTRACT EXPECTATION (record this
       choice for GE-120e-2's implementer, per its own AC's instruction that
       "one new key per entry" is needed and this AC's `expects_from` names
       "the recorded change-set source on each manifest entry, and the
       manifest-derived candidate set" as the contract it consumes):
           scripts/commit_guardian/change_set_source.py
               determine_change_set_sources(manifest_path: Path) -> result
               exposing:
                 .handed_its_files: list[str]  — entry ids recorded with
                     change_set_source == "handed_by_commit_path" (the
                     complement THIS AC sweeps)
                 .self_deriving: list[str]     — entry ids recorded with
                     change_set_source == "self_derived" (GE-120e-3's set —
                     do not iterate here)
                 .failures: list[str]          — entry ids with a missing or
                     contradicted change_set_source value
       Confirmed absent: no `change_set_source` key appears anywhere in
       templates/scripts/commit_guardian/commit_guardian.json today, and no
       scripts/commit_guardian/change_set_source.py exists. Importing it
       raises ImportError. THIS IS ALSO THE VALID RED STATE.

    Until BOTH land, every test below fails via an explicit self.fail() that
    names the missing dependency — unambiguous, actionable red, matching the
    existing convention in unit_tests/portability/test_build_deployment.py
    (`if not _BUILD_PHASES_OK: self.fail(...)`) rather than a bare crash.

====================================================================
DECISION HISTORY
====================================================================
- 2026-08-25 [EPIC-TrustThatAGreenCheckActuallyChecked/31]: Initial TDD
  red-baseline, written before GE-120c-1's harness or GE-120e-2's
  determination exist (both are separate tickets in this epic; this ticket's
  own `depends_on:` frontmatter is empty even though the AC store correctly
  records `depends_on: [GE-120e-2]` — flagged in the ticket Comments as a
  ticket-authoring gap, not fixed here). The module paths, field name
  (`change_set_source`), and value vocabulary (`handed_by_commit_path` /
  `self_derived`) chosen above are this ticket's proposed contract; GE-120e-2
  and GE-120c-1's implementers should honour them or update this file to
  match whatever they actually ship.
====================================================================
"""
# @ac-tag: GE-120e-2-i

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — make scripts/ and unit_tests/ importable regardless of cwd.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

_REAL_MANIFEST_PATH = (
    _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "commit_guardian.json"
)

# ---------------------------------------------------------------------------
# GE-120c-1's out-of-process harness.
#
# This file was authored against a speculative name — `unit_tests/portability/
# harness.py`, imported as `unit_tests.portability.harness`. GE-120c-1 shipped it
# as `_deployed_check_harness.py`, and that is the established name: eleven files
# reference it (four test files, the module, four tickets and GE-120c-1.yaml)
# against this file's one. Reconciled here in favour of the delivered name rather
# than renaming the module, and matching the sys.path import form its two sibling
# consumers already use (test_ge_120b_2_i.py, test_ge120c1i_setup_failure_reporting.py).
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import _deployed_check_harness as _harness  # type: ignore[import]  # noqa: E402
    _HARNESS_OK = True
except (ImportError, ModuleNotFoundError):
    _harness = None  # type: ignore[assignment]
    _HARNESS_OK = False

# ---------------------------------------------------------------------------
# GE-120e-2's expected manifest determination callable. Does not exist yet —
# see module docstring, dependency (2).
# ---------------------------------------------------------------------------
try:
    from scripts.commit_guardian.change_set_source import (  # type: ignore[import]
        determine_change_set_sources,
    )
    _DETERMINATION_OK = True
except (ImportError, ModuleNotFoundError):
    determine_change_set_sources = None  # type: ignore[assignment]
    _DETERMINATION_OK = False


def _write_fixture_manifest(tmp_dir: Path, hooks: list[dict]) -> Path:
    """Write a standalone fixture manifest carrying the given hook entries.

    Per GE-120e-2's own coverage note, a fixture manifest — never today's —
    is what proves the determination reads the manifest at run time rather
    than a hand-written list, and it is what this AC's own coverage note
    (planting a misrecorded check) requires to demonstrate a real failure.
    """
    manifest_path = tmp_dir / "fixture_commit_guardian.json"
    manifest_path.write_text(
        json.dumps({"hooks_manifest": {"hooks": hooks}}, indent=2),
        encoding="utf-8",
    )
    return manifest_path


def _write_planted_misrecorded_check(tmp_dir: Path) -> Path:
    """Write the self-demonstration fixture: a check script whose manifest
    entry (constructed by the caller) will claim `change_set_source:
    handed_by_commit_path`, while the script itself derives its own change
    set via `git diff --cached` instead of inspecting only the files it is
    handed — the exact misattribution this AC exists to catch by RUNNING the
    check, not by reading its manifest entry.
    """
    check_path = tmp_dir / "check_planted_misrecorded.py"
    check_path.write_text(
        '''"""Fixture check for GE-120e-2-i: claims handed-its-files, derives its own diff."""
import subprocess
import sys


def main() -> int:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        check=False,
    )
    changed = [line for line in result.stdout.splitlines() if line.strip()]
    offenders = [
        f for f in changed if f.startswith("unit_tests/") or f.startswith("tests/")
    ]
    if offenders:
        for offender in offenders:
            print(f"OBJECTION: {offender} (from self-derived git diff --cached, "
                  f"state=staged-index)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
''',
        encoding="utf-8",
    )
    return check_path


class TestHandedItsFilesChecksToleateCarriedInWork(unittest.TestCase):
    """Every manifest entry recorded as handed-its-files must, when actually
    run as a process against a commit whose only trip-worthy content is
    carried in (not authored), raise no objection — the commit path hands it
    only the author's files, so carried-in content is never in its input.
    """

    def test_ge120e2i_handed_files_check_raises_no_objection_to_carried_in_work(
        self,
    ) -> None:
        # covers: GE-120e-2-i
        """RED until GE-120c-1's harness and GE-120e-2's determination exist.

        Once both land: read the handed-its-files complement from the REAL
        manifest via determine_change_set_sources(), build one real second
        working copy via the harness, stage a commit whose only trip-worthy
        content is carried in from a merge (see harness contract,
        stage_carried_in_deletion), run every handed-its-files check as a
        process passing it ONLY the author's (empty) file list — as the
        commit path actually would — and assert every one exits clean.
        """
        if not _DETERMINATION_OK:
            self.fail(
                "scripts.commit_guardian.change_set_source."
                "determine_change_set_sources does not exist yet — GE-120e-2 "
                "has not landed. This test cannot identify the handed-its-files "
                "complement until it does."
            )
        if not _HARNESS_OK:
            self.fail(
                "unit_tests.portability.harness does not exist yet — GE-120c-1's "
                "out-of-process harness has not landed. This test cannot execute "
                "checks as real subprocesses until it does."
            )

        result = determine_change_set_sources(_REAL_MANIFEST_PATH)
        handed_its_files = result.handed_its_files
        self.assertTrue(
            handed_its_files,
            "Expected at least one manifest entry recorded as "
            "change_set_source: handed_by_commit_path once GE-120e-2 "
            "populates the field on every entry — none are recorded today.",
        )

        copy = _harness.build_second_working_copy()
        try:
            copy.stage_carried_in_deletion("unit_tests/portability/_fixture_only.py")
            for check_id in handed_its_files:
                outcome = _harness.run_check(copy, check_id, staged_files=[])
                self.assertEqual(
                    0,
                    outcome.exit_code,
                    f"{check_id} is recorded as handed-its-files but objected "
                    f"to carried-in content it was never handed: "
                    f"{outcome.stdout}\n{outcome.stderr}",
                )
        finally:
            copy.cleanup()


class TestSelfDemonstrationOfMisrecordedCheck(unittest.TestCase):
    """Self-demonstration is a deliverable (AC coverage note): plant a check
    whose manifest entry claims handed-its-files while it actually derives
    its own change set, and show the sweep both NAMES it and FAILS. A sweep
    that has never been observed to fail is not evidence.
    """

    def test_ge120e2i_misrecorded_check_is_named_and_the_sweep_fails(self) -> None:
        # covers: GE-120e-2-i
        """RED until GE-120c-1 + GE-120e-2 exist.

        Once both land: write a fixture manifest with one entry recorded as
        change_set_source: "handed_by_commit_path" pointing at a planted
        check script that actually runs `git diff --cached` itself (see
        _write_planted_misrecorded_check). Stage carried-in trip-worthy
        content (a deletion under unit_tests/) via a real merge, with no
        author change. Run the planted check as a process, passing it the
        (empty) author file list the commit path would hand it, and assert:
        it objects (non-zero exit) and the objection text names the check,
        the content objected to, and the state that content came in from.
        The planted check is discovered through the manifest (constructed
        as a fixture), never special-cased in the assertion.
        """
        if not _DETERMINATION_OK or not _HARNESS_OK:
            self.fail(
                "Cannot demonstrate the sweep failing on a planted misrecorded "
                "check until both scripts.commit_guardian.change_set_source."
                "determine_change_set_sources (GE-120e-2) and "
                "unit_tests.portability.harness (GE-120c-1) exist."
            )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            planted_check = _write_planted_misrecorded_check(tmp_path)
            fixture_manifest = _write_fixture_manifest(
                tmp_path,
                hooks=[
                    {
                        "id": "check-planted-misrecorded",
                        "entry": str(planted_check),
                        "pass_filenames": True,
                        "change_set_source": "handed_by_commit_path",
                    }
                ],
            )

            result = determine_change_set_sources(fixture_manifest)
            self.assertIn(
                "check-planted-misrecorded",
                result.handed_its_files,
                "The determination must discover the planted check through "
                "the fixture manifest, not via a hard-coded assertion.",
            )

            copy = _harness.build_second_working_copy()
            try:
                copy.stage_carried_in_deletion("unit_tests/some_fixture_test.py")
                outcome = _harness.run_check(
                    copy, "check-planted-misrecorded", staged_files=[]
                )
            finally:
                copy.cleanup()

            self.assertNotEqual(
                0,
                outcome.exit_code,
                "Self-demonstration failed: the sweep must be able to fail on "
                "a check that claims handed-its-files while actually deriving "
                "its own diff. A sweep that has never been observed to fail "
                "is not evidence.",
            )
            combined_output = outcome.stdout + outcome.stderr
            self.assertIn(
                "check-planted-misrecorded",
                combined_output,
                "Failure report must NAME the offending check.",
            )
            self.assertIn(
                "unit_tests/some_fixture_test.py",
                combined_output,
                "Failure report must name the content objected to.",
            )


class TestSweepCoversTheDerivedComplement(unittest.TestCase):
    """The subject set is the complement, derived not listed: every manifest
    entry recorded as handed-its-files is swept, read from GE-120e-2's
    manifest reader at run time — no hand-written check list, no hard-coded
    entry count.
    """

    def test_ge120e2i_sweep_covers_every_handed_files_manifest_entry(self) -> None:
        # covers: GE-120e-2-i
        """RED until GE-120e-2's determination exists.

        Two fixture manifests with DIFFERENT entry counts and different
        handed-its-files subsets must each produce exactly their own
        entries in .handed_its_files — proving the set is read at run time
        from whichever manifest is given, not pinned to any count or any
        hand-maintained list of check ids.
        """
        if not _DETERMINATION_OK:
            self.fail(
                "scripts.commit_guardian.change_set_source."
                "determine_change_set_sources does not exist yet — GE-120e-2 "
                "has not landed. The derived-complement property cannot be "
                "exercised until it does."
            )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            small_manifest = _write_fixture_manifest(
                tmp_path,
                hooks=[
                    {"id": "check-a", "entry": "check_a.py",
                     "change_set_source": "handed_by_commit_path"},
                    {"id": "check-b", "entry": "check_b.py",
                     "change_set_source": "self_derived"},
                ],
            )
            small_result = determine_change_set_sources(small_manifest)
            self.assertEqual(["check-a"], sorted(small_result.handed_its_files))

            larger_manifest_path = tmp_path / "larger.json"
            larger_manifest_path.write_text(
                json.dumps(
                    {
                        "hooks_manifest": {
                            "hooks": [
                                {"id": "check-a", "entry": "check_a.py",
                                 "change_set_source": "handed_by_commit_path"},
                                {"id": "check-b", "entry": "check_b.py",
                                 "change_set_source": "self_derived"},
                                {"id": "check-c", "entry": "check_c.py",
                                 "change_set_source": "handed_by_commit_path"},
                                {"id": "check-d", "entry": "check_d.py",
                                 "change_set_source": "handed_by_commit_path"},
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )
            larger_result = determine_change_set_sources(larger_manifest_path)
            self.assertEqual(
                ["check-a", "check-c", "check-d"],
                sorted(larger_result.handed_its_files),
                "Adding entries to the fixture manifest must change the "
                "swept set with no change to the sweep's own code — the "
                "set is read, not hard-coded, and no count is pinned.",
            )


class TestFailureReportNamesThreeThings(unittest.TestCase):
    """The failure report must name three things: the check, the content it
    objected to, and the state that content arrived from. 'Check X failed'
    is not actionable and does not distinguish this defect from an unrelated
    check failure.
    """

    def test_ge120e2i_failure_report_names_objected_content_and_originating_state(
        self,
    ) -> None:
        # covers: GE-120e-2-i
        """RED until GE-120c-1 + GE-120e-2 exist.

        Reuses the planted-misrecorded-check scenario, but asserts
        specifically on the THIRD required element: the state the objected
        content came in from (e.g. "staged-index" / "carried-in via merge"),
        not merely the check name and the file name (covered separately by
        the self-demonstration test above). All three must be present
        together in one failure report.
        """
        if not _DETERMINATION_OK or not _HARNESS_OK:
            self.fail(
                "Cannot verify the three-part failure report until both "
                "scripts.commit_guardian.change_set_source."
                "determine_change_set_sources (GE-120e-2) and "
                "unit_tests.portability.harness (GE-120c-1) exist."
            )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            planted_check = _write_planted_misrecorded_check(tmp_path)
            fixture_manifest = _write_fixture_manifest(
                tmp_path,
                hooks=[
                    {
                        "id": "check-planted-misrecorded",
                        "entry": str(planted_check),
                        "pass_filenames": True,
                        "change_set_source": "handed_by_commit_path",
                    }
                ],
            )
            determine_change_set_sources(fixture_manifest)  # discovery, as above

            copy = _harness.build_second_working_copy()
            try:
                copy.stage_carried_in_deletion("unit_tests/some_fixture_test.py")
                outcome = _harness.run_check(
                    copy, "check-planted-misrecorded", staged_files=[]
                )
            finally:
                copy.cleanup()

            combined_output = outcome.stdout + outcome.stderr
            # 1. the check
            self.assertIn("check-planted-misrecorded", combined_output)
            # 2. the content it objected to
            self.assertIn("unit_tests/some_fixture_test.py", combined_output)
            # 3. the state that content arrived from
            self.assertIn(
                "staged-index",
                combined_output,
                "Failure report must name the STATE the objected content "
                "arrived from, not just the check and the filename — "
                "'Check X failed' is not actionable.",
            )


class TestSetupFailureIsAFailureNotASkip(unittest.TestCase):
    """Error-handling policy applies to the sweep's own subprocess and
    filesystem calls: specific exceptions, logged at WARNING, never
    swallowed — and a setup failure is a reported failure rather than a
    silently skipped case (GE-120c-1-i's standard, applied here).
    """

    def test_ge120e2i_setup_failure_is_reported_as_a_failure_not_a_skip(self) -> None:
        # covers: GE-120e-2-i
        """RED until GE-120c-1's harness exists.

        Point the harness at a manifest fixture that cannot be built into a
        second working copy (e.g. a nonexistent repository root) and assert
        the harness raises / returns an explicit failure outcome — never a
        silently-skipped case indistinguishable from "nothing to check
        here." A sweep that silently skips is indistinguishable from a
        sweep that passed.
        """
        if not _HARNESS_OK:
            self.fail(
                "unit_tests.portability.harness does not exist yet — GE-120c-1's "
                "out-of-process harness has not landed. The setup-failure "
                "reporting contract cannot be exercised until it does."
            )

        nonexistent_root = Path(tempfile.gettempdir()) / "ge120e2i-does-not-exist-42"
        with self.assertRaises(Exception) as ctx:
            _harness.build_second_working_copy(source_root=nonexistent_root)

        self.assertNotIsInstance(
            ctx.exception,
            KeyboardInterrupt,
            "A setup failure must surface as a reported failure, never be "
            "swallowed into a bare pass/skip.",
        )


if __name__ == "__main__":
    unittest.main()
