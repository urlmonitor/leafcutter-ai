"""
MODULE: unit_tests/commit_guardian/test_ge_122a_2_lifecycle_folder_paths.py
GOAL: Regression tests for the lifecycle-folder-path bug found by pr-reviewer
    (feedback-id fb_2026-08-19_e1c1912f) in
    templates/scripts/commit_guardian/_work_items_scanner.py.

WHY A SIBLING FILE, NOT test_ge_122a_2.py: that file is already 801 lines
    covering the whole-collection "work-items" namespace end-to-end
    (contested pairs, uncontested singles, epic-sub-item false-positive
    guard, inspected_count, the emitted report, a repo-scale integration
    fixture). This module owns exactly one additional, narrower concern --
    whether the lifecycle folder LIST ITSELF is resolved correctly when a
    declared folder path is nested more than one level under tickets/, or
    when two distinct declared paths happen to share a basename -- so it is
    kept separate rather than pushed further past that file's existing
    size, per this ticket's own instruction to prefer a sibling module when
    the primary file is large (mirroring the
    test_ge_122a_1_fast_path_equivalence.py precedent already established
    in this directory for the sibling GE-122a-1 AC).

THE BUG (found by pr-reviewer, confirmed live 2026-08-19, see ticket
    03_TICKET-20260818-GE-122a-2.md's pr-reviewer sign-off comment):
    ``_read_lifecycle_folder_names`` in _work_items_scanner.py collapses
    every configured folder path to ``Path(entry["path"]).name`` --
    its LAST path component only -- before the caller rejoins that bare
    name under ``tickets_root``. Every parent segment beyond the last is
    discarded. This works today only because every folder currently
    declared in tickets/ticket_lifecycle.json happens to sit exactly one
    level under tickets/ (00_inbox, 01_todo, 99_done, 99_rejected), so
    ``.name`` happens to reconstruct the correct path by coincidence -- but
    the file's own ``_extensibility_guide`` field explicitly invites
    appending arbitrary custom folder entries, including nested ones.

    TWO FAILURE MODES, both silent:
      1. FALSE NEGATIVE (TestNestedLifecycleFolderCrossFolderDuplicate
         below): a folder declared at a NESTED path (e.g.
         "tickets/00_inbox/archive") collapses to "archive", which is then
         rejoined as tickets_root/"archive" -- a directory that does not
         exist. The folder is silently skipped: a real cross-folder
         duplicate held partly inside it is never seen, the namespace
         reports passed=True, and inspected_count is short by exactly the
         missed files.
      2. FALSE POSITIVE (TestSharedBasenameDistinctFoldersNoCollision
         below): two DISTINCT declared paths that happen to share a
         basename (e.g. "tickets/00_inbox" and
         "tickets/archive_area/00_inbox") both collapse to "00_inbox", so
         the walk visits the SAME physical directory (tickets_root/
         "00_inbox") twice instead of visiting each declared location once
         -- every real file in that one directory is walked twice and
         reported as if two different lifecycle folders held it, while the
         genuinely different content under the second declared path is
         never inspected at all.

BUSINESS CONTEXT: this module is a COLLISION DETECTOR
    (check_identifier_uniqueness.run_uniqueness_pass's "work-items"
    namespace). A collision detector that silently drops a real collision
    (failure mode 1) or manufactures a spurious one out of a single
    uniquely-held file (failure mode 2) is precisely the failure class
    GE-122 exists to eliminate -- the sibling GE-122a-1 ticket's own
    Master_Plan.md names "a false green in a duplicate detector" as the
    worst possible outcome for this epic.

FIXTURE AUTHENTICITY (per docs/reference/fixture-policy.md, and this
    repo's CLAUDE.md "Real-artifact behavioral spot-check" convention):
    ticket_lifecycle.json fixtures are never hand-typed. Each test starts
    from ``json.loads`` of the REAL on-disk tickets/ticket_lifecycle.json,
    deep-copies the folder entries it needs, mutates only the ``path``
    field programmatically, and writes the result back out via
    ``json.dump`` -- never a Python dict literal typed fresh, and never an
    indented/hand-formatted JSON string. The regression-anchor test
    (TestFlatLayoutRegressionAnchor) instead installs the real file
    BYTE-FOR-BYTE via ``shutil.copy2``, matching test_ge_122a_2.py's own
    convention for the unmodified-shape case. Ticket frontmatter is written
    via ``yaml.safe_dump``, never a hand-typed "status: X" string -- a
    hand-typed literal reproduces the author's formatting bias rather than
    the real serializer's column-0 output, the exact defect class that hid
    the files_touched parser bug in EPIC-PhantomDoneFilesTouched.

    Every test's "true" inspected/collision count is computed
    INDEPENDENTLY in the test itself, by joining ``root`` directly with
    each folder entry's own ``path`` field (the full relative path, never
    reduced to a basename) -- this is deliberately NOT a call into any
    helper inside _work_items_scanner.py, so a shared bug between the
    oracle and the code under test cannot hide from the comparison.

ARCHITECTURE / EXERCISE STRATEGY:
  - The module under test, _work_items_scanner.py, is imported by its real
    top-level name via importlib.import_module after inserting
    templates/scripts/commit_guardian/ onto sys.path -- required because it
    uses a plain sibling import (``from _uniqueness_types import ...``)
    rather than a package-relative one, mirroring the sys.path bootstrap
    check_identifier_uniqueness.py performs on itself and the convention
    test_ge_122a_1_fast_path_equivalence.py already uses for
    _uniqueness_scanners.py.
  - Tests call ``scan_work_items(tickets_root, lifecycle_config_path)``
    directly (the function whose caller, ``_read_lifecycle_folder_names``,
    contains the bug) rather than routing through
    ``check_identifier_uniqueness.run_uniqueness_pass`` -- this ticket's
    TARGET names _work_items_scanner.py specifically, and a direct call
    keeps each fixture minimal (no need to also scaffold
    docs/acceptance-criteria/, docs/architecture/adrs/, or
    docs/architecture/diagrams/ just to exercise this one namespace).

DECISION HISTORY
- 2026-08-19 [GE-122a-2/test-writer, bug-fix regression]: Initial authoring
  of the nested-folder false-negative test, the shared-basename
  false-positive test, the flat-layout regression anchor, and the
  missing-folder fail-open test, per pr-reviewer's finding
  fb_2026-08-19_e1c1912f. Verified RED/GREEN split against
  templates/scripts/commit_guardian/_work_items_scanner.py as it stands
  today (commit 6d82da27 and later, pre-fix) -- see the test-writer
  sign-off comment's red_baseline block for the exact captured output.
"""

