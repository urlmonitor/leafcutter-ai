"""
MODULE: test_ge_120e_2_i
GOAL: Behavioral tests for AC GE-120e-2-i — "A check whose recorded
    change-set source disagrees with what it actually inspects is named by
    running it, not by believing it."

    GE-120e-2 turns "does this check work out its own change set?" into a
    declared value (`change_set_source`) on each hooks_manifest.hooks[]
    entry. A declaration can be wrong the moment it is written. This AC is
    the only thing in the L1 that tests the claim for the COMPLEMENT of
    GE-120e-2's governed set — every entry recorded as HANDED its files by
    the commit path (i.e. NOT self-deriving). GE-120e-3's differential pair
    separately covers the governed (self-deriving) set; this file must never
    iterate the same entries GE-120e-3 does (see AC notes, "DO NOT DUPLICATE
    GE-120e-3").

BUSINESS CONTEXT: Ticket 31 of EPIC-TrustThatAGreenCheckActuallyChecked.
    Source AC: GE-120e-2-i. test_spec (AC YAML) is authoritative over the
    ticket body's derived Gherkin and supplies the five test names used
    below.

====================================================================
DECISION HISTORY
====================================================================
- 2026-08-25 [EPIC-TrustThatAGreenCheckActuallyChecked/31]: Initial TDD
  red-baseline, written before GE-120c-1's harness or GE-120e-2's
  determination existed. Proposed a SPECULATIVE harness contract
  (`unit_tests.portability.harness.build_second_working_copy()` /
  `.stage_carried_in_deletion()` / `.run_check()`) that GE-120c-1's
  implementer never built — GE-120c-1 shipped
  `unit_tests/portability/_deployed_check_harness.py`'s
  `DeployedCheckHarness` with a materially different surface
  (`create_second_copy(target_dir)` / `stage_files(dir, files)` /
  `invoke_check(dir, entry_template, args)` / `run_sweep(...)`). This is the
  third instance in this epic of a sibling test authored against a guessed
  API the implementing ticket then named differently (see also
  `_resolve_change_set` vs `_authored_change`, and `harness` vs
  `_deployed_check_harness` in this file's own original import line).

- 2026-09-07 [EPIC-TrustThatAGreenCheckActuallyChecked/31, reopened]:
  Reconciled against what actually shipped. `change_set_source.py`
  (GE-120e-2) landed with `determine_change_set_sources(manifest_path) ->
  DeterminationResult` exposing `.handed_its_files` / `.self_deriving` /
  `.failures` — this matches the original contract closely enough to use
  unchanged. `_deployed_check_harness.DeployedCheckHarness` (GE-120c-1) did
  NOT match the guessed contract at all; every use of it below is rewritten
  against its real, shipped methods. No shim methods were added to the
  harness to satisfy the old guessed names — per this ticket's own
  reopening note, that is exactly the move this reconciliation exists to
  avoid. `run_sweep()`'s own "agrees" semantics (built for GE-120c-1's
  differential first-copy/second-copy comparison) do not fit this AC's
  need — this AC asserts an ABSOLUTE property (does the check itself
  object or not against ONE copy), not a disagreement BETWEEN two copies —
  so the tests below build their own minimal sweep loop over
  `invoke_check()` rather than calling `run_sweep()`.
====================================================================
"""
# @ac-tag: GE-120e-2-i

from __future__ import annotations

import atexit
import json
import shutil
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
# GE-120c-1's real out-of-process harness module.
# unit_tests/portability/_deployed_check_harness.py — NOT the speculative
# unit_tests.portability.harness this file originally guessed at.
# ---------------------------------------------------------------------------
try:
    from unit_tests.portability import _deployed_check_harness as _harness_mod  # type: ignore[import]
    _HARNESS_OK = True
except (ImportError, ModuleNotFoundError):
    _harness_mod = None  # type: ignore[assignment]
    _HARNESS_OK = False

# ---------------------------------------------------------------------------
# GE-120e-2's manifest determination callable. Landed as guessed.
# ---------------------------------------------------------------------------
try:
    from scripts.commit_guardian.change_set_source import (  # type: ignore[import]
        determine_change_set_sources,
    )
    _DETERMINATION_OK = True
except (ImportError, ModuleNotFoundError):
    determine_change_set_sources = None  # type: ignore[assignment]
    _DETERMINATION_OK = False


def _read_manifest_hooks_by_id(manifest_path: Path) -> dict:
    """Read `hooks_manifest.hooks[]` from `manifest_path` into an id-keyed
    dict, exactly as `determine_change_set_sources` reads it — so the entry
    template + `pass_filenames` for a given check id can be looked up
    without a second, independent manifest reader drifting from the first.
    """
    data = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    hooks = data.get("hooks_manifest", {}).get("hooks", [])
    return {h["id"]: h for h in hooks if isinstance(h, dict) and h.get("id")}


