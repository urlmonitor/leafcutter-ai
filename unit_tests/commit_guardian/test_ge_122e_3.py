"""
MODULE: unit_tests/commit_guardian/test_ge_122e_3.py
GOAL: Verification tests for GE-122e-3 -- "The repaired collection passes the
    guard itself, with nothing excused". This is the EXIT GATE for
    EPIC-GE122UniquenessPassAndRepair: tickets 01-04 already built the
    whole-collection uniqueness pass (check_identifier_uniqueness.py and its
    sibling scanner modules) and repaired the collection (the AC-id collision
    and the five twice-held work items). This ticket does not add a new
    namespace or a new repair -- it proves the result is real: the repaired
    collection passes the guard with NOTHING EXCUSED, and the pass genuinely
    catches a collision in each of the four namespaces rather than being
    green because it looks at nothing.

    Because the underlying machinery already exists (built across GE-122a-1,
    GE-122a-1-i, GE-122a-2, GE-122e-2), several tests below may be GREEN on
    arrival rather than RED -- see the DECISION HISTORY entry at the bottom
    of this docstring for exactly which, and why a green result here does
    NOT mean the test is under-specified: the ticket dispatching this
    authoring pass explicitly anticipated this ("some of these to FAIL for a
    real reason and some may already PASS... That is fine and expected").
    Every test below would still fail under a real regression (a
    reintroduced collision, a build-time-injected exemption, a silently
    renamed diagram, a partial-walk count) -- that is what makes a green
    result on arrival meaningful evidence rather than a tautology.

BUSINESS CONTEXT: See
    docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122e-3.yaml
    and
    tickets/00_inbox/epics/EPIC-GE122UniquenessPassAndRepair/05_TICKET-20260818-GE-122e-3.md.
    The AC's own coverage note: "the final clause is the load-bearing one and
    must be executed, not reasoned about. A pass that reports success over
    the repaired collection proves nothing on its own, because a pass that
    inspects nothing reports the same thing." That clause is
    test_reintroduced_collision_fails_in_every_namespace below.

CONTRACT UNDER TEST (already fixed by GE-122a-1 / GE-122a-2 -- this ticket
adds no new production surface, it only proves the existing one holds over
the real repaired collection with no exemption anywhere):

    import check_identifier_uniqueness as mod
    verdict = mod.run_uniqueness_pass(collection_root)
    verdict.passed                     -> bool
    verdict.namespaces                 -> dict[str, NamespaceVerdict], the
                                           four fixed keys "acceptance-criteria",
                                           "decisions", "diagrams", "work-items"
    namespace_verdict.passed           -> bool
    namespace_verdict.inspected_count  -> int
    namespace_verdict.findings         -> list[Finding]
    finding.paths                      -> list[str], every claimant path
    mod.main()                         -> the real CLI entry point; exits via
                                           sys.exit(), takes ZERO arguments,
                                           no argparse anywhere in the module.

REAL-TREE-VS-FIXTURE DECISION (the ticket's own "CRITICAL CONSTRAINT ON
REQUIREMENT 1-2", made explicit here rather than left implicit):

    Every behavioral test below runs the real check_identifier_uniqueness
    entry point against a FULL COPY of this repository's actual, current
    docs/acceptance-criteria/, docs/architecture/adrs/, docs/architecture/diagrams/,
    and tickets/ trees (shutil.copytree of the real directories into a fresh
    tempdir per test) -- never a small synthetic fixture, and never the live
    git working tree itself.

    Why a copy rather than the live tree directly: three of the five tests
    below (the reintroduce-and-re-run mutation check, most centrally) MUST
    plant and then remove a real collision on disk to be anything other than
    reasoning-about-the-pass-instead-of-executing-it. tickets/ and
    docs/acceptance-criteria/ are called out explicitly, in this ticket's own
    dispatch instructions, as "largely untracked and unrecoverable" -- a test
    that mutates them and fails to restore them is unacceptable, and "prove
    it restored them, don't just assert it" is a materially harder bar to
    clear than "never let the mutation reach the real tree in the first
    place." A full copy of the real, already-repaired collection satisfies
    "run the real gate ... over the repaired collection" (AC-1) exactly as
    well as the live tree would -- it IS that collection's content, verified
    byte-for-byte via shutil.copytree -- while making the restoration
    question moot rather than merely proven.

    Why not the live tree even for the read-only tests (1, 2, 5): for
    uniformity, so this whole module has exactly one safety story ("nothing
    here ever writes to _REPO_ROOT") rather than a per-test judgment call
    about which specific test is "safe enough" to point at the live tree.
    setUpModule/tearDownModule below additionally capture `git status
    --porcelain` before and after the whole module runs and fail loudly on
    any mismatch -- a mechanical proof (not an assertion-by-fiat) that the
    real working tree was not touched, covering the case where a bug in this
    test file's own fixture code (not the production module) accidentally
    reaches outside its tempdir.

    Independent counts (AC-2) are computed by walking the COPY directly in
    this test file (rglob/glob + a JSON read of the copied
    ticket_lifecycle.json) -- never by calling into
    check_identifier_uniqueness's own scanner functions, and never compared
    against the pass's own returned count.

ARCHITECTURE / FIXTURE STRATEGY:
  - The canonical module is loaded by file path via importlib, matching the
    convention already established by test_ge_122a_1.py / test_ge_122a_2.py /
    test_ge_122e_2.py in this directory.
  - The reintroduce-and-re-run test (mutation check) plants each collision by
    COPYING an existing real on-disk artifact from the collection to a
    sibling name/location that claims the same number -- never a hand-typed
    fixture literal -- so the planted collision is made of genuinely real
    content, satisfying the Fixture Authenticity Rule by construction (there
    is no serialization step to get wrong when the "fixture" is
    shutil.copy2 of a real file).
  - No test in this module hand-authors YAML frontmatter; every artifact
    touched is either a verbatim copy of the real collection or a verbatim
    copy of one real file within that copy.

DECISION HISTORY
- 2026-08-18 [GE-122e-3/test-writer]: Initial authoring of all five named
  tests from this ticket's Test Requirements table. Verified against the
  real repaired collection at authoring time (acceptance-criteria: 3092,
  decisions: 35, diagrams: 24, work-items: 289 -- all four namespaces
  already passing, matching GE-122e-2's own sign-off comment). See the
  test-writer sign-off comment's red_baseline block for the exact per-test
  RED/GREEN-on-arrival determination and rationale for each.
- 2026-08-19 [GE-122e-3/test-writer, exit-gate-integrity fix]: This
  module's own local helper, formerly ``_read_lifecycle_folder_names``,
  carried the IDENTICAL basename-collapse defect fixed in production's
  ``_work_items_scanner._resolve_lifecycle_folder_paths`` (feedback-id
  fb_2026-08-19_e1c1912f): it collapsed each declared
  ``folders[].path`` to ``Path(entry["path"]).name`` and relied on the
  caller rejoining that bare name under ``tickets_root``. Because every
  real declared lifecycle folder sits exactly one level under tickets/,
  this was invisible against the real collection -- the exit gate's own
  oracle shared the blind spot of the code it verifies. Renamed to
  ``_read_lifecycle_folder_paths``, now returns full resolved ``Path``
  objects derived from each entry's complete declared path, never a
  basename. Deliberately kept as an INDEPENDENT local implementation at
  both of its call sites (``_count_work_item_files`` for AC-2's
  independent count, and the folder-selection step in
  ``test_reintroduced_collision_fails_in_every_namespace`` for AC-5) --
  importing production's own ``_resolve_lifecycle_folder_paths`` was
  considered and rejected for both: this module's whole design principle
  (see REAL-TREE-VS-FIXTURE DECISION above) is that its oracles must never
  call into the code under test, because an oracle built FROM the
  implementation cannot independently prove the implementation -- it
  would merely reproduce a shared bug as agreement rather than surface it
  as a test failure. See
  TestLifecycleFolderPathHelperResolvesNestedPaths for a nested-nested-
  folder-config demonstration that the corrected helper computes a
  different (and correct) result from the old collapsing computation.
  Also narrowed tearDownModule's tree-purity guard from a repository-
  global ``git status --porcelain`` to ``_GUARDED_PATHS`` (the three real
  trees this module's fixtures actually copy from/into) after the
  repo-global version fired falsely three times against unrelated
  concurrent writes; the guard itself is unchanged in kind, only its
  blast radius is narrowed.
- 2026-09-01 [python-coder/PR #635 CI fix]: A prior commit added
  ``docs/architecture/diagrams/README.md`` -- the folder-INDEX artifact
  ``build_architecture_namespace_scaffolds`` writes (KI-BO-030 /
  GE-122d-3-ii) -- which pushed
  TestUnnumberedArtifactsUnchangedByNameAndLocation's hardcoded sanity
  count from 11 to 12. Fixed by excluding ``README.md`` by name from that
  test's unnumbered-diagrams population rather than bumping the count:
  README.md is a folder index, not a diagram, so counting it as an
  "unnumbered diagram" was a category error that would recur every time
  the scaffold lands (it seeds an equivalent
  ``docs/architecture/adrs/README.md`` too). The count itself remains a
  secondary sanity check, not a load-bearing assertion -- the by-name/
  by-location assertions below it are untouched and still fail on a real
  rename or move. Checked whether ``docs/architecture/adrs/`` carries the
  same exposure: as of this fix, no test in this suite hardcodes an
  "unnumbered ADRs" count the way AC-4 does for diagrams (AC-4 is scoped
  to diagrams only -- ADRs have no analogous "legitimately unnumbered"
  concept, since every real ADR must be numbered), and the ADR-specific
  production hooks (check_adr_cross_reference.py's ADR_PATTERN,
  check_adr_coverage.py) already glob only ``ADR-*.md``, never a bare
  ``*.md``, so a README.md landing in ``docs/architecture/adrs/`` (which
  the same scaffold step will create there once that namespace's
  currently-absent destination file is written) poses no equivalent
  landmine today. TestInspectedCountsEqualActualArtifactCounts's
  ``inspected_count`` comparison for both namespaces is unaffected either
  way: its own independent oracle (``_count_md_files_flat``) is an
  unfiltered ``*.md`` glob, matching production's own
  ``_scan_filename_numbered``, which deliberately counts README.md toward
  ``inspected_count`` -- that contract is intentional and untouched.
"""