from __future__ import annotations

import copy
import importlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Canonical paths -- templates/scripts/commit_guardian/ is the source of
# truth (ADR-001: template-is-canonical, .leafcutter/ is a build output).
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_WORK_ITEMS_SCANNER_PATH = _COMMIT_GUARDIAN_DIR / "_work_items_scanner.py"
_REAL_LIFECYCLE_CONFIG = _REPO_ROOT / "tickets" / "ticket_lifecycle.json"


def _ensure_commit_guardian_on_sys_path() -> None:
    """Insert templates/scripts/commit_guardian/ onto sys.path, once.

    Required because _work_items_scanner.py uses a plain top-level sibling
    import (``from _uniqueness_types import Finding, NamespaceVerdict``)
    rather than a package-relative import.
    """
    commit_guardian_dir = str(_COMMIT_GUARDIAN_DIR)
    if commit_guardian_dir not in sys.path:
        sys.path.insert(0, commit_guardian_dir)


def _load_work_items_scanner():
    """Import _work_items_scanner.py (the module under test) by real name.

    Returns:
        The imported module, or None if the canonical file is missing
        (would be a regression -- the module already exists as of
        GE-122a-2).
    """
    if not _WORK_ITEMS_SCANNER_PATH.exists():
        return None
    _ensure_commit_guardian_on_sys_path()
    return importlib.import_module("_work_items_scanner")


_scanner = _load_work_items_scanner()


def _require_scanner(test_case: unittest.TestCase) -> None:
    """Fail with a clear message if the module under test could not be loaded.

    Args:
        test_case: The calling TestCase instance.
    """
    if _scanner is None:
        test_case.fail(
            f"_work_items_scanner.py not found at canonical path "
            f"{_WORK_ITEMS_SCANNER_PATH}. It should already exist from "
            "GE-122a-2 -- this would be a regression, not the expected RED "
            "state for this bug-fix ticket."
        )


# ---------------------------------------------------------------------------
# Lifecycle config fixtures -- always start from the real on-disk config
# (json.loads), then mutate programmatically. Never a hand-typed dict/JSON
# literal, per the Fixture Authenticity Rule.
# ---------------------------------------------------------------------------


