"""
MODULE: unit_tests/commit_guardian/test_ge_122a_2.py
GOAL: RED test-first stubs for GE-122a-2 -- "One work item cannot exist as two
    copies free to disagree about its state". The module under test,
    templates/scripts/commit_guardian/check_identifier_uniqueness.py, ALREADY
    EXISTS (built for the sibling AC GE-122a-1: three namespaces --
    acceptance-criteria, decisions, diagrams -- sharing one
    ``run_uniqueness_pass(collection_root) -> UniquenessVerdict`` entry point).
    This ticket is EXTRACT-AND-HARDEN, not greenfield: it adds a FOURTH
    namespace, ``work-items``, to the same shared verdict object, reusing the
    basename-duplicate-across-lifecycle-folders detection that already lives
    (dead, registered nowhere, always-exit-0) in
    templates/hooks/check_ticket_state_integrity.py.
BUSINESS CONTEXT: See
    docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122a-2.yaml
    and
    tickets/00_inbox/epics/EPIC-GE122UniquenessPassAndRepair/03_TICKET-20260818-GE-122a-2.md.
    GE-122a-1 covers "two unrelated artifacts claim one number"; this AC covers
    the sibling failure shape, "one artifact exists as two copies that may
    disagree about their own state". Five real duplicates exist in this
    repository today (four held by 00_inbox + 99_done, one by 00_inbox +
    01_todo) -- verified directly against the working tree at authoring time,
    not asserted against below (see "LIVE-TREE OVERRIDE" further down).

CONTRACT UNDER TEST (fixed here because the "work-items" namespace does not
exist yet in check_identifier_uniqueness.py; this is the explicit target
python-coder must satisfy):

    import check_identifier_uniqueness as mod
    verdict = mod.run_uniqueness_pass(collection_root)

    verdict.namespaces["work-items"]           -> NamespaceVerdict (NEW KEY)
    namespace_verdict.passed                   -> bool
    namespace_verdict.inspected_count          -> int, COUNT OF TICKET FILES
        WALKED across the four lifecycle folders named in
        <collection_root>/tickets/ticket_lifecycle.json (00_inbox, 01_todo,
        99_done, 99_rejected as of this writing -- READ from that file, never
        hard-coded). This is FILE-count semantics, matching the sibling
        namespaces' established NamespaceVerdict.inspected_count contract
        ("count of artifacts walked") -- NOT a count of distinct identifiers,
        even though the Gherkin prose says "identifiers". Namespace
        uniformity is a binding requirement of this AC's own Implementation
        Notes: "Feeds the same shared verdict object as GE-122a-1 ... Do not
        emit a separate work-item report format." Tickets sitting at the
        `tickets/` ROOT (outside all four lifecycle folders) are NOT counted
        -- they are unenrolled, not uniquely-held (see it_requirements in the
        AC YAML).
    namespace_verdict.findings                 -> list[Finding], one entry
        PER CONTESTED IDENTIFIER (a "TICKET-*.md" basename claimed by two or
        more lifecycle folders) -- never one entry per claimant file.
    finding.number                              -> str, the contested
        identifier (coder's chosen exact string form is not pinned by these
        tests; every assertion below keys on `finding.paths` instead, which
        IS pinned).
    finding.paths                               -> list[str], every claimant
        path for that identifier (>= 2 entries) -- SAME field GE-122a-1
        already fixed; must continue meaning "every claimant path".
    finding.declared_states                     -> dict[str, str] (NEW FIELD,
        ADDITIVE with a default so the three sibling namespaces are
        unaffected -- see Source-of-Truth Discipline Rule 5, "prefer
        expanding the test over shrinking production": this is a WIDENING of
        the shared Finding dataclass, not a narrowing, and none of
        GE-122a-1's six downstream consumers read anything but `.number` /
        `.paths`, so widening cannot break them). Maps EACH path in
        `finding.paths` to that copy's own declared `status:` frontmatter
        value, so a reader can identify the stale copy without reopening
        either file (AC-5).

    Identifier rule (AC it_requirement, verified 2026-08-17 against this
    repo's real tree): the declared identifier is a "TICKET-*.md" BASENAME
    match, never a bare "*.md" basename (which floods the report with every
    epic's Master_Plan.md / 01_*.md / 02_*.md) and never an epic-qualified
    full path (which would treat two files with the same basename in
    DIFFERENT epics as non-colliding even when their TICKET-content is
    identical -- not exercised here, since this AC's Gherkin fixes the
    identifier as a basename match).

LIVE-TREE OVERRIDE (read before touching test_pass_runs_against_the_real_tickets_tree):
    The AC's own test_spec calls this an "integration" test "[e]xecuted
    against the repository's actual tickets/ tree". The supervisor
    dispatching this authoring pass OVERRODE that instruction explicitly:
    ticket 04 of this epic (GE-122e-2) is about to repair/rename the five
    real duplicates, so a test asserting on the LIVE tickets/ tree would go
    stale (or worse, silently start asserting nothing) the moment ticket 04
    lands. This test instead builds a REPRODUCED-SHAPE fixture in an isolated
    tempdir -- same five identifier basenames, same folder pairings, same
    declared-state disagreement, plus several synthetic epics each
    contributing a Master_Plan.md and a numbered sub-ticket -- and runs the
    real entry point against that fixture. This still satisfies the AC's
    intent (a scale exercise a small unit fixture cannot make) without
    coupling to a tree ticket 04 is about to change.

REAL-ARTIFACT SIDE-EFFECT MANDATE (BP-1100f-2): does not apply here. This
    AC's deliverable is a READ-ONLY collection scan (it produces an in-memory
    verdict object and a printed report); it writes no durable artifact to
    disk. Every behavioral test below still exercises the real entry point
    against real on-disk ticket fixtures (never mocks the walk or the parse),
    which is the applicable bar for a read-side detector.

ARCHITECTURE / EXERCISE STRATEGY:
  - The canonical module is loaded by file path via importlib (same
    convention as unit_tests/commit_guardian/test_ge_122a_1.py and
    test_check_hook_parity.py in this directory) since it is not installed as
    a package.
  - Ticket frontmatter fixtures are produced with yaml.safe_dump (Fixture
    Authenticity Rule, docs/reference/fixture-policy.md) -- never a hand-typed
    "status: X" literal -- because a hand-typed literal reproduces the
    author's formatting bias rather than the real serializer's output, the
    exact defect class that hid the files_touched parser bug in
    EPIC-PhantomDoneFilesTouched.
  - The four-lifecycle-folder mapping is READ from a verbatim copy of this
    repo's own tickets/ticket_lifecycle.json (copied byte-for-byte via
    shutil.copy2, never restated as a Python literal) into every fixture
    tree, per the AC's own it_requirement: "must be read, not restated in
    code" -- binding on this test file's fixtures as much as on production.
  - Two tests (test_finding_names_every_holding_lifecycle_folder,
    test_finding_reports_both_declared_states_when_they_differ) assert
    against the pass's EMITTED report (mod.main()'s captured stdout/stderr),
    not only the returned verdict object, per those tests' own Test
    Requirements wording ("asserted against the emitted output rather than a
    helper return value").
  - No test baselines against a git ref (origin/main, main, a SHA) or the
    live tickets/ tree -- every fixture is a from-scratch tempdir.

DECISION HISTORY
- 2026-08-18 [GE-122a-2/test-writer]: Initial authoring of all seven RED test
  stubs (six behavioral + one reproduced-shape integration test). Verified
  RED via `AC_ENFORCE_STRICT=1 python -m pytest <this file> -q`: six fail with
  AssertionError from the `assertIn(_NS_WORK_ITEMS, verdict.namespaces, ...)`
  guard (the "work-items" namespace key does not exist in the current
  run_uniqueness_pass output) and one (the epic-subitem-prefix test) is
  expected to already pass under a correct no-op-for-missing-namespace
  implementation -- flagged and strengthened; see the test's own docstring
  and the sign-off comment's red_baseline block for the exact captured
  output.
"""