def _sweep(harness, working_copy_dir: Path, hooks_by_id: dict, check_ids, staged_files):
    """This AC's own minimal sweep: run each named check id (looked up in
    `hooks_by_id`) as a REAL SEPARATE PROCESS against `working_copy_dir`,
    handing it only `staged_files` (the files the commit path would hand
    it — empty when "the author wrote nothing"). Returns a dict of
    check_id -> CopyCheckOutcome, so a caller can name the check alongside
    its own observable output ("the content it objected to and the state
    that content came in from").
    """
    report = {}
    for check_id in check_ids:
        hook = hooks_by_id.get(check_id)
        if hook is None:
            continue
        args = list(staged_files) if hook.get("pass_filenames", False) else []
        report[check_id] = harness.invoke_check(working_copy_dir, hook.get("entry", ""), args)
    return report


# Signals that a non-zero exit means "this check could not run here", NOT
# "this check inspected the change set and objected to something in it".
#
# This distinction is the whole point of GE-120a-1, and getting it wrong is
# what made this sweep accuse six checks of objecting to carried-in content
# when not one of them had inspected anything: two were handed no file
# argument and printed usage, two needed a product-truth store the second
# working copy does not carry, and two needed a fuller layout than the
# fixture provides. `exit != 0` is not an objection.
#
# The RESULT-line form is the epic's own machine-readable vocabulary
# (`check_outcome.OUTCOME_COULD_NOT_CHECK`) and is the form this should
# eventually rely on alone. The prose markers below are a documented
# INTERIM fallback for checks that have not adopted that vocabulary yet —
# adoption across the fleet is GE-120a-2/GE-120a-5's scope. Delete the
# fallback when it lands; do not grow it to paper over a real objection.
_COULD_NOT_RUN_MARKERS = (
    "could_not_check",
    "usage:",
    "cannot read",
    "skipping",
    "no such file or directory",
    "modulenotfounderror",
    "importerror",
    "traceback (most recent call last)",
    "matches none of the",
)


def _could_not_run(outcome) -> bool:
    """True when `outcome` shows the check never performed its inspection."""
    lowered = (outcome.output or "").lower()
    return any(marker in lowered for marker in _COULD_NOT_RUN_MARKERS)


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


# ---------------------------------------------------------------------------
# Shared second working copy — built ONCE, lazily, on first use, per this
# AC's own Implementation Notes ("Build the fixture repository ONCE per
# sweep, never per check"). Only the tests that actually need a real
# deployed second copy (handed-files sweep + the two self-demonstration
# tests) trigger the build; the pure-determination test (sweep coverage)
# and the setup-failure test do not.
# ---------------------------------------------------------------------------
_shared_copy_holder: dict = {"path": None}


def _get_shared_second_copy() -> Path:
    if _shared_copy_holder["path"] is None:
        tmp_dir = Path(tempfile.mkdtemp(prefix="ge120e2i-second-copy-"))
        harness = _harness_mod.DeployedCheckHarness(_REPO_ROOT)
        harness.create_second_copy(tmp_dir)
        _shared_copy_holder["path"] = tmp_dir
    return _shared_copy_holder["path"]


def _cleanup_shared_second_copy() -> None:
    path = _shared_copy_holder.get("path")
    if path is not None:
        shutil.rmtree(path, ignore_errors=True)
        _shared_copy_holder["path"] = None


atexit.register(_cleanup_shared_second_copy)