def _real_lifecycle_dict() -> dict:
    """Load and parse this repo's real tickets/ticket_lifecycle.json.

    Returns:
        The parsed JSON document as a fresh dict (safe to mutate).
    """
    return json.loads(_REAL_LIFECYCLE_CONFIG.read_text(encoding="utf-8"))


def _folder_entry(real_config: dict, label: str) -> dict:
    """Deep-copy the real folder entry with the given ``label``.

    Args:
        real_config: The parsed real ticket_lifecycle.json document.
        label: The folder entry's "label" field (e.g. "inbox", "todo").

    Returns:
        A deep copy of the matching folder entry dict.

    Raises:
        AssertionError: If no entry with that label exists -- signals the
            real config's shape no longer matches this fixture's
            assumption, which must be re-verified rather than silently
            producing an empty fixture.
    """
    for entry in real_config["folders"]:
        if entry.get("label") == label:
            return copy.deepcopy(entry)
    raise AssertionError(
        f"No folder entry with label {label!r} found in the real "
        f"{_REAL_LIFECYCLE_CONFIG} -- fixture assumption invalidated, "
        "update this test to match the real config's current shape."
    )


def _write_lifecycle_config(root: Path, folder_entries: list[dict]) -> Path:
    """Write a ticket_lifecycle.json built from the real config's shape,
    with a caller-supplied ``folders`` list, via json.dump.

    Args:
        root: Fixture root; the file is written to root/tickets/ticket_lifecycle.json.
        folder_entries: The folder entry dicts to install (each already a
            deep copy of a real entry, possibly with its "path" mutated).

    Returns:
        The path the config was written to.
    """
    config = _real_lifecycle_dict()
    config["folders"] = folder_entries
    dest = root / "tickets" / "ticket_lifecycle.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(config, fh, indent=2)
    return dest


def _install_real_lifecycle_config(root: Path) -> Path:
    """Copy the real tickets/ticket_lifecycle.json byte-for-byte (unmodified).

    Used only by the flat-layout regression anchor, where the shape under
    test is deliberately the UNMODIFIED real config.

    Args:
        root: Fixture root; the file is copied to root/tickets/ticket_lifecycle.json.

    Returns:
        The path the config was copied to.
    """
    dest = root / "tickets" / "ticket_lifecycle.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(_REAL_LIFECYCLE_CONFIG, dest)
    return dest


# ---------------------------------------------------------------------------
# Ticket fixture writer
# ---------------------------------------------------------------------------