from __future__ import annotations

import contextlib
import importlib.util as _ilu
import io
import json
import os
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
_CANONICAL = _COMMIT_GUARDIAN_DIR / "check_identifier_uniqueness.py"
_REAL_LIFECYCLE_CONFIG = _REPO_ROOT / "tickets" / "ticket_lifecycle.json"

_NS_WORK_ITEMS = "work-items"


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
            f"check_identifier_uniqueness.py not found at canonical path "
            f"{_CANONICAL}. It should already exist from GE-122a-1 -- this "
            "would be a regression, not the expected RED state for GE-122a-2."
        )


# ---------------------------------------------------------------------------
# Lifecycle config -- read verbatim from this repo's real tickets/ticket_lifecycle.json
# ---------------------------------------------------------------------------

_LIFECYCLE_JSON = json.loads(_REAL_LIFECYCLE_CONFIG.read_text(encoding="utf-8"))
_LIFECYCLE_FOLDERS = [Path(entry["path"]).name for entry in _LIFECYCLE_JSON["folders"]]
_ALLOWED_STATUS_FOR = {
    Path(entry["path"]).name: entry["allowed_statuses"][0] for entry in _LIFECYCLE_JSON["folders"]
}


def _install_lifecycle_config(root: Path) -> None:
    """Copy the real tickets/ticket_lifecycle.json byte-for-byte into a fixture root.

    Per the Fixture Authenticity Rule, the allowed-status-per-folder mapping
    must be a verbatim on-disk artifact, never restated as a Python literal.

    Args:
        root: Fixture root to install the config under (as root/tickets/ticket_lifecycle.json).
    """
    dest = root / "tickets" / "ticket_lifecycle.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(_REAL_LIFECYCLE_CONFIG, dest)


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _write_ticket(path: Path, *, status: str, title: str = "Fixture ticket") -> None:
    """Write a ticket fixture with REAL YAML-serialized frontmatter.

    Uses yaml.safe_dump for the frontmatter block (never a hand-typed
    "status: X" string) per the Fixture Authenticity Rule -- a hand-typed
    literal reproduces the author's formatting bias rather than the real
    serializer's column-0 output, the defect class that hid the
    files_touched parser bug in EPIC-PhantomDoneFilesTouched.

    Args:
        path: Destination ticket file path (parents created as needed).
        status: The declared lifecycle status for this copy's frontmatter.
        title: Ticket title (frontmatter field, cosmetic for these fixtures).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = yaml.safe_dump({"status": status, "title": title}, sort_keys=False)
    content = f"---\n{frontmatter}---\n\n# {title}\n\nFixture ticket body.\n"
    path.write_text(content, encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    """Write a plain-text fixture artifact (e.g. an epic's Master_Plan.md).

    Args:
        path: Destination file path (parents created as needed).
        content: File content.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_work_items_fixture(root: Path) -> dict:
    """Build the shared fixture used by tests 1-5: two contested identifier
    pairs (mirroring the two real pairing shapes) plus one uncontested
    identifier per lifecycle folder plus one loose root ticket that must be
    excluded entirely.

    Args:
        root: Tempdir root to build the fixture under.

    Returns:
        A dict describing the fixture for assertions:
          "pair_a": (name, [path1, path2], {folder: status, ...})  -- inbox + active shape
          "pair_b": (name, [path1, path2], {folder: status, ...})  -- inbox + completed shape
          "uncontested": {folder: path}
          "loose_root": path
    """
    tickets_root = root / "tickets"

    # Pair A: 00_inbox + 01_todo, declared states differ -- mirrors the real
    # BP-1200a-1-ii shape (inbox + active).
    pair_a_name = "TICKET-20990101-FixtureFirstPair.md"
    pair_a_path_1 = tickets_root / "00_inbox" / pair_a_name
    pair_a_path_2 = tickets_root / "01_todo" / pair_a_name
    _write_ticket(pair_a_path_1, status="todo")
    _write_ticket(pair_a_path_2, status="in_progress")

    # Pair B: 00_inbox + 99_done, declared states differ -- mirrors the real
    # ConfigDrivenBuildPaths / FeedbackAnalysisPipeline / etc. shape (inbox +
    # completed).
    pair_b_name = "TICKET-20990102-FixtureSecondPair.md"
    pair_b_path_1 = tickets_root / "00_inbox" / pair_b_name
    pair_b_path_2 = tickets_root / "99_done" / pair_b_name
    _write_ticket(pair_b_path_1, status="todo")
    _write_ticket(pair_b_path_2, status="done")

    # One uncontested identifier per lifecycle folder, so "no finding when
    # held by exactly one folder" is exercised once per folder, not just once
    # overall.
    uncontested: dict[str, Path] = {}
    for folder in _LIFECYCLE_FOLDERS:
        name = f"TICKET-20990201-FixtureUncontested{folder}.md"
        p = tickets_root / folder / name
        _write_ticket(p, status=_ALLOWED_STATUS_FOR[folder])
        uncontested[folder] = p

    # A loose ticket sitting at the tickets/ ROOT, outside all four lifecycle
    # folders -- must be excluded entirely (unenrolled, not uniquely-held).
    loose_root = tickets_root / "TICKET-20990301-FixtureLooseRoot.md"
    _write_ticket(loose_root, status="todo")

    return {
        "pair_a": (
            pair_a_name,
            [pair_a_path_1, pair_a_path_2],
            {"00_inbox": "todo", "01_todo": "in_progress"},
        ),
        "pair_b": (
            pair_b_name,
            [pair_b_path_1, pair_b_path_2],
            {"00_inbox": "todo", "99_done": "done"},
        ),
        "uncontested": uncontested,
        "loose_root": loose_root,
    }


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


def _finding_matching_paths(findings, expected_paths, root: Path):
    """Return the Finding whose claimant paths exactly match expected_paths.

    Args:
        findings: Iterable of Finding objects to search.
        expected_paths: The exact set of claimant paths to match.
        root: Fixture root, used to resolve relative paths for comparison.

    Returns:
        The matching Finding, or None if no finding's paths equal expected_paths.
    """
    expected_resolved = {Path(p).resolve() for p in expected_paths}
    for finding in findings:
        if _resolved_path_set(finding.paths, root) == expected_resolved:
            return finding
    return None


def _run_main_and_capture(root: Path) -> tuple[str, int]:
    """Invoke the real check_identifier_uniqueness.main() against root and
    capture its emitted stdout/stderr and effective exit code.

    Chdir's into root for the duration of the call (main() reads Path.cwd())
    and always restores the original cwd afterward, even on exception.

    Args:
        root: The collection root to run main() against.

    Returns:
        A (captured_text, exit_code) tuple.
    """
    original_cwd = Path.cwd()
    os.chdir(root)
    buffer = io.StringIO()
    exit_code = 0
    try:
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            try:
                _mod.main()
            except SystemExit as exc:
                exit_code = exc.code if isinstance(exc.code, int) else 1
    finally:
        os.chdir(original_cwd)
    return buffer.getvalue(), exit_code


# ---------------------------------------------------------------------------
# Shared fixture scaffolding
# ---------------------------------------------------------------------------


class WorkItemsFixtureTestCase(unittest.TestCase):
    """Shared tempdir + lifecycle-config scaffolding for tests 1-5."""

    def setUp(self) -> None:
        _require_mod(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        _install_lifecycle_config(self.root)


# ---------------------------------------------------------------------------
# Tests 1-3: the contested-fixture half of the Gherkin
# ---------------------------------------------------------------------------


class TestContestedWorkItemsReporting(WorkItemsFixtureTestCase):
    """AC-1, AC-2, AC-3, AC-4, AC-5."""

    def test_identifier_in_two_lifecycle_folders_fails_the_pass(self):
        # covers: GE-122a-2
        """AC-1, AC-3, AC-4: over a fixture holding one identifier in
        00_inbox + 01_todo and a second in 00_inbox + 99_done, the
        "work-items" namespace must exist in the verdict, fail, and report
        exactly two findings -- one per contested identifier, never one per
        claimant file (which would be four).

        FAILS TODAY: run_uniqueness_pass's returned verdict.namespaces has no
        "work-items" key at all (only acceptance-criteria / decisions /
        diagrams exist) -- the assertIn below is the first failure.
        """
        _build_work_items_fixture(self.root)

        verdict = _mod.run_uniqueness_pass(self.root)

        self.assertIn(
            _NS_WORK_ITEMS,
            verdict.namespaces,
            msg=(
                "verdict.namespaces is missing the 'work-items' namespace "
                "entirely -- check_identifier_uniqueness.py has not yet been "
                "extended per GE-122a-2."
            ),
        )
        self.assertFalse(verdict.passed, msg="A collection with two contested identifiers must fail.")
        ns = verdict.namespaces[_NS_WORK_ITEMS]
        self.assertFalse(ns.passed, msg="The work-items namespace itself must report failure.")
        self.assertEqual(
            len(ns.findings),
            2,
            msg=(
                f"Expected exactly 2 findings (one per contested identifier), "
                f"got {len(ns.findings)}: {ns.findings}. A per-claimant-file "
                "report (4 findings) is the specific off-by-design error this "
                "AC calls out."
            ),
        )

    def test_finding_names_every_holding_lifecycle_folder(self):
        # covers: GE-122a-2
        """AC-4: each finding must name EVERY lifecycle folder holding a
        copy -- asserted both on the returned Finding.paths AND on the
        EMITTED report text (mod.main()'s captured stdout), per this test's
        own Test Requirements wording ("asserted against the emitted output
        rather than a helper return value").

        FAILS TODAY: no "work-items" namespace exists, so neither the
        returned-object assertion nor the emitted-output assertion can pass.
        """
        fixture = _build_work_items_fixture(self.root)
        pair_a_name, pair_a_paths, _ = fixture["pair_a"]
        pair_b_name, pair_b_paths, _ = fixture["pair_b"]

        verdict = _mod.run_uniqueness_pass(self.root)
        self.assertIn(_NS_WORK_ITEMS, verdict.namespaces)
        ns = verdict.namespaces[_NS_WORK_ITEMS]

        finding_a = _finding_matching_paths(ns.findings, pair_a_paths, self.root)
        finding_b = _finding_matching_paths(ns.findings, pair_b_paths, self.root)
        self.assertIsNotNone(
            finding_a,
            msg=f"No finding names exactly {pair_a_name}'s two claimant paths: {pair_a_paths}.",
        )
        self.assertIsNotNone(
            finding_b,
            msg=f"No finding names exactly {pair_b_name}'s two claimant paths: {pair_b_paths}.",
        )

        stdout_text, exit_code = _run_main_and_capture(self.root)
        self.assertNotEqual(0, exit_code, msg="main() must exit non-zero when findings exist.")
        for folder in ("00_inbox", "01_todo", "99_done"):
            self.assertIn(
                folder,
                stdout_text,
                msg=f"Emitted report never mentions lifecycle folder {folder!r}. Report:\n{stdout_text}",
            )

    def test_finding_reports_both_declared_states_when_they_differ(self):
        # covers: GE-122a-2
        """AC-2, AC-5: for pair_a (00_inbox declares "todo", 01_todo declares
        "in_progress"), the finding must carry BOTH declared states -- via a
        new Finding.declared_states mapping (path -> declared status) AND in
        the emitted report text -- so a reader can identify the stale copy
        without opening either file.

        FAILS TODAY: no "work-items" namespace exists yet, and even once it
        does, Finding currently has no declared_states attribute at all
        (AttributeError) until python-coder adds it.
        """
        fixture = _build_work_items_fixture(self.root)
        pair_a_name, pair_a_paths, pair_a_states = fixture["pair_a"]

        verdict = _mod.run_uniqueness_pass(self.root)
        self.assertIn(_NS_WORK_ITEMS, verdict.namespaces)
        ns = verdict.namespaces[_NS_WORK_ITEMS]

        finding_a = _finding_matching_paths(ns.findings, pair_a_paths, self.root)
        self.assertIsNotNone(finding_a, msg=f"No finding for {pair_a_name}'s contested pair.")

        self.assertTrue(
            hasattr(finding_a, "declared_states"),
            msg=(
                "Finding has no 'declared_states' attribute. GE-122a-2 requires "
                "a path -> declared-status mapping on each work-items Finding "
                "so a reader can see which copy is stale without opening "
                "either file."
            ),
        )
        self.assertEqual(
            set(finding_a.paths),
            set(finding_a.declared_states.keys()),
            msg="declared_states keys must line up 1:1 with finding.paths.",
        )
        self.assertEqual(
            set(finding_a.declared_states.values()),
            set(pair_a_states.values()),
            msg=(
                f"Expected both declared states {set(pair_a_states.values())!r} "
                f"to appear, got {finding_a.declared_states!r}."
            ),
        )

        stdout_text, _exit_code = _run_main_and_capture(self.root)
        for status in pair_a_states.values():
            self.assertIn(
                status,
                stdout_text,
                msg=f"Emitted report never mentions declared state {status!r}. Report:\n{stdout_text}",
            )


# ---------------------------------------------------------------------------
# Tests 4-5: the uncontested / count half of the Gherkin
# ---------------------------------------------------------------------------


class TestUncontestedWorkItems(WorkItemsFixtureTestCase):
    """AC-6, AC-7."""

    def test_identifier_in_one_folder_produces_no_finding_in_any_folder(self):
        # covers: GE-122a-2
        """AC-6: an identifier held in exactly one lifecycle folder must
        produce no finding -- exercised once PER lifecycle folder (00_inbox,
        01_todo, 99_done, 99_rejected) so the rule is not accidentally
        folder-specific (e.g. correct for 00_inbox but broken for
        99_rejected).

        FAILS TODAY: no "work-items" namespace exists yet, so the assertIn
        guard fails before the uncontested-identifier assertions are reached.
        """
        fixture = _build_work_items_fixture(self.root)

        verdict = _mod.run_uniqueness_pass(self.root)
        self.assertIn(_NS_WORK_ITEMS, verdict.namespaces)
        ns = verdict.namespaces[_NS_WORK_ITEMS]

        reported_paths: set = set()
        for finding in ns.findings:
            reported_paths |= _resolved_path_set(finding.paths, self.root)

        for folder, path in fixture["uncontested"].items():
            self.assertNotIn(
                path.resolve(),
                reported_paths,
                msg=(
                    f"An identifier held only in lifecycle folder {folder!r} "
                    "leaked into a finding -- the rule must not be folder-specific."
                ),
            )

    def test_inspected_identifier_count_is_reported(self):
        # covers: GE-122a-2
        """AC-7: the pass reports how many work-item files it inspected, and
        that count must equal an INDEPENDENTLY-COMPUTED count of TICKET-*.md
        files across the four lifecycle folders -- never merely non-zero, and
        never inflated by the loose root ticket (which sits outside all four
        lifecycle folders and must not be counted at all).

        FAILS TODAY: no "work-items" namespace exists yet, so
        ns.inspected_count cannot be read.
        """
        _build_work_items_fixture(self.root)

        verdict = _mod.run_uniqueness_pass(self.root)
        self.assertIn(_NS_WORK_ITEMS, verdict.namespaces)
        ns = verdict.namespaces[_NS_WORK_ITEMS]

        # Independently computed: glob each lifecycle folder's own TICKET-*.md
        # files (never the tickets/ root itself, and never ticket_lifecycle.json).
        computed_count = sum(
            len(list((self.root / "tickets" / folder).glob("TICKET-*.md"))) for folder in _LIFECYCLE_FOLDERS
        )
        self.assertEqual(
            computed_count,
            8,
            msg="Fixture sanity check failed: expected 2 pairs (2 files each) + 4 uncontested singles = 8.",
        )
        self.assertEqual(
            ns.inspected_count,
            computed_count,
            msg=(
                f"inspected_count must equal the independently-computed count "
                f"({computed_count}) of TICKET-*.md files across the four "
                f"lifecycle folders, got {ns.inspected_count}. A count that is "
                "merely non-zero cannot distinguish a real pass from a pass "
                "over a partial walk."
            ),
        )
        self.assertNotEqual(
            ns.inspected_count,
            computed_count + 1,
            msg=(
                "inspected_count must NOT include the loose root ticket "
                "(tickets/TICKET-20990301-FixtureLooseRoot.md) -- the tickets/ "
                "root is not a lifecycle location per this AC's it_requirements."
            ),
        )


# ---------------------------------------------------------------------------
# Test 6: shared numeric-prefix / Master_Plan.md robustness
# ---------------------------------------------------------------------------


class TestEpicSubitemPrefixesNotCollisions(unittest.TestCase):
    """test_epic_subitem_prefixes_are_not_reported_as_collisions."""

    def setUp(self) -> None:
        _require_mod(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        _install_lifecycle_config(self.root)

    def test_epic_subitem_prefixes_are_not_reported_as_collisions(self):
        # covers: GE-122a-2
        """A fixture holding two different epics (both nested under
        00_inbox/epics/, mirroring this repo's real has_epics_subfolder shape)
        that each contribute a Master_Plan.md AND a '01_'-prefixed sub-ticket
        must produce NO finding. Two failure modes this guards against:
          1. Master_Plan.md is excluded outright (it is not a "TICKET-*.md"
             basename at all under either epic's directory).
          2. Two DIFFERENT '01_TICKET-...' sub-tickets that merely share the
             leading ordinal "01_" must not be treated as the same identifier
             just because a naive rule matched on the numeric prefix instead
             of the full TICKET-content.

        This exercises the identifier rule's precision at the point the AC's
        own it_requirements calls out: "over bare basenames... the duplicate
        set is enormous and almost entirely spurious... every epic
        contributes Master_Plan.md, 01_*.md".

        This test may PASS under a naive "do nothing for work-items"
        no-op implementation (zero findings trivially satisfies "no
        finding"), so it does not by itself prove correct behavior -- it is
        a necessary, not sufficient, RED-state check alongside tests 1-5
        above, which DO fail under a no-op implementation.
        """
        epics_root = self.root / "tickets" / "00_inbox" / "epics"

        for epic_name, ticket_suffix in (
            ("EPIC-FixtureAlpha", "FixtureAlphaFirst"),
            ("EPIC-FixtureBeta", "FixtureBetaFirst"),
        ):
            epic_dir = epics_root / epic_name
            _write_text(epic_dir / "Master_Plan.md", f"# {epic_name} Master Plan\n\nFixture scaffold.\n")
            _write_ticket(
                epic_dir / f"01_TICKET-20990401-{ticket_suffix}.md",
                status="todo",
                title=ticket_suffix,
            )

        verdict = _mod.run_uniqueness_pass(self.root)
        self.assertIn(_NS_WORK_ITEMS, verdict.namespaces)
        ns = verdict.namespaces[_NS_WORK_ITEMS]

        self.assertTrue(
            ns.passed,
            msg=(
                "Two epics that each contribute a Master_Plan.md and a "
                "'01_'-prefixed sub-ticket must not be reported as a collision "
                "merely because they share a leading ordinal prefix or the "
                "Master_Plan.md filename."
            ),
        )
        self.assertEqual(len(ns.findings), 0, msg=f"Expected no findings, got: {ns.findings}")


# ---------------------------------------------------------------------------
# Test 7: reproduced-shape integration test (see LIVE-TREE OVERRIDE above)
# ---------------------------------------------------------------------------


class TestRepoShapedFixtureIntegration(unittest.TestCase):
    """test_pass_runs_against_the_real_tickets_tree.

    Named to match this AC's Test Requirements table exactly, but implemented
    against a REPRODUCED-SHAPE fixture rather than this repo's live tickets/
    tree -- see the module docstring's "LIVE-TREE OVERRIDE" section for why:
    ticket 04 of this epic is about to repair the five real duplicates this
    fixture mirrors, so asserting on the live tree would go stale (or worse,
    silently pass on nothing) the moment that ticket lands.
    """

    def setUp(self) -> None:
        _require_mod(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        _install_lifecycle_config(self.root)

    def test_pass_runs_against_the_real_tickets_tree(self):
        # covers: GE-122a-2
        """At repo scale (5 duplicate pairs, ~4 synthetic epics each
        contributing a Master_Plan.md + numbered sub-ticket, and a batch of
        uncontested standalone tickets), the pass must report EXACTLY the 5
        duplicate identifiers -- named after this repo's real five known
        duplicates purely as fixture labels, not as a live-tree read -- and
        zero spurious epic-sub-item findings.

        FAILS TODAY: no "work-items" namespace exists yet.
        """
        tickets_root = self.root / "tickets"

        # The five real duplicate shapes (fixture-only paths; NOT the live
        # tree). Four inbox+completed, one inbox+active, all with disagreeing
        # declared states, mirroring the real pairings verified 2026-08-18.
        duplicate_shapes = [
            ("TICKET-20260603-ConfigDrivenBuildPaths.md", "00_inbox", "99_done", "todo", "done"),
            ("TICKET-20260603-FeedbackAnalysisPipeline.md", "00_inbox", "99_done", "todo", "done"),
            ("TICKET-20260604-PullRequestAgentProjectContext.md", "00_inbox", "99_done", "todo", "done"),
            ("TICKET-20260605-ContractShrinkingSelfExclusion.md", "00_inbox", "99_done", "todo", "done"),
            ("TICKET-20260629-BP-1200a-1-ii.md", "00_inbox", "01_todo", "todo", "in_progress"),
        ]
        expected_pairs = []
        for name, folder_1, folder_2, status_1, status_2 in duplicate_shapes:
            path_1 = tickets_root / folder_1 / name
            path_2 = tickets_root / folder_2 / name
            _write_ticket(path_1, status=status_1)
            _write_ticket(path_2, status=status_2)
            expected_pairs.append((name, [path_1, path_2]))

        # Synthetic epics -- each contributes Master_Plan.md + a numbered
        # sub-ticket sharing the SAME ordinal prefix across epics, exercising
        # the epic-scale version of test 6 alongside the duplicate pairs.
        epics_root = tickets_root / "00_inbox" / "epics"
        for i in range(1, 5):
            epic_dir = epics_root / f"EPIC-FixtureRepoShape{i}"
            _write_text(epic_dir / "Master_Plan.md", f"# EPIC-FixtureRepoShape{i} Master Plan\n")
            _write_ticket(
                epic_dir / f"01_TICKET-2099060{i}-FixtureEpicItem{i}.md",
                status="todo",
                title=f"Fixture epic item {i}",
            )

        # Uncontested standalone tickets spread across all four folders.
        for i in range(1, 21):
            folder = _LIFECYCLE_FOLDERS[i % len(_LIFECYCLE_FOLDERS)]
            _write_ticket(
                tickets_root / folder / f"TICKET-20990{700 + i}-FixtureStandalone{i}.md",
                status=_ALLOWED_STATUS_FOR[folder],
                title=f"Fixture standalone {i}",
            )

        verdict = _mod.run_uniqueness_pass(self.root)
        self.assertIn(_NS_WORK_ITEMS, verdict.namespaces)
        ns = verdict.namespaces[_NS_WORK_ITEMS]

        self.assertFalse(ns.passed, msg="A collection with five planted duplicates must fail.")
        self.assertEqual(
            len(ns.findings),
            5,
            msg=(
                f"Expected exactly 5 findings mirroring this repo's five known "
                f"real duplicates, got {len(ns.findings)}: {ns.findings}. Any "
                "extra finding is a spurious epic-sub-item or standalone-ticket "
                "collision that must not occur."
            ),
        )
        for name, paths in expected_pairs:
            finding = _finding_matching_paths(ns.findings, paths, self.root)
            self.assertIsNotNone(finding, msg=f"No finding names exactly {name}'s two claimant paths: {paths}.")


if __name__ == "__main__":
    unittest.main()
