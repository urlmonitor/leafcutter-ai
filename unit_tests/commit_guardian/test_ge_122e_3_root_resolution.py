"""
MODULE: unit_tests/commit_guardian/test_ge_122e_3_root_resolution.py
GOAL: RED test-first stubs pinning the floor for pr-reviewer finding [H-3]
    (feedback-id fb_2026-08-24_94dc4ba4, filed against GE-122e-3): a wholly
    missing or unreadable namespace root -- or, for "work-items", a missing
    or unreadable ``tickets/ticket_lifecycle.json`` -- silently reports that
    namespace, and transitively the WHOLE COLLECTION, as PASSED with
    ``inspected_count == 0``, rather than a distinguishable failure.

WHY A SIBLING FILE, NOT test_ge_122e_3.py: that file is already ~920 lines
    covering the whole exit-gate contract end-to-end against a full copy of
    this repository's real, current collection (AC-1, AC-2, AC-3, AC-4, AC-5
    from the ticket's own Test Requirements table). This module owns exactly
    one additional, narrower concern -- root/config RESOLVABILITY, as opposed
    to collision detection over a resolved root -- so it is kept separate
    rather than pushed further past that file's existing size, mirroring the
    test_ge_122a_1_fast_path_equivalence.py / test_ge_122a_2_lifecycle_folder_paths.py
    precedent already established in this directory for a sibling AC's
    bug-fix regression coverage.

THE DEFECT (reproduced directly against this branch before writing a single
    test below):

        run_uniqueness_pass(Path('/tmp/definitely_does_not_exist_ge122_probe'))
          overall passed = True
          acceptance-criteria  passed=True  inspected_count=0
          decisions            passed=True  inspected_count=0
          diagrams             passed=True  inspected_count=0
          work-items           passed=True  inspected_count=0

    Root cause: ``scan_acceptance_criteria`` and ``_scan_filename_numbered``
    (backing ``scan_decisions`` / ``scan_diagrams``) in
    _uniqueness_scanners.py, and ``_resolve_lifecycle_folder_paths`` (backing
    ``scan_work_items``) in _work_items_scanner.py, each return
    ``NamespaceVerdict(passed=True, inspected_count=0, findings=[])`` -- an
    UNCONDITIONAL pass -- whenever their root directory or config file does
    not exist, is unreadable, or is unparsable. ``run_uniqueness_pass``'s
    ``passed = all(ns.passed for ns in namespaces.values())`` then reports
    the WHOLE COLLECTION as passing.

WHY THIS IS THE EPIC'S OWN THESIS VIOLATED BY ITS OWN IMPLEMENTATION:
    GE-122a-1's own coverage note requires the pass to state per-namespace
    inspected counts precisely "so a passing result is distinguishable from
    a pass produced by inspecting nothing." This AC's own doc_links call out
    GE-120a-1 as "the sibling policy the per-namespace inspected count
    serves: a check that could not inspect must not look like one that
    inspected and found nothing." The gate built to make a pass-over-nothing
    detectable IS a pass-over-nothing, for exactly the input class (a wrong
    or renamed root) most likely in a real consumer install.

    Existing coverage cannot see it: test_ge_122e_3.py always points at a
    full copy of this repo's OWN real, populated collection (never a wrong
    or absent root). test_ge_122a_2_lifecycle_folder_paths.py's
    TestMissingDeclaredFolderFailsOpen covers ONE declared FOLDER missing
    while the CONFIG FILE ITSELF is present and valid -- a legitimate,
    unaffected fail-open case under the contract this module fixes (see
    "THE CONTRACT DECISION" below). Nothing anywhere covers the root
    directory, or the work-items config FILE, being absent or unreadable
    entirely.

THE CONTRACT DECISION (this module's central design question, answered
    explicitly rather than picked implicitly -- the coder implements to
    these tests, so the reasoning here fixes the contract):

    There is a genuine, real difference between two situations that
    currently look identical (``passed=True, inspected_count=0``):

      (1) LEGITIMATE EMPTY: the namespace's root/config was actually
          resolved -- the directory exists and was walked, or the config
          file was read and parsed -- and it genuinely holds zero artifacts
          today (e.g. a fresh project with no ADRs yet, or a
          ``ticket_lifecycle.json`` that explicitly declares
          ``"folders": []``). A pass here is TRUE evidence: the check ran
          and found nothing to complain about.
      (2) MISCONFIGURATION: the root/config could not be found or read at
          all (typo'd ``collection_root``, a build-layout change that
          renamed ``docs/acceptance-criteria/``, a deleted or corrupted
          ``tickets/ticket_lifecycle.json``). A pass here is FALSE evidence:
          the check never ran, and reporting it as clean actively certifies
          a broken installation as sound.

    DECISION: distinguish them WITHOUT widening the NamespaceVerdict /
    UniquenessVerdict dataclasses with a new field. Instead, tighten what
    ``passed=True`` is allowed to MEAN: a namespace may report
    ``passed=True`` ONLY when its root/config was actually resolved (walked
    or read), REGARDLESS of whether that walk/read produced zero or many
    artifacts. A namespace whose root/config could not be resolved at all
    MUST report ``passed=False`` -- even though it has no findings to name,
    since there is nothing to name; the root itself is the finding.

    This is deliberately the MINIMAL surgical fix, not a new tri-state enum
    or an added ``root_resolved`` flag, for three reasons:
      a. It requires no widening of the shared dataclasses that six
         downstream ACs consume (Source-of-Truth Discipline Rule 5: prefer
         the smaller, additive-or-neutral change; a same-shape tightening of
         an existing bool's MEANING is smaller than adding a field every
         consumer must learn to check).
      b. It is fully sufficient to answer the question a caller actually
         asks at commit time or in CI: "can I trust this green?" A caller
         who receives ``passed=True`` can now always trust it means "this
         was actually inspected, and it was clean" -- never "this was never
         looked at." That is precisely the assurance GE-120a-1's sibling
         policy and this AC's own coverage note ask for.
      c. It remains MECHANICALLY DISTINGUISHABLE from the outside without a
         new field: a caller who additionally wants to tell "misconfigured"
         apart from "resolved but genuinely found real contested numbers"
         can already do so from the EXISTING ``findings`` list --
         ``passed=False`` with ``findings == []`` is the misconfiguration
         signal (nothing to name because the root itself is missing);
         ``passed=False`` with ``findings != []`` is a genuine collision.
         Every currently-reachable failure path in this codebase already
         populates ``findings`` when it fails for a collision reason, so
         this three-way split (passed=True / passed=False+empty-findings /
         passed=False+findings) is real and load-bearing today, not merely
         theoretical.

    CONSEQUENCE FOR run_uniqueness_pass: ``passed = all(ns.passed for ns in
    namespaces.values())`` needs NO change under this decision -- it already
    correctly propagates a per-namespace False to the whole-collection
    verdict. The bug lives entirely in the four scan_* functions'
    root/config existence checks, not in the orchestrator.

    WHAT THIS DECISION DELIBERATELY DOES NOT COVER (flagged, not silently
    assumed): a lifecycle folder DECLARED in a resolvable, readable
    ticket_lifecycle.json but absent on disk (the case
    TestMissingDeclaredFolderFailsOpen already covers) remains fail-open --
    the CONFIG was resolved; one declared LOCATION within it being empty or
    missing is a per-folder concern the existing "fail-open per missing
    directory" convention (verified in _uniqueness_scanners.py's docstring)
    already correctly handles, and this module does not disturb it. Only the
    CONFIG FILE ITSELF (or the namespace ROOT itself, for the three
    filesystem-walk namespaces) being unresolvable is in scope here. This is
    a genuinely ambiguous line and is called out explicitly rather than
    silently generalized past what this defect report and this AC require.

KNOWN INTERACTION WITH AN EXISTING TEST (flagged prominently, per this
    ticket's own dispatch instructions, rather than silently worked around):

    unit_tests/commit_guardian/test_ge_122a_1.py::TestRepairedCollectionPasses::
    test_repaired_collection_passes_with_per_namespace_counts asserts
    ``self.assertTrue(verdict.passed, ...)`` over a fixture built by that
    file's own ``_build_fixture_collection`` helper -- which populates
    docs/acceptance-criteria/, docs/architecture/adrs/, and
    docs/architecture/diagrams/ but NEVER creates a ``tickets/`` root or a
    ``tickets/ticket_lifecycle.json`` at all. Today, the work-items
    namespace's config-absent case fail-opens to ``passed=True``, so this
    gap is invisible: the test's ``verdict.passed`` assertion currently
    passes only because THIS SAME DEFECT'S fail-open masks the fixture's own
    incompleteness. Once the contract above is implemented, that fixture's
    missing ``tickets/`` root makes the work-items namespace correctly
    report ``passed=False`` (nothing there to inspect), which flips
    ``verdict.passed`` to False and that assertion RED.

    This is test drift, not production drift, per Source-of-Truth
    Discipline Rule 1: production would be doing exactly what this module's
    contract requires (refusing to call an unresolvable namespace clean);
    the test's OWN fixture is incomplete relative to what it has always
    claimed to build ("a collection with every collision resolved" -- a
    collection, not three-quarters of one). This module does not edit that
    test file (out of the narrow scope this dispatch named -- the two
    production files and their scanners), but the fix, when python-coder
    picks this up, is to add a minimal populated ``tickets/`` root (one
    lifecycle folder, one uncontested ticket) to
    ``_build_fixture_collection`` in test_ge_122a_1.py alongside the
    production fix -- restoring, not weakening, that test's asserted intent.
    Per Source-of-Truth Discipline Rule 4, this is a TEST-repair change with
    no production-behavior claim baked into it and can ride with the
    production fix; it is not itself a production behavior change.

FIXTURE AUTHENTICITY: every serialized artifact (AC YAML id, ADR/diagram
    markdown, ticket frontmatter, ticket_lifecycle.json) is produced via the
    real serializer (yaml.safe_dump / json.dump) and read back by the code
    under test -- never a hand-typed literal -- per
    docs/reference/fixture-policy.md and this repo's CLAUDE.md Fixture
    Authenticity convention. The two deliberately-CORRUPT fixtures (malformed
    JSON text, a permission-denied file) are exceptions by definition: they
    exist specifically to simulate a file a real serializer could never
    produce, which is exactly the "unreadable/unparsable" half of the
    contract under test.

ARCHITECTURE / EXERCISE STRATEGY:
  - check_identifier_uniqueness.py is loaded by file path via importlib
    (matching test_ge_122a_1.py / test_ge_122e_3.py's own convention).
  - _uniqueness_scanners.py and _work_items_scanner.py are imported by their
    real top-level names via importlib.import_module after inserting
    templates/scripts/commit_guardian/ onto sys.path (matching
    test_ge_122a_2_lifecycle_folder_paths.py's own convention) so the
    per-namespace scan_* functions can be called directly, independent of
    the run_uniqueness_pass orchestrator, for the item-(c) tests below.
  - No test in this module touches the real repository tree at all -- every
    fixture is a from-scratch tempdir, and the "root entirely missing" cases
    deliberately never create anything on disk (mirroring the exact probe
    pr-reviewer and this dispatch's own reproduction used).

DECISION HISTORY
- 2026-08-25 [GE-122e-3/test-writer, H-3 bug-fix regression]: Initial
  authoring of all tests pinning the root/config-resolvability floor. A
  previous dispatch of this authoring task was interrupted and wrote nothing
  to disk; this is the first content committed under this filename. Verified
  RED/GREEN split against templates/scripts/commit_guardian/
  check_identifier_uniqueness.py and its sibling scanner modules as they
  stand today (pre-fix) -- see the test-writer sign-off comment's
  red_baseline block for the exact captured output.
"""