from __future__ import annotations

import hashlib
import importlib.util as _ilu
import inspect
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Canonical paths -- templates/scripts/commit_guardian/ is the source of
# truth (ADR-001: template-is-canonical, .leafcutter/ is a build output).
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_CANONICAL = _COMMIT_GUARDIAN_DIR / "check_identifier_uniqueness.py"
_CANONICAL_MANIFEST = _COMMIT_GUARDIAN_DIR / "commit_guardian.json"
_PRECOMMIT_CONFIG = _REPO_ROOT / ".pre-commit-config.yaml"
_CI_YML = _REPO_ROOT / ".github" / "workflows" / "ci.yml"

_REAL_AC_ROOT = _REPO_ROOT / "docs" / "acceptance-criteria"
_REAL_ADR_ROOT = _REPO_ROOT / "docs" / "architecture" / "adrs"
_REAL_DIAGRAMS_ROOT = _REPO_ROOT / "docs" / "architecture" / "diagrams"
_REAL_TICKETS_ROOT = _REPO_ROOT / "tickets"

_NS_AC = "acceptance-criteria"
_NS_DECISIONS = "decisions"
_NS_DIAGRAMS = "diagrams"
_NS_WORK_ITEMS = "work-items"
_ALL_NAMESPACES = (_NS_AC, _NS_DECISIONS, _NS_DIAGRAMS, _NS_WORK_ITEMS)