def _write_ticket(path: Path, *, status: str, title: str = "Fixture ticket") -> None:
    """Write a ticket fixture with REAL YAML-serialized frontmatter.

    Uses yaml.safe_dump for the frontmatter block (never a hand-typed
    "status: X" string) per the Fixture Authenticity Rule.

    Args:
        path: Destination ticket file path (parents created as needed).
        status: The declared lifecycle status for this copy's frontmatter.
        title: Ticket title (frontmatter field, cosmetic for these fixtures).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = yaml.safe_dump({"status": status, "title": title}, sort_keys=False)
    content = f"---\n{frontmatter}---\n\n# {title}\n\nFixture ticket body.\n"
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Independent oracle -- deliberately does NOT call into
# _work_items_scanner._read_lifecycle_folder_names (the function that
# contains the bug); joins root directly with each entry's own full "path"
# field, which is the CORRECT construction, so a shared bug between this
# oracle and the code under test cannot hide from the comparison.
# ---------------------------------------------------------------------------


def _true_inspected_count(root: Path, folder_entries: list[dict]) -> int:
    """Independently count every "TICKET-*.md" file across the declared folders.

    Args:
        root: Fixture root the folder paths are relative to.
        folder_entries: The folder entry dicts actually installed in the
            fixture's ticket_lifecycle.json.

    Returns:
        The true count of "TICKET-*.md" files directly under each declared
        folder (non-recursive, matching the production walk's own
        contract), resolved via the entry's FULL "path" field -- never a
        basename.
    """
    total = 0
    for entry in folder_entries:
        folder_dir = root / entry["path"]
        if folder_dir.is_dir():
            total += len(list(folder_dir.glob("TICKET-*.md")))
    return total


def _resolved_path_set(raw_paths, root: Path) -> set:
    """Normalize a finding's claimant path strings to resolved absolute Paths.

    Args:
        raw_paths: Iterable of path strings/Path objects from a Finding.
        root: The fixture root, used to resolve relative paths.

    Returns:
        Set of resolved absolute Path objects.
    """
    resolved = set()
    for raw in raw_paths:
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = root / candidate
        resolved.add(candidate.resolve())
    return resolved


# ---------------------------------------------------------------------------
# (a) NESTED FOLDER, FALSE NEGATIVE -- the load-bearing test.
# ---------------------------------------------------------------------------


class TestNestedLifecycleFolderCrossFolderDuplicate(unittest.TestCase):
    """test_ac_nested_folder_duplicate_is_reported (false-negative regression)."""

    def setUp(self) -> None:
        _require_scanner(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_nested_lifecycle_folder_duplicate_is_reported_with_both_claimants(self):
        # covers: GE-122a-2
        """Bug-fix regression (false negative): a lifecycle folder declared
        at a NESTED path ("tickets/00_inbox/archive", two levels under
        tickets/) must still be walked, and a genuine cross-folder
        duplicate held partly inside it must still be reported -- naming
        BOTH claimant paths -- exactly like a duplicate held by two flat,
        one-level folders.

        FAILS TODAY: ``_read_lifecycle_folder_names`` collapses
        "tickets/00_inbox/archive" to the bare basename "archive", which
        the caller then rejoins as ``tickets_root / "archive"`` -- a
        directory that does not exist in this fixture (the real files live
        at ``tickets_root / "00_inbox" / "archive"``). ``is_dir()`` on the
        wrong reconstructed path returns False, so that folder is silently
        skipped entirely: the nested copy of the duplicate is never seen,
        ``verdict.passed`` is (incorrectly) True, and ``inspected_count``
        is short by exactly the two files that live under the nested
        folder.
        """
        real_config = _real_lifecycle_dict()
        nested_inbox = _folder_entry(real_config, "inbox")
        nested_inbox["path"] = "tickets/00_inbox/archive"
        todo_entry = _folder_entry(real_config, "todo")
        folder_entries = [nested_inbox, todo_entry]
        lifecycle_path = _write_lifecycle_config(self.root, folder_entries)

        tickets_root = self.root / "tickets"
        dup_name = "TICKET-30000001-NestedDup.md"
        path_in_archive = tickets_root / "00_inbox" / "archive" / dup_name
        path_in_todo = tickets_root / "01_todo" / dup_name
        _write_ticket(path_in_archive, status="archived")
        _write_ticket(path_in_todo, status="in_progress")
        # One uncontested file in each declared folder, so inspected_count
        # is not trivially "just the pair".
        _write_ticket(
            tickets_root / "00_inbox" / "archive" / "TICKET-30000002-NestedOnly.md",
            status="archived",
        )
        _write_ticket(tickets_root / "01_todo" / "TICKET-30000003-TodoOnly.md", status="todo")

        true_count = _true_inspected_count(self.root, folder_entries)
        self.assertEqual(true_count, 4, msg="Fixture sanity check: expected 2 files per declared folder.")

        verdict = _scanner.scan_work_items(tickets_root, lifecycle_path)

        self.assertFalse(
            verdict.passed,
            msg=(
                "A genuine cross-folder duplicate involving a NESTED lifecycle "
                "folder must fail the pass, same as a flat-folder duplicate. "
                f"Got passed={verdict.passed}, inspected_count={verdict.inspected_count}, "
                f"findings={verdict.findings}."
            ),
        )
        self.assertEqual(
            len(verdict.findings),
            1,
            msg=f"Expected exactly 1 finding for the one contested identifier, got {verdict.findings}.",
        )
        finding = verdict.findings[0]
        actual_paths = _resolved_path_set(finding.paths, self.root)
        expected_paths = {path_in_archive.resolve(), path_in_todo.resolve()}
        self.assertEqual(
            actual_paths,
            expected_paths,
            msg=(
                f"The finding must name BOTH claimant paths, including the one "
                f"under the nested folder. Expected {expected_paths}, got {actual_paths}."
            ),
        )
        self.assertEqual(
            verdict.inspected_count,
            true_count,
            msg=(
                f"inspected_count must equal the independently-computed true count "
                f"({true_count}) across BOTH declared folders (including the nested "
                f"one), got {verdict.inspected_count}. A short count means the nested "
                "folder was silently skipped."
            ),
        )


# ---------------------------------------------------------------------------
# (b) SHARED BASENAME, FALSE POSITIVE.
# ---------------------------------------------------------------------------


class TestSharedBasenameDistinctFoldersNoCollision(unittest.TestCase):
    """test_ac_shared_basename_distinct_folders_produce_no_finding (false-positive regression)."""

    def setUp(self) -> None:
        _require_scanner(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_two_declared_paths_sharing_a_basename_hold_different_items_no_collision(self):
        # covers: GE-122a-2
        """Bug-fix regression (false positive): two DISTINCT declared
        lifecycle folder paths that happen to share their LAST path
        component ("tickets/00_inbox" and "tickets/archive_area/00_inbox",
        both basename "00_inbox") but hold DIFFERENT work items must
        produce NO finding -- this is the case a naive "just don't call
        .name" fix could still get wrong if it does not also guarantee each
        declared path is walked as its own distinct directory.

        FAILS TODAY: ``_read_lifecycle_folder_names`` collapses both
        declared paths to the SAME basename "00_inbox", so the walk visits
        ``tickets_root / "00_inbox"`` TWICE instead of visiting each
        declared location once. The single real file living there
        (FileA) is walked twice and recorded as two claimant entries for
        the SAME path -- a spurious "collision" of one file with itself --
        while FileB, which genuinely lives at the other declared path
        ("tickets/archive_area/00_inbox"), is never inspected at all.
        """
        real_config = _real_lifecycle_dict()
        flat_inbox = _folder_entry(real_config, "inbox")  # path stays "tickets/00_inbox"
        nested_inbox_lookalike = _folder_entry(real_config, "inbox")
        nested_inbox_lookalike["path"] = "tickets/archive_area/00_inbox"
        nested_inbox_lookalike["label"] = "archived-inbox-lookalike"
        folder_entries = [flat_inbox, nested_inbox_lookalike]
        lifecycle_path = _write_lifecycle_config(self.root, folder_entries)

        tickets_root = self.root / "tickets"
        file_a = tickets_root / "00_inbox" / "TICKET-40000001-Solo.md"
        file_b = tickets_root / "archive_area" / "00_inbox" / "TICKET-40000002-OtherSolo.md"
        _write_ticket(file_a, status="todo")
        _write_ticket(file_b, status="archived")

        true_count = _true_inspected_count(self.root, folder_entries)
        self.assertEqual(true_count, 2, msg="Fixture sanity check: one file under each distinct declared path.")

        verdict = _scanner.scan_work_items(tickets_root, lifecycle_path)

        self.assertTrue(
            verdict.passed,
            msg=(
                "Two distinct declared paths that merely SHARE a basename but "
                "hold DIFFERENT work items must not collide. "
                f"Got passed={verdict.passed}, findings={verdict.findings}."
            ),
        )
        self.assertEqual(
            len(verdict.findings),
            0,
            msg=(
                f"Expected zero findings, got {verdict.findings!r} -- this is the "
                "single real file (FileA) being walked twice under the same "
                "collapsed basename and reported as if two folders held it."
            ),
        )
        self.assertEqual(
            verdict.inspected_count,
            true_count,
            msg=(
                f"inspected_count must equal the independently-computed true count "
                f"({true_count}: one file per distinct declared path), got "
                f"{verdict.inspected_count}. A matching-but-wrong count (e.g. "
                "counting FileA twice while never inspecting FileB) is possible "
                "here too -- this assertion alone does not prove correctness, "
                "which is why the zero-findings assertion above is the primary one."
            ),
        )


# ---------------------------------------------------------------------------
# (c) REGRESSION ANCHOR -- the current flat layout must keep working exactly
# as it does today.
# ---------------------------------------------------------------------------


class TestFlatLayoutRegressionAnchor(unittest.TestCase):
    """test_ac_flat_layout_still_works (must stay green before and after the fix)."""

    def setUp(self) -> None:
        _require_scanner(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_flat_one_level_lifecycle_folders_duplicate_still_detected(self):
        # covers: GE-122a-2
        """Regression anchor: this repo's REAL, unmodified
        ticket_lifecycle.json (installed byte-for-byte) declares every
        lifecycle folder exactly one level under tickets/ -- the shape the
        current ``.name``-based implementation happens to get right by
        coincidence. A cross-folder duplicate over this real, flat shape
        must be detected correctly both BEFORE and AFTER the nested-path
        fix -- this test must be green today and stay green.
        """
        lifecycle_path = _install_real_lifecycle_config(self.root)
        real_config = _real_lifecycle_dict()
        folder_entries = real_config["folders"]

        tickets_root = self.root / "tickets"
        dup_name = "TICKET-30000101-FlatDup.md"
        path_inbox = tickets_root / "00_inbox" / dup_name
        path_todo = tickets_root / "01_todo" / dup_name
        _write_ticket(path_inbox, status="todo")
        _write_ticket(path_todo, status="in_progress")
        _write_ticket(tickets_root / "99_done" / "TICKET-30000102-DoneOnly.md", status="done")

        true_count = _true_inspected_count(self.root, folder_entries)
        self.assertEqual(true_count, 3, msg="Fixture sanity check: 2 pair files + 1 uncontested file.")

        verdict = _scanner.scan_work_items(tickets_root, lifecycle_path)

        self.assertFalse(verdict.passed, msg="A real cross-folder duplicate over the flat layout must fail.")
        self.assertEqual(len(verdict.findings), 1, msg=f"Expected exactly 1 finding, got {verdict.findings}.")
        finding = verdict.findings[0]
        actual_paths = _resolved_path_set(finding.paths, self.root)
        expected_paths = {path_inbox.resolve(), path_todo.resolve()}
        self.assertEqual(actual_paths, expected_paths, msg=f"Expected {expected_paths}, got {actual_paths}.")
        self.assertEqual(
            verdict.inspected_count,
            true_count,
            msg=f"inspected_count must equal the independently-computed true count ({true_count}).",
        )


# ---------------------------------------------------------------------------
# (d) Declared folder absent from disk entirely -- fail-open convention.
# ---------------------------------------------------------------------------


class TestMissingDeclaredFolderFailsOpen(unittest.TestCase):
    """test_ac_missing_declared_folder_fails_open (no crash, counted as nothing)."""

    def setUp(self) -> None:
        _require_scanner(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_declared_folder_absent_from_disk_is_skipped_not_crashed(self):
        # covers: GE-122a-2
        """A declared lifecycle folder that does not exist on disk AT ALL
        (never created in this fixture) must be silently skipped -- counted
        as zero files, not a crash -- consistent with the other three
        namespaces' established fail-open-per-missing-directory convention
        (verified against _uniqueness_scanners.py). This must hold both for
        a flat missing folder and for a NESTED missing folder, since the
        nested-path fix must not turn "does not exist" into an exception.
        """
        real_config = _real_lifecycle_dict()
        real_inbox = _folder_entry(real_config, "inbox")  # exists, holds one real file
        missing_nested = _folder_entry(real_config, "inbox")
        missing_nested["path"] = "tickets/00_inbox/nonexistent_nested_archive"
        missing_nested["label"] = "missing-nested"
        folder_entries = [real_inbox, missing_nested]
        lifecycle_path = _write_lifecycle_config(self.root, folder_entries)

        tickets_root = self.root / "tickets"
        _write_ticket(tickets_root / "00_inbox" / "TICKET-30000201-OnlyRealFile.md", status="todo")
        # Deliberately never create tickets/00_inbox/nonexistent_nested_archive/.

        true_count = _true_inspected_count(self.root, folder_entries)
        self.assertEqual(true_count, 1, msg="Fixture sanity check: only the real folder's one file counts.")

        try:
            verdict = _scanner.scan_work_items(tickets_root, lifecycle_path)
        except OSError as exc:
            self.fail(
                f"scan_work_items must fail open on a missing declared folder, not "
                f"raise -- got {type(exc).__name__}: {exc}"
            )

        self.assertTrue(verdict.passed, msg="A single uniquely-held file with a missing sibling folder must pass.")
        self.assertEqual(len(verdict.findings), 0, msg=f"Expected zero findings, got {verdict.findings}.")
        self.assertEqual(
            verdict.inspected_count,
            true_count,
            msg=(
                f"inspected_count must equal the true count ({true_count}) from the "
                f"one folder that actually exists, got {verdict.inspected_count}. "
                "The missing nested folder must be counted as nothing, not crash "
                "and not be silently substituted for a different real directory."
            ),
        )


if __name__ == "__main__":
    unittest.main()