from __future__ import annotations

import importlib
import importlib.util as _ilu
import json
import os
import stat
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
_CANONICAL = _COMMIT_GUARDIAN_DIR / "check_identifier_uniqueness.py"

_NS_AC = "acceptance-criteria"
_NS_DECISIONS = "decisions"
_NS_DIAGRAMS = "diagrams"
_NS_WORK_ITEMS = "work-items"
_ALL_NAMESPACES = (_NS_AC, _NS_DECISIONS, _NS_DIAGRAMS, _NS_WORK_ITEMS)


def _load_check_identifier_uniqueness():
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


_mod = _load_check_identifier_uniqueness()


def _ensure_commit_guardian_on_sys_path() -> None:
    """Insert templates/scripts/commit_guardian/ onto sys.path, once.

    Required because _uniqueness_scanners.py and _work_items_scanner.py use
    plain top-level sibling imports (e.g. ``from _uniqueness_types import
    ...``) rather than package-relative ones.
    """
    commit_guardian_dir = str(_COMMIT_GUARDIAN_DIR)
    if commit_guardian_dir not in sys.path:
        sys.path.insert(0, commit_guardian_dir)


def _load_sibling_scanner_modules():
    """Import _uniqueness_scanners and _work_items_scanner by their real names.

    Returns:
        A (scanners_module, work_items_module) tuple, or (None, None) if
        either canonical file is missing.
    """
    scanners_path = _COMMIT_GUARDIAN_DIR / "_uniqueness_scanners.py"
    work_items_path = _COMMIT_GUARDIAN_DIR / "_work_items_scanner.py"
    if not scanners_path.exists() or not work_items_path.exists():
        return None, None
    _ensure_commit_guardian_on_sys_path()
    return (
        importlib.import_module("_uniqueness_scanners"),
        importlib.import_module("_work_items_scanner"),
    )