class TestHandedItsFilesChecksTolerateCarriedInWork(unittest.TestCase):
    """Every manifest entry recorded as handed-its-files must, when actually
    run as a process against a commit whose only trip-worthy content is
    carried in (not authored), raise no objection — the commit path hands it
    only the author's files, so carried-in content is never in its input.
    """

    def test_ge120e2i_handed_files_check_raises_no_objection_to_carried_in_work_MANUAL(
        self,
    ) -> None:
        # covers: GE-120e-2-i
        # angle: deployed
        """MANUAL: iterates every real handed-its-files entry (roughly fifty
        as of this AC's Implementation Notes) as a real subprocess against a
        real deployed second working copy — this deliberately exceeds the
        5s per-test budget rather than narrowing the subject list to stay
        fast (this AC's own Implementation Notes forbid the latter).

        Reads the handed-its-files complement from the REAL manifest via
        determine_change_set_sources(), builds (or reuses) one real second
        working copy via the harness's build.py deploy, stages a file that
        represents carried-in content the author never authored, runs every
        handed-its-files check as a process handing it ONLY the (empty)
        author file list — as the commit path actually would when the
        author wrote nothing — and asserts every one exits clean.
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
                "unit_tests.portability._deployed_check_harness does not exist "
                "yet — GE-120c-1's out-of-process harness has not landed. This "
                "test cannot execute checks as real subprocesses until it does."
            )

        result = determine_change_set_sources(_REAL_MANIFEST_PATH)
        handed_its_files = result.handed_its_files
        self.assertTrue(
            handed_its_files,
            "Expected at least one manifest entry recorded as "
            "change_set_source: handed_by_commit_path — none are recorded.",
        )

        copy_dir = _get_shared_second_copy()
        harness = _harness_mod.DeployedCheckHarness(_REPO_ROOT)
        harness.stage_files(
            copy_dir,
            {"unit_tests/portability/_ge120e2i_carried_in_fixture.py": "# carried-in, not authored\n"},
        )

        hooks_by_id = _read_manifest_hooks_by_id(_REAL_MANIFEST_PATH)
        report = _sweep(harness, copy_dir, hooks_by_id, handed_its_files, staged_files=[])

        # An objection is a check that RAN and found fault. A check that could
        # not run raised nothing — counting it here would conflate
        # could-not-check with objected, which is the exact confusion
        # GE-120a-1 exists to remove and which this sweep previously made.
        objections = [
            f"{check_id}: exit={outcome.exit_code} output={outcome.output.strip()[:300]!r}"
            for check_id, outcome in report.items()
            if outcome.exit_code != 0 and not _could_not_run(outcome)
        ]
        could_not_run = [
            check_id
            for check_id, outcome in report.items()
            if outcome.exit_code != 0 and _could_not_run(outcome)
        ]
        exercised = [
            check_id for check_id, outcome in report.items() if outcome.exit_code == 0
        ]

        # GE-120c-1-i: a sweep that exercised nothing must fail loudly rather
        # than report success over an empty subject set. Reporting zero
        # objections out of zero checks actually run is the vacuous pass this
        # tree forbids.
        self.assertTrue(
            exercised,
            "The sweep objected to nothing, but it also ran nothing: all "
            f"{len(report)} handed-its-files entries reported could-not-run "
            f"({', '.join(could_not_run)}). That is a broken fixture, not a "
            "clean result.",
        )

        self.assertEqual(
            [],
            objections,
            "Handed-its-files checks must raise no objection to carried-in "
            "content they were never handed (author wrote nothing). "
            f"{len(exercised)} entries ran and were clean; "
            f"{len(could_not_run)} could not run here and are excluded as "
            f"non-evidence ({', '.join(could_not_run)}). Real objections:\n"
            + "\n".join(objections),
        )


class TestSelfDemonstrationOfMisrecordedCheck(unittest.TestCase):
    """Self-demonstration is a deliverable (AC coverage note): plant a check
    whose manifest entry claims handed-its-files while it actually derives
    its own change set, and show this AC's own sweep both NAMES it and
    FAILS. A sweep that has never been observed to fail is not evidence.
    """

    def test_ge120e2i_misrecorded_check_is_named_and_the_sweep_fails(self) -> None:
        # covers: GE-120e-2-i
        # angle: failure
        """Write a fixture manifest with one entry recorded as
        change_set_source: "handed_by_commit_path" pointing at a planted
        check script that actually runs `git diff --cached` itself (see
        _write_planted_misrecorded_check). Confirm the determination
        discovers it as handed-its-files through the manifest (never a
        hard-coded id in the assertion). Stage carried-in trip-worthy
        content directly into the shared second copy's git index, run the
        planted check as a process handing it the (empty) author file list
        the commit path would hand it, and assert: it objects (non-zero
        exit) and the sweep's own report names the check together with the
        content objected to.
        """
        if not _DETERMINATION_OK or not _HARNESS_OK:
            self.fail(
                "Cannot demonstrate the sweep failing on a planted misrecorded "
                "check until both scripts.commit_guardian.change_set_source."
                "determine_change_set_sources (GE-120e-2) and "
                "unit_tests.portability._deployed_check_harness (GE-120c-1) exist."
            )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            planted_check = _write_planted_misrecorded_check(tmp_path)
            fixture_manifest = _write_fixture_manifest(
                tmp_path,
                hooks=[
                    {
                        "id": "check-planted-misrecorded",
                        "entry": f"python {planted_check}",
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

            copy_dir = _get_shared_second_copy()
            harness = _harness_mod.DeployedCheckHarness(_REPO_ROOT)
            harness.stage_files(
                copy_dir,
                {"unit_tests/ge120e2i_planted_carried_in.py": "# carried-in via staged tree\n"},
            )

            hooks_by_id = _read_manifest_hooks_by_id(fixture_manifest)
            report = _sweep(
                harness, copy_dir, hooks_by_id, ["check-planted-misrecorded"], staged_files=[]
            )
            outcome = report["check-planted-misrecorded"]

            self.assertNotEqual(
                0,
                outcome.exit_code,
                "Self-demonstration failed: the sweep must be able to fail on "
                "a check that claims handed-its-files while actually deriving "
                "its own diff. A sweep that has never been observed to fail "
                "is not evidence.",
            )
            named_report = f"check-planted-misrecorded: {outcome.output}"
            self.assertIn(
                "unit_tests/ge120e2i_planted_carried_in.py",
                named_report,
                "The sweep's report must name the content objected to, "
                "alongside the check id.",
            )


class TestSweepCoversTheDerivedComplement(unittest.TestCase):
    """The subject set is the complement, derived not listed: every manifest
    entry recorded as handed-its-files is swept, read from GE-120e-2's
    manifest reader at run time — no hand-written check list, no hard-coded
    entry count.
    """

    def test_ge120e2i_sweep_covers_every_handed_files_manifest_entry(self) -> None:
        # covers: GE-120e-2-i
        # angle: criterion
        """Two fixture manifests with DIFFERENT entry counts and different
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
        # angle: failure
        """Reuses the planted-misrecorded-check scenario, but asserts
        specifically on the THIRD required element: the state the objected
        content came in from ("state=staged-index", printed by the planted
        check itself), not merely the check name and the file name (covered
        separately by the self-demonstration test above). All three must be
        present together in one report this AC's own sweep can build.
        """
        if not _DETERMINATION_OK or not _HARNESS_OK:
            self.fail(
                "Cannot verify the three-part failure report until both "
                "scripts.commit_guardian.change_set_source."
                "determine_change_set_sources (GE-120e-2) and "
                "unit_tests.portability._deployed_check_harness (GE-120c-1) exist."
            )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            planted_check = _write_planted_misrecorded_check(tmp_path)
            fixture_manifest = _write_fixture_manifest(
                tmp_path,
                hooks=[
                    {
                        "id": "check-planted-misrecorded",
                        "entry": f"python {planted_check}",
                        "pass_filenames": True,
                        "change_set_source": "handed_by_commit_path",
                    }
                ],
            )
            determine_change_set_sources(fixture_manifest)  # discovery, as above

            copy_dir = _get_shared_second_copy()
            harness = _harness_mod.DeployedCheckHarness(_REPO_ROOT)
            harness.stage_files(
                copy_dir,
                {"unit_tests/ge120e2i_report_fixture.py": "# carried-in via staged tree\n"},
            )

            hooks_by_id = _read_manifest_hooks_by_id(fixture_manifest)
            report = _sweep(
                harness, copy_dir, hooks_by_id, ["check-planted-misrecorded"], staged_files=[]
            )
            outcome = report["check-planted-misrecorded"]
            named_report = f"check-planted-misrecorded: {outcome.output}"

            # 1. the check
            self.assertIn("check-planted-misrecorded", named_report)
            # 2. the content it objected to
            self.assertIn("unit_tests/ge120e2i_report_fixture.py", named_report)
            # 3. the state that content arrived from
            self.assertIn(
                "state=staged-index",
                named_report,
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
        # angle: failure
        """Point the harness's `create_second_copy` at a bogus `repo_root`
        (so its own `scripts/build.py` cannot be found) and assert it
        raises — never a silently-skipped case indistinguishable from
        "nothing to check here." A sweep that silently skips is
        indistinguishable from a sweep that passed.
        """
        if not _HARNESS_OK:
            self.fail(
                "unit_tests.portability._deployed_check_harness does not exist "
                "yet — GE-120c-1's out-of-process harness has not landed. The "
                "setup-failure reporting contract cannot be exercised until it "
                "does."
            )

        bogus_repo_root = Path(tempfile.gettempdir()) / "ge120e2i-bogus-repo-root-42"
        harness = _harness_mod.DeployedCheckHarness(bogus_repo_root)

        with tempfile.TemporaryDirectory() as tmp:
            target_dir = Path(tmp) / "second-copy"
            with self.assertRaises(Exception) as ctx:
                harness.create_second_copy(target_dir)

        self.assertNotIsInstance(
            ctx.exception,
            KeyboardInterrupt,
            "A setup failure must surface as a reported failure, never be "
            "swallowed into a bare pass/skip.",
        )


if __name__ == "__main__":
    unittest.main()