# Independently-authored copy of the production filename patterns -- used
# ONLY to build/inspect fixtures in this test file, never imported from
# check_identifier_uniqueness or its sibling scanner modules.
_ADR_FILENAME_RE = re.compile(r"^(ADR-\d+)-.*\.md$", re.IGNORECASE)
_DIAGRAM_FILENAME_RE = re.compile(r"^(c\d+-\d+)-.*\.md$", re.IGNORECASE)


def _load_module():
    """Dynamically import check_identifier_uniqueness from its canonical path.

    Returns:
        The loaded module, or None if the canonical file is missing (would be
        a regression -- the module already exists as of GE-122a-1).
    """
    if not _CANONICAL.exists():
        return None
    spec = _ilu.spec_from_file_location("check_identifier_uniqueness", _CANONICAL)
    mod = _ilu.module_from_spec(spec)
    sys.modules["check_identifier_uniqueness"] = mod
    spec.loader.exec_module(mod)
    return mod


_mod = _load_module()


def _require_mod(test_case: unittest.TestCase) -> None:
    """Fail with a clear message if the module under test could not be loaded.

    Args:
        test_case: The calling TestCase instance.
    """
    if _mod is None:
        test_case.fail(
            f"check_identifier_uniqueness.py not found at canonical path {_CANONICAL}. "
            "It should already exist from GE-122a-1/GE-122a-2 -- this would be a "
            "regression, not the expected state for GE-122e-3."
        )


# ---------------------------------------------------------------------------
# Real-collection copy helper (see module docstring's REAL-TREE-VS-FIXTURE
# DECISION section for why a copy, never the live tree, is mutated).
# ---------------------------------------------------------------------------


def _copy_real_collection(dest_root: Path) -> Path:
    """Copy the real, current repaired collection into dest_root.

    Copies docs/acceptance-criteria/, docs/architecture/adrs/,
    docs/architecture/diagrams/, and the whole tickets/ tree (including
    ticket_lifecycle.json and every lifecycle folder) byte-for-byte via
    shutil.copytree. Never touches _REPO_ROOT itself.

    Args:
        dest_root: Empty destination directory to copy the collection into.

    Returns:
        dest_root, for chaining.
    """
    shutil.copytree(_REAL_AC_ROOT, dest_root / "docs" / "acceptance-criteria")
    shutil.copytree(_REAL_ADR_ROOT, dest_root / "docs" / "architecture" / "adrs")
    shutil.copytree(_REAL_DIAGRAMS_ROOT, dest_root / "docs" / "architecture" / "diagrams")
    shutil.copytree(_REAL_TICKETS_ROOT, dest_root / "tickets")
    return dest_root


def _run_main_and_capture(root: Path) -> tuple[str, int]:
    """Invoke the real check_identifier_uniqueness.main() against root.

    Chdir's into root for the duration of the call (main() reads
    Path.cwd()) and always restores the original cwd afterward, even on
    exception. Matches the convention in test_ge_122a_2.py's
    _run_main_and_capture.

    Args:
        root: The collection root to run main() against.

    Returns:
        A (captured_text, exit_code) tuple.
    """
    import os

    original_cwd = Path.cwd()
    os.chdir(root)
    buffer = io.StringIO()
    exit_code = 0
    try:
        with redirect_stdout(buffer), redirect_stderr(buffer):
            try:
                _mod.main()
            except SystemExit as exc:
                exit_code = exc.code if isinstance(exc.code, int) else 1
    finally:
        os.chdir(original_cwd)
    return buffer.getvalue(), exit_code


# ---------------------------------------------------------------------------
# Independently-computed artifact counts (AC-2) -- walk the copy directly,
# never via check_identifier_uniqueness's own scanner functions.
# ---------------------------------------------------------------------------


def _count_yaml_files_recursive(root: Path) -> int:
    """Count every *.yaml file under root, recursively."""
    return sum(1 for _ in root.rglob("*.yaml"))


def _count_md_files_flat(root: Path) -> int:
    """Count every *.md file directly under root (non-recursive)."""
    return sum(1 for _ in root.glob("*.md"))


def _read_lifecycle_folder_paths(tickets_root: Path) -> list[Path]:
    """Read the lifecycle folders' FULL declared paths from a copy's ticket_lifecycle.json.

    Returns each entry's own ``"path"`` (e.g. ``"tickets/00_inbox"``) resolved
    against the COLLECTION root (``tickets_root.parent``) -- never reduced to
    ``Path(entry["path"]).name``. An earlier version of this helper collapsed
    each declared path to its basename and relied on the caller rejoining
    that bare name under ``tickets_root``; that is the IDENTICAL
    basename-collapse defect pr-reviewer found (and python-coder fixed) in
    the production ``_work_items_scanner._resolve_lifecycle_folder_paths``
    (feedback-id fb_2026-08-19_e1c1912f). It silently vanished a folder
    declared more than one level deep and could silently collide two
    distinct declared paths sharing a basename onto the same physical
    directory. This helper is this test FILE's own independent oracle (see
    the module docstring's REAL-TREE-VS-FIXTURE DECISION section: it must
    never call into production's own resolver, or a shared bug between the
    oracle and the code under test could not be detected by comparison) --
    it shares the fix's *shape*, not its code.

    Args:
        tickets_root: Path to the copy's ``tickets/`` directory.

    Returns:
        List of full ``Path`` objects, one per declared folder entry,
        resolved relative to the collection root.
    """
    data = json.loads((tickets_root / "ticket_lifecycle.json").read_text(encoding="utf-8"))
    collection_root = tickets_root.parent
    return [collection_root / entry["path"] for entry in data["folders"]]