_scanners, _work_items = _load_sibling_scanner_modules()


def _require_mod(test_case: unittest.TestCase) -> None:
    """Fail with a clear message if check_identifier_uniqueness could not be loaded.

    Args:
        test_case: The calling TestCase instance.
    """
    if _mod is None:
        test_case.fail(
            f"check_identifier_uniqueness.py not found at canonical path {_CANONICAL}. "
            "It should already exist from GE-122a-1/GE-122a-2 -- this would be a "
            "regression, not the expected state for this GE-122e-3 bug-fix module."
        )


def _require_scanners(test_case: unittest.TestCase) -> None:
    """Fail with a clear message if the sibling scanner modules could not be loaded.

    Args:
        test_case: The calling TestCase instance.
    """
    if _scanners is None or _work_items is None:
        test_case.fail(
            "_uniqueness_scanners.py / _work_items_scanner.py not found under "
            f"{_COMMIT_GUARDIAN_DIR}. Both should already exist from GE-122a-1/GE-122a-2."
        )


# ---------------------------------------------------------------------------
# Fixture writers -- real serializers only (Fixture Authenticity Rule).
# ---------------------------------------------------------------------------


def _write_ac_yaml(path: Path, data: dict) -> None:
    """Write an AC YAML fixture using the REAL serializer (yaml.safe_dump).

    Args:
        path: Destination file path (parents created as needed).
        data: The AC record fields to serialize.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False)


def _write_text(path: Path, content: str) -> None:
    """Write a plain-text fixture artifact (decision record / diagram doc).

    Args:
        path: Destination file path (parents created as needed).
        content: File content.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_ticket(path: Path, *, status: str, title: str = "Fixture ticket") -> None:
    """Write a ticket fixture with REAL YAML-serialized frontmatter.

    Args:
        path: Destination ticket file path (parents created as needed).
        status: The declared lifecycle status for this copy's frontmatter.
        title: Ticket title (frontmatter field, cosmetic for this fixture).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = yaml.safe_dump({"status": status, "title": title}, sort_keys=False)
    content = f"---\n{frontmatter}---\n\n# {title}\n\nFixture ticket body.\n"
    path.write_text(content, encoding="utf-8")


def _write_lifecycle_config(path: Path, folders: list[dict]) -> Path:
    """Write a ticket_lifecycle.json fixture via the REAL serializer (json.dump).

    Args:
        path: Destination path for ticket_lifecycle.json (parents created as needed).
        folders: The "folders" list to install.

    Returns:
        path, for chaining.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"folders": folders}, fh)
    return path


# ---------------------------------------------------------------------------
# (a) + (b): whole-collection root entirely missing / present-but-empty.
# ---------------------------------------------------------------------------


class TestWholeCollectionRootEntirelyMissing(unittest.TestCase):
    """Reproduces the exact defect report verbatim: a collection_root that
    does not exist on disk AT ALL (never created, not even the tempdir
    itself) must not report a clean overall pass.
    """

    def setUp(self) -> None:
        _require_mod(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        # Deliberately NEVER created -- matches the probe's own
        # '/tmp/definitely_does_not_exist_ge122_probe' exactly.
        self.root = Path(self._tmp.name) / "definitely_does_not_exist_ge122_probe"

    def test_entirely_missing_root_does_not_report_overall_passed(self):
        # covers: GE-122e-3
        """A collection_root that does not exist at all must not yield
        ``verdict.passed is True`` -- the exact scenario pr-reviewer's
        finding [H-3] reproduced. Today it does: every namespace fail-opens
        to ``passed=True, inspected_count=0`` and ``all(...)`` reports the
        whole collection clean.

        FAILS TODAY: verdict.passed is True over a wholly nonexistent root.
        """
        verdict = _mod.run_uniqueness_pass(self.root)

        self.assertFalse(
            verdict.passed,
            msg=(
                "run_uniqueness_pass over a collection_root that does not exist at all "
                "must NOT report an overall passing verdict -- a pass that inspected "
                "nothing must not look like a pass that inspected a clean collection."
            ),
        )

    def test_entirely_missing_root_every_namespace_individually_fails(self):
        # covers: GE-122e-3
        """Per THE CONTRACT DECISION above: it is not enough for the overall
        verdict to flip False while individual namespaces still silently
        report ``passed=True`` -- a caller inspecting a single namespace
        (as several of this repo's own downstream consumers, e.g. GE-122d-3,
        are documented to do) must see the same signal. All FOUR namespaces
        must individually report ``passed=False`` when the collection_root
        does not exist at all.

        FAILS TODAY: all four namespaces report passed=True, inspected_count=0.
        """
        verdict = _mod.run_uniqueness_pass(self.root)

        for ns_name in _ALL_NAMESPACES:
            self.assertIn(ns_name, verdict.namespaces, msg=f"namespace {ns_name!r} missing from the verdict.")
            ns = verdict.namespaces[ns_name]
            self.assertFalse(
                ns.passed,
                msg=(
                    f"namespace {ns_name!r} reported passed=True, inspected_count="
                    f"{ns.inspected_count} over a wholly nonexistent collection_root -- "
                    "this namespace was never actually inspected and must not report clean."
                ),
            )


class TestWholeCollectionRootExistsButNoNamespaceDirectories(unittest.TestCase):
    """Item (b): the root itself EXISTS (a real, empty directory) but
    contains none of the four expected namespace subtrees at all. From each
    scan_* function's own point of view this is indistinguishable from the
    namespace root itself not existing -- ``root / "docs" / "acceptance-criteria"``
    is exactly as absent either way -- so the same contract applies.
    """

    def setUp(self) -> None:
        _require_mod(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.assertTrue(self.root.is_dir(), "fixture sanity: the tempdir root itself must exist.")

    def test_root_exists_with_no_namespace_directories_does_not_pass(self):
        # covers: GE-122e-3
        """A root that exists but holds none of docs/acceptance-criteria/,
        docs/architecture/adrs/, docs/architecture/diagrams/, or tickets/
        must not report an overall passing verdict, nor any individually
        passing namespace -- this is a misconfiguration (wrong root pointed
        at an otherwise-real directory), not a legitimately empty project.

        FAILS TODAY: same fail-open as the entirely-missing-root case.
        """
        verdict = _mod.run_uniqueness_pass(self.root)

        self.assertFalse(
            verdict.passed,
            msg="A root with none of the four expected namespace subtrees must not report an overall pass.",
        )
        for ns_name in _ALL_NAMESPACES:
            ns = verdict.namespaces[ns_name]
            self.assertFalse(
                ns.passed,
                msg=f"namespace {ns_name!r} must not report passed=True when its own subtree is entirely absent.",
            )


# ---------------------------------------------------------------------------
# (c) Each namespace individually: root/config absent or unreadable.
# ---------------------------------------------------------------------------


class TestPerNamespaceRootOrConfigAbsentOrUnreadable(unittest.TestCase):
    """Calls each scan_* function DIRECTLY (bypassing run_uniqueness_pass)
    so a fix scoped only to the orchestrator -- rather than to the four
    scan_* functions that actually own this fail-open branch -- cannot pass
    these tests by accident.
    """

    def setUp(self) -> None:
        _require_scanners(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_acceptance_criteria_scan_root_absent_does_not_pass_cleanly(self):
        # covers: GE-122e-3
        """scan_acceptance_criteria over a nonexistent ac_root must not
        report passed=True.

        FAILS TODAY: returns NamespaceVerdict(passed=True, inspected_count=0, findings=[]).
        """
        missing_ac_root = self.root / "does_not_exist" / "acceptance-criteria"
        ns = _scanners.scan_acceptance_criteria(missing_ac_root)
        self.assertFalse(
            ns.passed,
            msg=f"scan_acceptance_criteria over a nonexistent root reported passed=True (inspected_count={ns.inspected_count}).",
        )

    def test_decisions_scan_root_absent_does_not_pass_cleanly(self):
        # covers: GE-122e-3
        """scan_decisions over a nonexistent adr_root must not report passed=True.

        FAILS TODAY: returns NamespaceVerdict(passed=True, inspected_count=0, findings=[]).
        """
        missing_adr_root = self.root / "does_not_exist" / "adrs"
        ns = _scanners.scan_decisions(missing_adr_root)
        self.assertFalse(
            ns.passed,
            msg=f"scan_decisions over a nonexistent root reported passed=True (inspected_count={ns.inspected_count}).",
        )

    def test_diagrams_scan_root_absent_does_not_pass_cleanly(self):
        # covers: GE-122e-3
        """scan_diagrams over a nonexistent diagram_root must not report passed=True.

        FAILS TODAY: returns NamespaceVerdict(passed=True, inspected_count=0, findings=[]).
        """
        missing_diagram_root = self.root / "does_not_exist" / "diagrams"
        ns = _scanners.scan_diagrams(missing_diagram_root)
        self.assertFalse(
            ns.passed,
            msg=f"scan_diagrams over a nonexistent root reported passed=True (inspected_count={ns.inspected_count}).",
        )

    def test_work_items_lifecycle_config_absent_does_not_pass_cleanly(self):
        # covers: GE-122e-3
        """scan_work_items over a ticket_lifecycle.json path that does not
        exist at all must not report passed=True -- this is the exact
        "accidentally deleted config" scenario this AC's own dispatch names
        as the most plausible real-world trigger.

        FAILS TODAY: _resolve_lifecycle_folder_paths returns [] on a missing
        config file, and scan_work_items's `if not folder_paths:` branch
        returns NamespaceVerdict(passed=True, inspected_count=0, findings=[]).
        """
        tickets_root = self.root / "tickets"
        missing_config = tickets_root / "ticket_lifecycle.json"
        self.assertFalse(missing_config.exists(), "fixture sanity: the config must not exist for this test.")
        ns = _work_items.scan_work_items(tickets_root, missing_config)
        self.assertFalse(
            ns.passed,
            msg=f"scan_work_items over a missing ticket_lifecycle.json reported passed=True (inspected_count={ns.inspected_count}).",
        )

    def test_work_items_lifecycle_config_unparsable_json_does_not_pass_cleanly(self):
        # covers: GE-122e-3
        """scan_work_items over a ticket_lifecycle.json that exists but is
        not valid JSON (corrupted on disk) must not report passed=True.
        Deliberately hand-written invalid JSON, not yaml.safe_dump/json.dump
        output -- an intentionally-corrupt fixture cannot be produced by the
        real serializer by definition; that is exactly the condition under
        test.

        FAILS TODAY: json.JSONDecodeError is caught, _resolve_lifecycle_folder_paths
        returns [], and the same passed=True fail-open branch is taken as
        the missing-config case above.
        """
        tickets_root = self.root / "tickets"
        config_path = tickets_root / "ticket_lifecycle.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text("{ this is not valid json at all !!", encoding="utf-8")

        ns = _work_items.scan_work_items(tickets_root, config_path)
        self.assertFalse(
            ns.passed,
            msg=f"scan_work_items over an unparsable ticket_lifecycle.json reported passed=True (inspected_count={ns.inspected_count}).",
        )

    @unittest.skipIf(os.name != "posix", "permission bits are not meaningfully testable on this platform")
    @unittest.skipIf(
        hasattr(os, "geteuid") and os.geteuid() == 0,
        "running as root bypasses file permission checks; this test cannot simulate 'unreadable' under root",
    )
    def test_work_items_lifecycle_config_permission_denied_does_not_pass_cleanly(self):
        # covers: GE-122e-3
        """scan_work_items over a ticket_lifecycle.json that exists, IS
        valid JSON, but cannot be READ due to filesystem permissions (mode
        0o000) must not report passed=True -- distinct from the unparsable
        case above, this exercises the OSError/PermissionError branch in
        ``_resolve_lifecycle_folder_paths`` rather than the JSONDecodeError
        branch, since both currently collapse to the identical fail-open.

        FAILS TODAY: OSError is caught, _resolve_lifecycle_folder_paths
        returns [], same passed=True fail-open branch as the other two
        work-items cases above.
        """
        tickets_root = self.root / "tickets"
        config_path = _write_lifecycle_config(tickets_root / "ticket_lifecycle.json", [{"path": "tickets/00_inbox"}])
        original_mode = config_path.stat().st_mode
        config_path.chmod(0)
        try:
            ns = _work_items.scan_work_items(tickets_root, config_path)
        finally:
            config_path.chmod(original_mode | stat.S_IWUSR | stat.S_IRUSR)

        self.assertFalse(
            ns.passed,
            msg=f"scan_work_items over a permission-denied ticket_lifecycle.json reported passed=True (inspected_count={ns.inspected_count}).",
        )


# ---------------------------------------------------------------------------
# Design-question anchor: a root/config that IS resolved but genuinely holds
# zero artifacts must still legitimately pass. This is the other half of THE
# CONTRACT DECISION above -- without this anchor, a coder could satisfy every
# test above by making "inspected_count == 0" always fail, which would be a
# real regression against a legitimately empty, freshly-onboarded project.
# ---------------------------------------------------------------------------


class TestNamespaceRootPresentButGenuinelyEmptyStillPassesCleanly(unittest.TestCase):
    """These are the CONTRASTING cases to the previous class: the root/config
    itself IS resolvable, and simply contains nothing yet. Every assertion
    here is expected to be GREEN both before and after python-coder's fix --
    this class exists to lock in the "legitimate pass" side of the contract
    so a future implementation cannot overcorrect into "any inspected_count
    == 0 is now a failure," which would itself be a regression this same AC
    would then need a second bug-fix ticket to undo.
    """

    def setUp(self) -> None:
        _require_scanners(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_acceptance_criteria_present_empty_directory_passes_cleanly(self):
        # covers: GE-122e-3
        """An acceptance-criteria root that EXISTS as a real, empty
        directory (no *.yaml files at all) must still pass, with
        inspected_count == 0 -- this is a genuinely empty namespace, not a
        misconfigured one.
        """
        ac_root = self.root / "docs" / "acceptance-criteria"
        ac_root.mkdir(parents=True)
        ns = _scanners.scan_acceptance_criteria(ac_root)
        self.assertTrue(ns.passed, msg="An existing, genuinely empty acceptance-criteria directory must pass.")
        self.assertEqual(ns.inspected_count, 0)
        self.assertEqual(ns.findings, [])

    def test_decisions_present_empty_directory_passes_cleanly(self):
        # covers: GE-122e-3
        """An existing, empty decisions (ADR) directory must still pass,
        with inspected_count == 0.
        """
        adr_root = self.root / "docs" / "architecture" / "adrs"
        adr_root.mkdir(parents=True)
        ns = _scanners.scan_decisions(adr_root)
        self.assertTrue(ns.passed, msg="An existing, genuinely empty decisions directory must pass.")
        self.assertEqual(ns.inspected_count, 0)
        self.assertEqual(ns.findings, [])

    def test_diagrams_present_empty_directory_passes_cleanly(self):
        # covers: GE-122e-3
        """An existing, empty diagrams directory must still pass, with
        inspected_count == 0.
        """
        diagram_root = self.root / "docs" / "architecture" / "diagrams"
        diagram_root.mkdir(parents=True)
        ns = _scanners.scan_diagrams(diagram_root)
        self.assertTrue(ns.passed, msg="An existing, genuinely empty diagrams directory must pass.")
        self.assertEqual(ns.inspected_count, 0)
        self.assertEqual(ns.findings, [])

    def test_work_items_config_present_with_zero_declared_folders_passes_cleanly(self):
        # covers: GE-122e-3
        """A ticket_lifecycle.json that EXISTS, IS valid JSON, and
        EXPLICITLY declares an empty "folders" list must still pass, with
        inspected_count == 0 -- this is a project that has deliberately
        enrolled zero lifecycle folders, not one whose config could not be
        found or read. This is the sharpest illustration of THE CONTRACT
        DECISION above: this exact fixture is CURRENTLY indistinguishable,
        inside _resolve_lifecycle_folder_paths, from a missing/corrupt
        config (both take the same `if not folder_paths:` branch) -- so a
        correct fix must actively keep this one passing while making the
        missing/corrupt-config siblings above start failing, not merely add
        a blanket "always fail on empty" rule.
        """
        tickets_root = self.root / "tickets"
        config_path = _write_lifecycle_config(tickets_root / "ticket_lifecycle.json", [])
        ns = _work_items.scan_work_items(tickets_root, config_path)
        self.assertTrue(
            ns.passed,
            msg="A present, valid ticket_lifecycle.json declaring zero folders must still pass cleanly.",
        )
        self.assertEqual(ns.inspected_count, 0)
        self.assertEqual(ns.findings, [])


# ---------------------------------------------------------------------------
# (d) Anchor: a correctly, fully populated collection must still pass, with
# correct NON-ZERO counts. Without this, every test above could be satisfied
# by an implementation that simply always returns passed=False -- "always
# fail" is exactly as useless a gate as "always pass".
# ---------------------------------------------------------------------------


class TestFullyPopulatedCollectionStillPassesWithCorrectCounts(unittest.TestCase):
    def setUp(self) -> None:
        _require_mod(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_correctly_populated_collection_passes_with_correct_nonzero_counts(self):
        # covers: GE-122e-3
        """A collection with a real, resolvable, populated root in all four
        namespaces -- one uncontested artifact per namespace, no collisions
        anywhere -- must pass overall, with every namespace individually
        passing and reporting inspected_count equal to the actual on-disk
        count (1 in every namespace here). This is the anchor that stops
        this whole module's fix from degenerating into "always fail";
        expected GREEN both before and after python-coder's fix.
        """
        ac_root = self.root / "docs" / "acceptance-criteria" / "fixture-component"
        adr_root = self.root / "docs" / "architecture" / "adrs"
        diagram_root = self.root / "docs" / "architecture" / "diagrams"
        tickets_root = self.root / "tickets"

        _write_ac_yaml(ac_root / "GE-9001-standalone.yaml", {"id": "GE-9001", "level": "L2", "title": "Fixture AC"})
        _write_text(adr_root / "ADR-9001-fixture.md", "# ADR-9001 Fixture\n\nStatus: accepted\n")
        _write_text(diagram_root / "c2-9001-fixture.md", "# c2-9001 Fixture\n")
        _write_lifecycle_config(tickets_root / "ticket_lifecycle.json", [{"path": "tickets/00_inbox"}])
        _write_ticket(tickets_root / "00_inbox" / "TICKET-90010101-Fixture.md", status="todo")

        verdict = _mod.run_uniqueness_pass(self.root)

        self.assertTrue(
            verdict.passed,
            msg=(
                f"A fully populated, uncontested collection must pass overall. "
                f"Per-namespace: { {n: (v.passed, v.inspected_count) for n, v in verdict.namespaces.items()} }"
            ),
        )
        expected_counts = {
            _NS_AC: 1,
            _NS_DECISIONS: 1,
            _NS_DIAGRAMS: 1,
            _NS_WORK_ITEMS: 1,
        }
        for ns_name, expected_count in expected_counts.items():
            ns = verdict.namespaces[ns_name]
            self.assertTrue(ns.passed, msg=f"namespace {ns_name!r} must pass when genuinely populated with no collisions.")
            self.assertEqual(
                ns.inspected_count,
                expected_count,
                msg=(
                    f"namespace {ns_name!r} inspected_count must equal the actual on-disk count "
                    f"({expected_count}), got {ns.inspected_count} -- a fix that satisfies the "
                    "absent-root tests by always failing, or by fabricating a count, would still "
                    "be wrong here."
                ),
            )
            self.assertEqual(ns.findings, [])


if __name__ == "__main__":
    unittest.main()