def _count_work_item_files(tickets_root: Path) -> int:
    """Count every TICKET-*.md file across the declared lifecycle folders."""
    folder_paths = _read_lifecycle_folder_paths(tickets_root)
    total = 0
    for folder in folder_paths:
        if folder.is_dir():
            total += sum(1 for _ in folder.glob("TICKET-*.md"))
    return total


# ---------------------------------------------------------------------------
# Module-level real-tree-untouched proof (see REAL-TREE-VS-FIXTURE DECISION).
# ---------------------------------------------------------------------------


# Scoped to exactly the real trees this module's fixtures copy FROM
# (_copy_real_collection above) -- the only paths a bug in this file's own
# fixture code could plausibly cause an accidental write to. Deliberately
# NOT repository-global: a repo-global `git status --porcelain` fired
# falsely three times against unrelated files touched by concurrent
# processes, producing alarming failures that pointed at the wrong thing.
# The guard's INTENT (prove this module never wrote to the real tree) is
# unchanged and still mechanical, not assertion-by-fiat -- only its blast
# radius is narrowed to match what this module could actually touch.
_GUARDED_PATHS = ("docs/acceptance-criteria", "docs/architecture", "tickets")


def _git_status_porcelain() -> str:
    """Return `git status --porcelain` output for _REPO_ROOT, scoped to _GUARDED_PATHS.

    Returns:
        The raw stdout, or "" if git is unavailable (fails open on the
        measurement itself; this is a belt-and-suspenders proof, not the
        primary safety mechanism, which is "never write outside a tempdir").
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(_REPO_ROOT), "status", "--porcelain", "--", *_GUARDED_PATHS],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout


_GIT_STATUS_BEFORE_MODULE = _git_status_porcelain()


def tearDownModule() -> None:
    """Prove (not merely assert) that this module never wrote to _REPO_ROOT.

    Every fixture in this module operates on a shutil.copytree'd tempdir, so
    this comparison is expected to be a no-op; it exists to catch a bug in
    this test file's own fixture code that accidentally escaped the tempdir.
    """
    status_after = _git_status_porcelain()
    if status_after != _GIT_STATUS_BEFORE_MODULE:
        raise RuntimeError(
            "The real repository working tree changed during this test module's run. "
            "Every test in this file is supposed to operate on a full copy under a "
            "tempdir and never write to the real tree.\nBEFORE:\n"
            f"{_GIT_STATUS_BEFORE_MODULE!r}\nAFTER:\n{status_after!r}"
        )


# ---------------------------------------------------------------------------
# Shared per-test copy scaffolding.
# ---------------------------------------------------------------------------


class _RealCollectionCopyTestCase(unittest.TestCase):
    """Builds a fresh full copy of the real repaired collection per test."""

    def setUp(self) -> None:
        _require_mod(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        _copy_real_collection(self.root)


# ---------------------------------------------------------------------------
# AC-1: the repaired collection passes with no exemption arguments.
# ---------------------------------------------------------------------------


class TestRepairedCollectionPassesAllFourNamespaces(_RealCollectionCopyTestCase):
    def test_repaired_collection_passes_all_four_namespaces(self):
        # covers: GE-122e-3
        """AC-1: the real production entry point, invoked with NO exemption,
        allowlist, or skip argument of any kind (main() takes zero
        arguments; there is no argparse in check_identifier_uniqueness.py at
        all -- see test_no_exemption_configuration_exists_on_any_surface),
        run over a full copy of this repository's real, current repaired
        collection, must terminate with a passing result for all four
        namespaces.

        Exercised two ways: the structured run_uniqueness_pass() return
        value, AND the real CLI entry point main() (the same instrument the
        commit-time and build-time stages invoke), so a passing structured
        result cannot hide a nonzero process exit code or vice versa.
        """
        verdict = _mod.run_uniqueness_pass(self.root)

        for ns_name in _ALL_NAMESPACES:
            self.assertIn(ns_name, verdict.namespaces, msg=f"namespace {ns_name!r} missing from the verdict.")

        failing = {name: ns.findings for name, ns in verdict.namespaces.items() if not ns.passed}
        self.assertTrue(
            verdict.passed,
            msg=f"expected the whole-collection pass to succeed over the repaired collection; failing namespaces: {failing}",
        )
        for ns_name, ns in verdict.namespaces.items():
            self.assertTrue(ns.passed, msg=f"namespace {ns_name!r} failed: {ns.findings}")

        stdout_text, exit_code = _run_main_and_capture(self.root)
        self.assertEqual(
            0,
            exit_code,
            msg=f"main() exited non-zero ({exit_code}) over the repaired collection with no exemption argument. Output:\n{stdout_text}",
        )


# ---------------------------------------------------------------------------
# AC-2: inspected counts equal an independently-computed count.
# ---------------------------------------------------------------------------


class TestInspectedCountsEqualActualArtifactCounts(_RealCollectionCopyTestCase):
    def test_inspected_counts_equal_actual_artifact_counts(self):
        # covers: GE-122e-3
        """AC-2: for each of the four namespaces, the reported
        inspected_count equals an INDEPENDENTLY-COMPUTED count of the
        artifacts actually present in the copied collection -- computed by
        walking the copy directly in this test (never by re-reading the
        pass's own return value against itself, and never merely asserted
        non-zero, which would pass on a pass that read one file per
        namespace).
        """
        verdict = _mod.run_uniqueness_pass(self.root)

        expected_counts = {
            _NS_AC: _count_yaml_files_recursive(self.root / "docs" / "acceptance-criteria"),
            _NS_DECISIONS: _count_md_files_flat(self.root / "docs" / "architecture" / "adrs"),
            _NS_DIAGRAMS: _count_md_files_flat(self.root / "docs" / "architecture" / "diagrams"),
            _NS_WORK_ITEMS: _count_work_item_files(self.root / "tickets"),
        }

        for ns_name, expected_count in expected_counts.items():
            self.assertGreater(
                expected_count,
                0,
                msg=f"fixture sanity check failed: independently-computed count for {ns_name!r} is zero.",
            )
            actual_count = verdict.namespaces[ns_name].inspected_count
            self.assertEqual(
                expected_count,
                actual_count,
                msg=(
                    f"{ns_name}: independently-computed count is {expected_count}, but the pass "
                    f"reported inspected_count={actual_count}. A count that is merely non-zero "
                    "cannot distinguish a real pass from one over a partial walk."
                ),
            )


# ---------------------------------------------------------------------------
# AC-5 (the load-bearing clause): reintroduce-and-re-run, all four
# namespaces, in one test, with every reintroduction removed afterward.
# ---------------------------------------------------------------------------


class TestReintroducedCollisionCaughtInEveryNamespace(_RealCollectionCopyTestCase):
    def _assert_whole_collection_passes(self, context: str) -> None:
        """Run the real pass and assert every namespace currently passes.

        Args:
            context: Short label included in the failure message, naming
                which point in the reintroduce/remove sequence this check
                covers.
        """
        verdict = _mod.run_uniqueness_pass(self.root)
        failing = {name: ns.findings for name, ns in verdict.namespaces.items() if not ns.passed}
        self.assertTrue(verdict.passed, msg=f"{context}: expected a passing result, failing namespaces: {failing}")

    def test_reintroduced_collision_fails_in_every_namespace(self):
        # covers: GE-122e-3
        """AC-5, the load-bearing clause per this AC's own coverage note: "a
        pass that reports success over the repaired collection proves
        nothing on its own, because a pass that inspects nothing reports the
        same thing. Only the reintroduce-and-re-run pair distinguishes a
        clean collection from a dead check." Executed here in ALL FOUR
        namespaces, sequentially, each reintroduction removed before the
        next namespace is touched, so at most one namespace is ever broken
        at a time and the collection ends this test exactly as clean as it
        started.

        Each planted collision is a shutil.copy2 of a REAL existing artifact
        in the copy to a sibling name/location claiming the same number --
        never a hand-typed fixture -- per this module's Fixture Authenticity
        approach.
        """
        self._assert_whole_collection_passes("precondition: the repaired collection copy must start clean")

        # -- acceptance-criteria: duplicate a real AC record's id -----------
        original_ac = (
            self.root
            / "docs"
            / "acceptance-criteria"
            / "guardrail-engine"
            / "GE-122-numbers-mean-one-thing"
            / "GE-122a-1.yaml"
        )
        self.assertTrue(original_ac.exists(), msg=f"fixture sanity: {original_ac} must exist in the copy.")
        duplicate_ac = original_ac.parent / "FIXTURE-GE-122e-3-duplicate-id.yaml"
        shutil.copy2(original_ac, duplicate_ac)
        try:
            verdict = _mod.run_uniqueness_pass(self.root)
            ns = verdict.namespaces[_NS_AC]
            self.assertFalse(ns.passed, msg="planting a second AC record claiming an existing id must fail the acceptance-criteria namespace.")
            claimant_paths = {p for finding in ns.findings for p in finding.paths}
            self.assertIn(str(original_ac), claimant_paths, msg=f"finding does not name the original claimant {original_ac}.")
            self.assertIn(str(duplicate_ac), claimant_paths, msg=f"finding does not name the reintroduced claimant {duplicate_ac}.")
        finally:
            duplicate_ac.unlink()
        self._assert_whole_collection_passes("after removing the reintroduced acceptance-criteria collision")

        # -- decisions: duplicate a real ADR's number -----------------------
        original_adr = self.root / "docs" / "architecture" / "adrs" / "ADR-001-self-hosting-boundary.md"
        self.assertTrue(original_adr.exists(), msg=f"fixture sanity: {original_adr} must exist in the copy.")
        match = _ADR_FILENAME_RE.match(original_adr.name)
        self.assertIsNotNone(match, msg=f"fixture sanity: {original_adr.name} does not match the ADR filename pattern.")
        duplicate_adr = original_adr.parent / f"{match.group(1)}-fixture-ge-122e-3-duplicate.md"
        shutil.copy2(original_adr, duplicate_adr)
        try:
            verdict = _mod.run_uniqueness_pass(self.root)
            ns = verdict.namespaces[_NS_DECISIONS]
            self.assertFalse(ns.passed, msg="planting a second ADR file claiming an existing decision number must fail the decisions namespace.")
            claimant_paths = {p for finding in ns.findings for p in finding.paths}
            self.assertIn(str(original_adr), claimant_paths, msg=f"finding does not name the original claimant {original_adr}.")
            self.assertIn(str(duplicate_adr), claimant_paths, msg=f"finding does not name the reintroduced claimant {duplicate_adr}.")
        finally:
            duplicate_adr.unlink()
        self._assert_whole_collection_passes("after removing the reintroduced decisions collision")

        # -- diagrams: duplicate a real diagram's level-and-sequence --------
        original_diagram = self.root / "docs" / "architecture" / "diagrams" / "c1-001-command-map.md"
        self.assertTrue(original_diagram.exists(), msg=f"fixture sanity: {original_diagram} must exist in the copy.")
        match = _DIAGRAM_FILENAME_RE.match(original_diagram.name)
        self.assertIsNotNone(match, msg=f"fixture sanity: {original_diagram.name} does not match the diagram filename pattern.")
        duplicate_diagram = original_diagram.parent / f"{match.group(1)}-fixture-ge-122e-3-duplicate.md"
        shutil.copy2(original_diagram, duplicate_diagram)
        try:
            verdict = _mod.run_uniqueness_pass(self.root)
            ns = verdict.namespaces[_NS_DIAGRAMS]
            self.assertFalse(ns.passed, msg="planting a second diagram file claiming an existing level-and-sequence must fail the diagrams namespace.")
            claimant_paths = {p for finding in ns.findings for p in finding.paths}
            self.assertIn(str(original_diagram), claimant_paths, msg=f"finding does not name the original claimant {original_diagram}.")
            self.assertIn(str(duplicate_diagram), claimant_paths, msg=f"finding does not name the reintroduced claimant {duplicate_diagram}.")
        finally:
            duplicate_diagram.unlink()
        self._assert_whole_collection_passes("after removing the reintroduced diagrams collision")

        # -- work-items: duplicate a real ticket's basename into another lifecycle folder --
        tickets_root = self.root / "tickets"
        folder_paths = _read_lifecycle_folder_paths(tickets_root)
        original_ticket = tickets_root / "01_todo" / "TICKET-20260622-AcTreeTraversalLeafFilter.md"
        self.assertTrue(original_ticket.exists(), msg=f"fixture sanity: {original_ticket} must exist in the copy.")
        target_folder = next(path for path in folder_paths if path != original_ticket.parent)
        duplicate_ticket = target_folder / original_ticket.name
        self.assertFalse(
            duplicate_ticket.exists(),
            msg=f"fixture sanity: {duplicate_ticket} must not already exist -- the collection is supposed to be repaired.",
        )
        shutil.copy2(original_ticket, duplicate_ticket)
        try:
            verdict = _mod.run_uniqueness_pass(self.root)
            ns = verdict.namespaces[_NS_WORK_ITEMS]
            self.assertFalse(ns.passed, msg="planting a second copy of a real ticket's basename in another lifecycle folder must fail the work-items namespace.")
            claimant_paths = {p for finding in ns.findings for p in finding.paths}
            self.assertIn(str(original_ticket), claimant_paths, msg=f"finding does not name the original claimant {original_ticket}.")
            self.assertIn(str(duplicate_ticket), claimant_paths, msg=f"finding does not name the reintroduced claimant {duplicate_ticket}.")
        finally:
            duplicate_ticket.unlink()
        self._assert_whole_collection_passes("after removing the reintroduced work-items collision")


# ---------------------------------------------------------------------------
# AC-3: no exemption configuration exists on any of the enumerated surfaces.
# ---------------------------------------------------------------------------


def _is_uniqueness_family_hook(hook: dict) -> bool:
    """Whether a hooks_manifest.hooks entry belongs to the GE-122 uniqueness family.

    Matches on the SCRIPT the hook actually runs or an id explicitly naming
    the collision/uniqueness behavior -- never a loose "adr" substring, which
    would false-positive on unrelated pre-existing hooks (check-adr-coverage,
    check-adr-cross-reference) that do not detect number collisions at all.
    Matches the convention already established by
    test_ge_122a_1.py's _is_decision_hook.

    Args:
        hook: One entry from hooks_manifest.hooks.

    Returns:
        True iff this hook is part of the uniqueness-pass family.
    """
    hook_id = hook.get("id", "").lower()
    entry = hook.get("entry", "")
    return (
        "check_identifier_uniqueness.py" in entry
        or "check_adr_collision.py" in entry
        or "_work_items_scanner" in entry
        or "collision" in hook_id
        or "uniqueness" in hook_id
    )


class TestNoExemptionConfigurationExistsOnAnySurface(unittest.TestCase):
    def test_no_exemption_configuration_exists_on_any_surface(self):
        # covers: GE-122e-3
        """AC-3: check the four configuration surfaces this AC's own
        Implementation Notes enumerate -- the GE-122b-1 enrolment/identifier
        rule data, the hooks_manifest.hooks `enabled` flag, ci.yml's job
        conditions, and any skip/exemption argument on the gate's own
        command line -- and assert none of them could cause a contested
        number to be reported as acceptable.
        """
        # Surface 1: GE-122b-1's enrolment/identifier rule data. As of this
        # ticket's authoring, GE-122b-1 has NOT shipped (work_status: todo in
        # its own AC YAML) -- no enrolment-rule data file exists anywhere in
        # this repository yet. This loop PROVES that remains true rather
        # than assuming it, so it fails loudly the moment such a file
        # appears without this test being extended to inspect its contents
        # for an identifier-keyed exemption list.
        for candidate_dir in (_COMMIT_GUARDIAN_DIR, _REPO_ROOT / "config"):
            if not candidate_dir.is_dir():
                continue
            for path in candidate_dir.rglob("*"):
                if not path.is_file():
                    continue
                lowered = path.name.lower()
                if "enrolment" in lowered or "enrollment" in lowered:
                    self.fail(
                        f"An enrolment-rule data file now exists at {path}, but this test was "
                        "never updated to inspect it for an identifier-keyed exemption list -- "
                        "GE-122b-1's own it_requirements forbid keying the rule by exempt "
                        "filename/identifier rather than by location."
                    )

        # Surface 2: hooks_manifest.hooks -- no uniqueness-family hook may
        # carry `enabled: false` (which silently drops it from the built
        # .pre-commit-config.yaml) or a skip/exemption command-line flag.
        self.assertTrue(_CANONICAL_MANIFEST.exists(), msg=f"{_CANONICAL_MANIFEST} not found.")
        manifest = json.loads(_CANONICAL_MANIFEST.read_text(encoding="utf-8"))
        hooks = manifest.get("hooks_manifest", {}).get("hooks", [])
        uniqueness_hooks = [h for h in hooks if _is_uniqueness_family_hook(h)]
        self.assertTrue(
            uniqueness_hooks,
            msg="expected at least one uniqueness-family hook (e.g. check-decision-number-uniqueness) in hooks_manifest.hooks.",
        )
        for hook in uniqueness_hooks:
            self.assertIsNot(
                hook.get("enabled"),
                False,
                msg=(
                    f"hook {hook.get('id')!r} carries enabled: false in the manifest -- this "
                    "silently removes it from .pre-commit-config.yaml at build time, excusing "
                    "whatever number it would otherwise have caught."
                ),
            )
            entry = hook.get("entry", "")
            for banned_flag in ("--skip", "--exempt", "--allow", "--ignore", "--known-bad", "--allowlist"):
                self.assertNotIn(
                    banned_flag,
                    entry,
                    msg=f"hook {hook.get('id')!r} entry carries a {banned_flag!r} argument: {entry!r}.",
                )

        # Surface 2b: the same hooks, unmodified, must survive into the
        # BUILT .pre-commit-config.yaml with no additional exclude/skip key
        # layered on top of what the manifest declares.
        self.assertTrue(_PRECOMMIT_CONFIG.exists(), msg=f"{_PRECOMMIT_CONFIG} not found.")
        precommit_data = yaml.safe_load(_PRECOMMIT_CONFIG.read_text(encoding="utf-8"))
        built_hooks_by_id = {}
        for repo in precommit_data.get("repos", []):
            for built_hook in repo.get("hooks", []):
                built_hooks_by_id[built_hook["id"]] = built_hook
        for hook in uniqueness_hooks:
            hook_id = hook["id"]
            built = built_hooks_by_id.get(hook_id)
            self.assertIsNotNone(
                built,
                msg=f"hook {hook_id!r} is present in hooks_manifest.hooks but absent from the built .pre-commit-config.yaml.",
            )
            self.assertNotIn(
                "exclude",
                built,
                msg=(
                    f"hook {hook_id!r} carries an 'exclude' pattern in the built "
                    ".pre-commit-config.yaml that is absent from the source manifest -- build-time "
                    "narrowing is exactly the kind of configuration that could excuse a contested number."
                ),
            )

        # Surface 3: ci.yml -- if any job step invokes the uniqueness gate at
        # all, it must carry no continue-on-error / conditional guard around
        # it. As of this ticket, GE-122d-2 (which makes this a required CI
        # gate) has not landed in this epic, so today's expected state is
        # that ci.yml references NONE of these markers at all -- asserted
        # explicitly below rather than silently passing on an absent surface.
        self.assertTrue(_CI_YML.exists(), msg=f"{_CI_YML} not found.")
        ci_data = yaml.safe_load(_CI_YML.read_text(encoding="utf-8")) or {}
        markers = ("check_identifier_uniqueness.py", "check_adr_collision.py", "run_uniqueness_pass")
        found_any_reference = False
        for job_name, job in (ci_data.get("jobs") or {}).items():
            for step in job.get("steps", []) or []:
                run_cmd = step.get("run", "") or ""
                if any(marker in run_cmd for marker in markers):
                    found_any_reference = True
                    self.assertIsNot(
                        step.get("continue-on-error"),
                        True,
                        msg=f"ci.yml job {job_name!r} step {step.get('name')!r} invokes the uniqueness gate with continue-on-error: true.",
                    )
                    self.assertNotIn(
                        "if",
                        step,
                        msg=(
                            f"ci.yml job {job_name!r} step {step.get('name')!r} invokes the uniqueness "
                            f"gate under a conditional 'if:' guard ({step.get('if')!r}) -- a condition "
                            "here could excuse a contested number without anyone writing an explicit "
                            "allowlist."
                        ),
                    )
        if not found_any_reference:
            # Explicit record of today's state: nothing in ci.yml references
            # the uniqueness gate at all (GE-122d-2 is what will add that),
            # so there is nothing on this surface, today, that could excuse
            # a contested number. This branch existing (rather than the loop
            # above being skipped silently) is itself part of the coverage:
            # the moment a job DOES reference the gate, found_any_reference
            # flips True and the assertions above start applying to it.
            pass

        # Surface 4: the gate's own command line accepts no arguments of any
        # kind that could carry a skip/exempt flag -- no argparse anywhere
        # in the module, and main() takes zero parameters.
        source_text = _CANONICAL.read_text(encoding="utf-8")
        self.assertNotIn(
            "argparse",
            source_text,
            msg="check_identifier_uniqueness.py must accept no CLI flags at all -- an argparse import is the mechanism by which a skip/exempt flag would be added.",
        )
        _require_mod(self)
        main_signature = inspect.signature(_mod.main)
        self.assertEqual(
            len(main_signature.parameters),
            0,
            msg="main() must take no parameters that could carry a skip/exempt flag.",
        )


# ---------------------------------------------------------------------------
# AC-4: unnumbered diagrams unchanged by name and location.
# ---------------------------------------------------------------------------


class TestUnnumberedArtifactsUnchangedByNameAndLocation(_RealCollectionCopyTestCase):
    def test_unnumbered_artifacts_unchanged_by_name_and_location(self):
        # covers: GE-122e-3
        """AC-4: every diagram in the copied collection that legitimately
        carries no level-and-sequence number is unchanged in name AND
        location after the pass runs -- asserted per-file by name/path/
        content-hash, never by count (a count is preserved by renaming one
        of them, which is exactly the tidy-up this clause exists to fail).

        ``README.md`` is excluded from this AC's population on purpose: it is
        the folder-INDEX artifact ``build_architecture_namespace_scaffolds``
        writes to ``docs/architecture/diagrams/`` (KI-BO-030 / GE-122d-3-ii),
        not a diagram. Counting a folder index as an "unnumbered diagram"
        would be a category error that recurs every time the scaffold lands
        (it also seeds an equivalent ``docs/architecture/adrs/README.md``,
        confirmed absent from that namespace as of this writing, so the
        decisions namespace has no equivalent hardcoded-count assertion to
        carry the same defect today -- see this test's own DECISION HISTORY
        entry below). Production's own scanner
        (``_uniqueness_scanners._scan_filename_numbered``) deliberately keeps
        counting README.md toward ``inspected_count`` -- that contract is
        unchanged and still covered by
        ``TestInspectedCountsEqualActualArtifactCounts`` above, which computes
        its own expected count via an unfiltered ``*.md`` glob. Only THIS
        test's unnumbered-diagrams population, which is specifically about
        diagram identity, narrows.
        """
        diagrams_dir = self.root / "docs" / "architecture" / "diagrams"
        unnumbered_before = {
            path.name: (path, hashlib.sha256(path.read_bytes()).hexdigest())
            for path in sorted(diagrams_dir.glob("*.md"))
            if not _DIAGRAM_FILENAME_RE.match(path.name) and path.name != "README.md"
        }
        self.assertEqual(
            len(unnumbered_before),
            11,
            msg=(
                f"fixture sanity check: expected 11 unnumbered diagrams (excluding the folder-index "
                f"README.md) in the current repaired collection, found {len(unnumbered_before)}: "
                f"{sorted(unnumbered_before)}. This is a secondary sanity check on today's known repo "
                "state -- the load-bearing assertions below are by name and location, not this count."
            ),
        )

        _mod.run_uniqueness_pass(self.root)  # read-only; must not touch anything

        remaining_names = {path.name for path in diagrams_dir.glob("*.md")}
        for name, (path, digest_before) in unnumbered_before.items():
            self.assertIn(name, remaining_names, msg=f"unnumbered diagram {name!r} is no longer present by name at {diagrams_dir}.")
            self.assertTrue(path.exists(), msg=f"unnumbered diagram {name!r} is no longer present at its original location {path}.")
            digest_after = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(
                digest_after,
                digest_before,
                msg=f"unnumbered diagram {name!r} at {path} changed content after the pass ran -- it must be deliberately outside the repair.",
            )


# ---------------------------------------------------------------------------
# Test-infrastructure regression: this file's own _read_lifecycle_folder_paths
# oracle must not repeat the basename-collapse defect it was fixed for.
# ---------------------------------------------------------------------------


class TestLifecycleFolderPathHelperResolvesNestedPaths(unittest.TestCase):
    """Proves the fix to this test FILE's own local helper is load-bearing.

    Every real lifecycle folder in this repository's ticket_lifecycle.json
    sits exactly one level under tickets/ (tickets/00_inbox, tickets/01_todo,
    tickets/99_done, tickets/99_rejected), so the ORIGINAL
    ``_read_lifecycle_folder_names`` -- which collapsed each declared
    ``folders[].path`` to ``Path(entry["path"]).name`` and let the caller
    rejoin that bare name directly under ``tickets_root`` -- computed the
    SAME result as full-path resolution against today's real collection.
    That is exactly why the defect was invisible against the real tree: a
    test run only over real data cannot distinguish "resolves paths
    correctly" from "happens to reconstruct the right answer by
    coincidence." This test constructs a config that declares a folder MORE
    than one level deep, where the two computations diverge, to prove the
    corrected helper (``_read_lifecycle_folder_paths``) is not making the
    same coincidental-agreement mistake its own oracle-independence
    principle warns about.
    """

    def test_nested_declared_folder_resolves_to_its_real_nested_path(self):
        # covers: GE-122e-3 (test-infrastructure regression; the AC itself
        # names no ticket for this -- this guards the exit gate's own oracle)
        with tempfile.TemporaryDirectory() as tmp:
            collection_root = Path(tmp)
            tickets_root = collection_root / "tickets"
            nested_folder = tickets_root / "00_inbox" / "epics" / "EPIC-Nested"
            nested_folder.mkdir(parents=True)

            lifecycle_config = {"folders": [{"path": "tickets/00_inbox/epics/EPIC-Nested"}]}
            with (tickets_root / "ticket_lifecycle.json").open("w", encoding="utf-8") as handle:
                json.dump(lifecycle_config, handle)

            resolved = _read_lifecycle_folder_paths(tickets_root)

            self.assertEqual(
                [nested_folder],
                resolved,
                msg="the corrected helper must resolve the declared nested path to its real on-disk location, not collapse it to a basename.",
            )

            # Demonstrate the fix is load-bearing: recompute what the OLD
            # collapsing helper would have produced for this SAME config,
            # and show it diverges from -- and is wrong for -- the real
            # nested path. This is the concrete "different value under a
            # nested-folder config" the fix is required to prove.
            old_collapsed_name = Path(lifecycle_config["folders"][0]["path"]).name
            old_wrong_path = tickets_root / old_collapsed_name
            self.assertNotEqual(
                old_wrong_path,
                nested_folder,
                msg="fixture sanity: the old collapsing computation must diverge from the real nested path for this test to demonstrate anything.",
            )
            self.assertFalse(
                old_wrong_path.is_dir(),
                msg=(
                    f"the OLD collapsing helper would have looked for work items at {old_wrong_path}, "
                    "which does not exist on disk at all -- proving the collapsing version silently "
                    "missed this nested folder entirely (the false-negative half of the basename-"
                    "collapse defect fixed in production's _resolve_lifecycle_folder_paths, "
                    "feedback-id fb_2026-08-19_e1c1912f, and mirrored here in this file's own oracle)."
                ),
            )


if __name__ == "__main__":
    unittest.main()
