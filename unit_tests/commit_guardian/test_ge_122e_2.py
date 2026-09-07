"""
MODULE: unit_tests/commit_guardian/test_ge_122e_2.py
GOAL: RED test-first stubs for GE-122e-2 -- "Each work item that exists twice
    is reduced to the one copy that is right". This is the REPAIR half of the
    pair GE-122a-2 (detection) / GE-122e-2 (repair): GE-122a-2's pass, already
    implemented in templates/scripts/commit_guardian/_work_items_scanner.py
    and exposed via check_identifier_uniqueness.run_uniqueness_pass(), reports
    exactly five real work-item identifiers each held by two lifecycle
    folders (four intake+completed, one intake+active). This ticket is the
    repair: reduce each of those five to the one copy whose declared state
    agrees with the folder it sits in, without losing any content only the
    deleted copy held.

    NO REPAIR MODULE EXISTS YET. This is greenfield, not extract-and-harden
    (unlike GE-122a-2, which extended an already-existing scanner). This test
    module therefore FIXES the contract the repair entry point must satisfy
    -- see "CONTRACT UNDER TEST" below -- the same way test_ge_122a_2.py
    fixed the "work-items" namespace contract before it existed.

BUSINESS CONTEXT: See
    docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122e-2.yaml
    (read in full, INCLUDING its 2026-08-18 amendment) and
    tickets/00_inbox/epics/EPIC-GE122UniquenessPassAndRepair/04_TICKET-20260818-GE-122e-2.md.

    THE SURVIVOR RULE (binding on every test below): the survivor is the copy
    whose declared ``status:`` is PERMITTED, per tickets/ticket_lifecycle.json,
    in the lifecycle folder it should end up in -- never "the completed
    folder wins" as a rule of thumb. This module's fixture deliberately makes
    every one of its five pairs disagree between a "todo" declared state and
    a "done" declared state, so in every pair the "done" side is the later,
    correct state and its permitted folder is ``99_done`` (``tickets/
    ticket_lifecycle.json``: 00_inbox allows [todo, blocked, deferred];
    01_todo allows [todo, in_progress, blocked]; 99_done and 99_rejected
    allow [done, deferred] -- "done" is permitted ONLY in 99_done/99_rejected).

    Four of the five pairs already have their "done" copy sitting in
    ``99_done`` -- for those, the repair is a straightforward delete of the
    stale ``00_inbox`` copy, and a rule of thumb ("keep the completed-folder
    copy") would coincidentally get the right answer. The fifth pair -- the
    real TICKET-20260629-BP-1200a-1-ii shape -- is the discriminating case:
    its "done"-declaring copy sits in ``01_todo``, a folder that does NOT
    permit "done". A survivor rule computed correctly from
    ticket_lifecycle.json must MOVE that copy's content to ``99_done``; a
    rule of thumb that assumes "the non-inbox copy wins" would instead keep
    the ``01_todo`` copy in place, leaving a file whose folder still
    contradicts its own declared state -- exactly the defect this AC exists
    to prevent. test_bp1200a_survivor_is_moved_to_the_folder_its_declared_state_permits
    is the dedicated test for this case.

    The EPIC-MoveOnMainOnly exclusion this AC used to carry is MOOT (per the
    AC's own 2026-08-18 amendment): that pair was repaired outside this AC's
    scope, and tickets/99_rejected/ now holds only .gitkeep. This module does
    not test for it, per that amendment's explicit instruction not to look
    for it. The loose root tickets named in the AC's it_requirements are
    SEVENTEEN as of authoring and will keep moving -- see
    test_out_of_scope_tickets_are_untouched, which asserts them BY NAME
    against a list captured from the fixture itself (never a live-tree
    count), so this test file never depends on that number.

CONTRACT UNDER TEST (fixed here because no repair module exists yet -- this
is the explicit target python-coder must satisfy):

    import repair_work_item_duplicates as mod

    report = mod.repair_work_item_duplicates(tickets_root, lifecycle_config_path)

    report.resolutions              -> list[Resolution], one entry per
        identifier ACTUALLY repaired (a copy moved and/or deleted) in this
        call. Empty when the collection under tickets_root has no contested
        work-item identifier left to repair -- in particular, re-running the
        repair over its own already-repaired output (idempotency) must
        return an EMPTY list, not a list of no-op entries.

    resolution.identifier            -> str, the contested "TICKET-*.md"
        basename (e.g. "TICKET-20260603-ConfigDrivenBuildPaths.md").
    resolution.survivor_path         -> str, absolute path to the ONE file
        left behind for this identifier after the call returns.
    resolution.deleted_path          -> str, absolute path to the file this
        call removed (must no longer exist on disk after the call returns).
    resolution.resolution            -> str, a short label for the decision
        taken (e.g. which side's declared state won and why). Exact wording
        is NOT pinned by any test below -- only that it is a non-empty
        string.
    resolution.reason                -> str, a human-readable explanation of
        the decision. Pinned by exactly one durable property (AC-3): it MUST
        appear, verbatim as returned, somewhere in the SURVIVOR FILE'S OWN
        on-disk content after the call returns -- "recorded on the surviving
        file", not merely returned to the caller and then discarded. A
        resolution.reason that is never written to disk fails this contract
        even if the return value itself looks correct.

    The function performs the real filesystem side effects itself (moves the
    survivor into the folder its declared state permits when it is not
    already there, deletes the losing copy) -- these tests build real ticket
    fixtures on a real tempdir and invoke the real entry point; they never
    mock the filesystem operations themselves (Real-Artifact Behavioral Test
    Mandate, BP-1100f-2 -- the deliverable here is durable ticket files on
    disk, not an in-memory report).

ARCHITECTURE / FIXTURE STRATEGY:
  - Ticket frontmatter fixtures are produced with yaml.safe_dump (Fixture
    Authenticity Rule) -- never a hand-typed "status: X" literal -- for the
    same reason test_ge_122a_2.py gives: a hand-typed literal reproduces the
    author's formatting bias rather than the real serializer's output, the
    exact defect class that hid the files_touched parser bug in
    EPIC-PhantomDoneFilesTouched.
  - The lifecycle folder / allowed-status mapping is READ from a verbatim
    copy of this repo's own tickets/ticket_lifecycle.json (copied
    byte-for-byte via shutil.copy2, never restated as a Python literal), per
    this AC's own it_requirement that the survivor decision "must be
    computed from this data rather than from an assumption about which
    folder is 'more final'" -- binding on this test file's fixtures and
    assertions as much as on production.
  - Every fixture lives in a fresh tempdir per test class; NOTHING is
    asserted against the live tickets/ tree (the repair this ticket
    implements is about to change that tree for real, so a test coupled to
    it would go stale, or worse, silently start asserting nothing, the
    moment the real repair lands -- same reasoning test_ge_122a_2.py's
    "LIVE-TREE OVERRIDE" section gives).
  - No test baselines against origin/main, main, or a hardcoded SHA -- every
    fixture is built from scratch.
  - This module's own docstrings and identifiers deliberately avoid citing
    the retired "GE-119" identifier anywhere (see
    unit_tests/commit_guardian/test_ge_122e_1.py's live-citation guard);
    illustrative examples elsewhere in this codebase use a "GE-000" style
    placeholder for the same reason -- not needed in this module since no
    illustrative identifier examples are required here.

DECISION HISTORY
- 2026-08-18 [GE-122e-2/test-writer]: Initial authoring of all RED test
  stubs. No repair module exists yet at
  templates/scripts/commit_guardian/repair_work_item_duplicates.py, so every
  test in this module fails at the same first gate: _require_mod's
  assertion that the canonical module file exists. See the sign-off
  comment's red_baseline block for the exact captured output.
"""

from __future__ import annotations

import hashlib
import importlib.util as _ilu
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
_CANONICAL = _COMMIT_GUARDIAN_DIR / "repair_work_item_duplicates.py"
_UNIQUENESS_CANONICAL = _COMMIT_GUARDIAN_DIR / "check_identifier_uniqueness.py"
_REAL_LIFECYCLE_CONFIG = _REPO_ROOT / "tickets" / "ticket_lifecycle.json"


def _load_module_by_path(path: Path, module_name: str):
    """Dynamically import a module from an explicit file path.

    Args:
        path: Absolute path to the module's .py file.
        module_name: The name to register the module under in sys.modules.

    Returns:
        The loaded module, or None if *path* does not exist.
    """
    if not path.exists():
        return None
    spec = _ilu.spec_from_file_location(module_name, path)
    mod = _ilu.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


_repair_mod = _load_module_by_path(_CANONICAL, "repair_work_item_duplicates")
_uniqueness_mod = _load_module_by_path(_UNIQUENESS_CANONICAL, "check_identifier_uniqueness")


def _require_repair_mod(test_case: unittest.TestCase) -> None:
    """Fail with a clear message if the repair module could not be loaded.

    Args:
        test_case: The calling TestCase instance.
    """
    if _repair_mod is None:
        test_case.fail(
            "repair_work_item_duplicates.py not found at canonical path "
            f"{_CANONICAL}. This is GE-122e-2's own deliverable -- it does "
            "not exist yet, which is the expected RED state before "
            "python-coder implements it."
        )


# ---------------------------------------------------------------------------
# Lifecycle config -- read verbatim from this repo's real
# tickets/ticket_lifecycle.json, per the Fixture Authenticity Rule.
# ---------------------------------------------------------------------------

_LIFECYCLE_JSON = yaml.safe_load(_REAL_LIFECYCLE_CONFIG.read_text(encoding="utf-8"))
_LIFECYCLE_FOLDERS = [Path(entry["path"]).name for entry in _LIFECYCLE_JSON["folders"]]
_ALLOWED_STATUSES_FOR = {
    Path(entry["path"]).name: list(entry["allowed_statuses"]) for entry in _LIFECYCLE_JSON["folders"]
}


def _install_lifecycle_config(root: Path) -> Path:
    """Copy the real tickets/ticket_lifecycle.json byte-for-byte into a fixture root.

    Args:
        root: Fixture root to install the config under.

    Returns:
        The path the config was installed at (root/tickets/ticket_lifecycle.json).
    """
    dest = root / "tickets" / "ticket_lifecycle.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(_REAL_LIFECYCLE_CONFIG, dest)
    return dest


def _folder_permits_status(folder_name: str, status: str) -> bool:
    """Whether *folder_name* permits *status* per the real lifecycle config.

    Args:
        folder_name: A lifecycle folder basename (e.g. "99_done").
        status: A declared ``status:`` value (e.g. "done").

    Returns:
        True iff the folder's allowed_statuses list contains status.
    """
    return status in _ALLOWED_STATUSES_FOR.get(folder_name, [])


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _write_ticket(path: Path, *, status: str, title: str = "Fixture ticket", extra_body: str = "") -> None:
    """Write a ticket fixture with REAL YAML-serialized frontmatter.

    Uses yaml.safe_dump for the frontmatter block (never a hand-typed
    "status: X" string) per the Fixture Authenticity Rule.

    Args:
        path: Destination ticket file path (parents created as needed).
        status: The declared lifecycle status for this copy's frontmatter.
        title: Ticket title (frontmatter field).
        extra_body: Additional Markdown appended after the ticket body --
            used to plant content unique to one copy of a pair (e.g. a
            sign-off comment), so the "no content lost" tests have something
            real to assert on.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = yaml.safe_dump({"status": status, "title": title}, sort_keys=False)
    content = f"---\n{frontmatter}---\n\n# {title}\n\nFixture ticket body.\n"
    if extra_body:
        content += f"\n{extra_body}\n"
    path.write_text(content, encoding="utf-8")


def _parse_frontmatter(path: Path) -> dict:
    """Read and parse a ticket fixture's YAML frontmatter block.

    Args:
        path: Path to the ticket Markdown file.

    Returns:
        The parsed frontmatter mapping, or {} if the file has none.
    """
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    end = text.find("---", 3)
    fm_text = text[3:end] if end != -1 else text[3:]
    data = yaml.safe_load(fm_text)
    return data if isinstance(data, dict) else {}


def _sha256(path: Path) -> str:
    """Return the sha256 hex digest of *path*'s content, for idempotency checks."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


# One shared shape for all five pairs: a "todo" declaring copy (always the
# one that must be deleted) and a "done" declaring copy (always the later,
# correct state) that carries a marker unique to it -- except for pair 2,
# where the marker is deliberately placed on the copy TO BE DELETED, so the
# "no content lost" test exercises the case where the deleted copy, not the
# survivor, is the one holding content nothing else has (AC-4 / the
# Implementation Notes' "two copies that have drifted may each hold
# something the other lacks").
_FOUR_INTAKE_PLUS_COMPLETED = [
    "TICKET-20260603-ConfigDrivenBuildPaths.md",
    "TICKET-20260603-FeedbackAnalysisPipeline.md",
    "TICKET-20260604-PullRequestAgentProjectContext.md",
    "TICKET-20260605-ContractShrinkingSelfExclusion.md",
]
_FIFTH_INTAKE_PLUS_ACTIVE = "TICKET-20260629-BP-1200a-1-ii.md"


def _build_five_duplicates_fixture(root: Path) -> dict:
    """Build the five real duplicate shapes as on-disk ticket fixtures.

    Four pairs of (00_inbox: todo) + (99_done: done); one pair of
    (00_inbox: todo) + (01_todo: done) -- the discriminating BP-1200a-1-ii
    shape, whose "done" copy sits in a folder that does not permit "done".

    Args:
        root: Tempdir root to build the fixture under.

    Returns:
        Dict keyed by identifier basename, each value a dict with:
          "todo_path": Path -- the copy that must always be deleted.
          "done_path": Path -- the copy carrying the later, correct state.
          "expected_survivor_path": Path -- tickets/99_done/<name>, the ONE
              correct location for the survivor regardless of where the
              "done" copy started out.
          "deleted_marker": str | None -- present only for the one pair
              (FeedbackAnalysisPipeline) whose TO-BE-DELETED copy carries
              content found nowhere else, for the "no content lost" test.
    """
    tickets_root = root / "tickets"
    pairs: dict[str, dict] = {}

    for name in _FOUR_INTAKE_PLUS_COMPLETED:
        todo_path = tickets_root / "00_inbox" / name
        done_path = tickets_root / "99_done" / name
        deleted_marker = None
        if name == "TICKET-20260603-FeedbackAnalysisPipeline.md":
            deleted_marker = f"UNIQUE-CONTENT-ONLY-ON-DELETED-COPY-{name}"
            _write_ticket(
                todo_path,
                status="todo",
                title=name,
                extra_body=f"## Comments\n\n{deleted_marker}\n",
            )
        else:
            _write_ticket(todo_path, status="todo", title=name)
        _write_ticket(done_path, status="done", title=name)
        pairs[name] = {
            "todo_path": todo_path,
            "done_path": done_path,
            "expected_survivor_path": tickets_root / "99_done" / name,
            "deleted_marker": deleted_marker,
        }

    fifth_name = _FIFTH_INTAKE_PLUS_ACTIVE
    fifth_todo_path = tickets_root / "00_inbox" / fifth_name
    fifth_done_path = tickets_root / "01_todo" / fifth_name
    _write_ticket(fifth_todo_path, status="todo", title=fifth_name)
    _write_ticket(fifth_done_path, status="done", title=fifth_name)
    pairs[fifth_name] = {
        "todo_path": fifth_todo_path,
        "done_path": fifth_done_path,
        "expected_survivor_path": tickets_root / "99_done" / fifth_name,
        "deleted_marker": None,
    }

    return pairs


def _build_referencer_fixtures(root: Path, identifiers: list[str]) -> dict[str, Path]:
    """Build one referencing ticket per identifier, each naming it in depends_on.

    Args:
        root: Tempdir root the five-duplicates fixture was built under.
        identifiers: The identifier basenames to build a referencer for.

    Returns:
        Mapping of identifier basename -> the referencer ticket's own path.
    """
    tickets_root = root / "tickets"
    referencers: dict[str, Path] = {}
    for index, identifier in enumerate(sorted(identifiers), start=1):
        ref_path = tickets_root / "00_inbox" / f"TICKET-2099050{index}-FixtureReferencer{index}.md"
        ref_path.parent.mkdir(parents=True, exist_ok=True)
        frontmatter = yaml.safe_dump(
            {"status": "todo", "title": f"Referencer {index}", "depends_on": [identifier]},
            sort_keys=False,
        )
        ref_path.write_text(
            f"---\n{frontmatter}---\n\n# Referencer {index}\n\nRefers to {identifier}.\n",
            encoding="utf-8",
        )
        referencers[identifier] = ref_path
    return referencers


def _build_loose_root_tickets(root: Path) -> list[Path]:
    """Build several loose TICKET-*.md fixtures sitting at tickets/ ROOT.

    These are out of scope for the repair per the AC's it_requirements --
    they are unenrolled (outside all four lifecycle folders), not
    twice-held, and must be left completely untouched.

    Args:
        root: Tempdir root to build the fixture under.

    Returns:
        Sorted list of the loose root ticket paths created.
    """
    tickets_root = root / "tickets"
    names = [
        "TICKET-20990601-FixtureLooseRootAlpha.md",
        "TICKET-20990602-FixtureLooseRootBeta.md",
        "TICKET-20990603-FixtureLooseRootGamma.md",
    ]
    paths = []
    for name in names:
        path = tickets_root / name
        _write_ticket(path, status="todo", title=name)
        paths.append(path)
    return sorted(paths)


def _resolve_identifier(tickets_root: Path, identifier: str) -> list[Path]:
    """Resolve an identifier basename to every file claiming it across the
    four lifecycle folders -- the same "reference resolution" a real
    depends_on consumer would perform.

    Args:
        tickets_root: The tickets/ directory to search.
        identifier: A "TICKET-*.md" basename.

    Returns:
        Sorted list of matching paths (expected length 1 after a correct repair).
    """
    matches = []
    for folder in _LIFECYCLE_FOLDERS:
        candidate = tickets_root / folder / identifier
        if candidate.is_file():
            matches.append(candidate)
    return sorted(matches)


# ---------------------------------------------------------------------------
# Shared fixture scaffolding
# ---------------------------------------------------------------------------


class FiveDuplicatesFixtureTestCase(unittest.TestCase):
    """Shared tempdir + lifecycle-config + five-pairs scaffolding."""

    def setUp(self) -> None:
        _require_repair_mod(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.tickets_root = self.root / "tickets"
        self.lifecycle_config_path = _install_lifecycle_config(self.root)
        self.pairs = _build_five_duplicates_fixture(self.root)
        self.loose_root_tickets = _build_loose_root_tickets(self.root)
        self.referencers = _build_referencer_fixtures(self.root, list(self.pairs.keys()))

    def _run_repair(self):
        """Invoke the real repair entry point over this test's fixture root."""
        return _repair_mod.repair_work_item_duplicates(self.tickets_root, self.lifecycle_config_path)


# ---------------------------------------------------------------------------
# AC-1 / AC-7: each of the five exists as exactly one file, and it is the
# RIGHT one, not merely a surviving one.
# ---------------------------------------------------------------------------


class TestEachIdentifierExistsExactlyOnce(FiveDuplicatesFixtureTestCase):
    def test_each_of_the_five_identifiers_exists_exactly_once(self):
        # covers: GE-122e-2
        """AC-1, AC-7: after the repair, each of the five named identifiers is
        held by exactly one file -- and it MUST be the correct survivor
        (tickets/99_done/<name>), never merely "a" survivor. Counting alone
        does not cover this: deleting the WRONG copy also yields one file, so
        every pair's assertion below pins the exact surviving path.

        FAILS TODAY: repair_work_item_duplicates.py does not exist at its
        canonical path -- setUp's _require_repair_mod call fails first.
        """
        self._run_repair()

        for identifier, pair in self.pairs.items():
            matches = _resolve_identifier(self.tickets_root, identifier)
            self.assertEqual(
                len(matches),
                1,
                msg=f"{identifier}: expected exactly one surviving file, found {matches}.",
            )
            self.assertEqual(
                matches[0],
                pair["expected_survivor_path"],
                msg=(
                    f"{identifier}: exactly one file survived, but at {matches[0]}, "
                    f"not the correct location {pair['expected_survivor_path']} -- "
                    "one surviving file is not the same as the RIGHT one surviving."
                ),
            )
            self.assertFalse(pair["todo_path"].exists(), msg=f"{pair['todo_path']} must have been removed.")


# ---------------------------------------------------------------------------
# AC-2: the surviving file's folder agrees with its own declared state.
# ---------------------------------------------------------------------------


class TestSurvivorFolderAgreesWithDeclaredState(FiveDuplicatesFixtureTestCase):
    def test_surviving_copy_folder_agrees_with_its_declared_state(self):
        # covers: GE-122e-2
        """AC-2: for each of the five, the surviving file's lifecycle folder
        is the one ticket_lifecycle.json permits for the state DECLARED IN
        ITS OWN CONTENT -- computed from the config, never assumed to be
        "the completed folder" or "the non-inbox folder" as a rule of thumb.

        FAILS TODAY: no repair module exists.
        """
        self._run_repair()

        for identifier, pair in self.pairs.items():
            matches = _resolve_identifier(self.tickets_root, identifier)
            self.assertEqual(len(matches), 1, msg=f"{identifier}: setup precondition failed: {matches}")
            survivor_path = matches[0]
            survivor_folder = survivor_path.parent.name
            declared_status = _parse_frontmatter(survivor_path).get("status")

            self.assertTrue(
                _folder_permits_status(survivor_folder, declared_status),
                msg=(
                    f"{identifier}: survivor at {survivor_path} declares status "
                    f"{declared_status!r}, which ticket_lifecycle.json does NOT "
                    f"permit in folder {survivor_folder!r} (permits "
                    f"{_ALLOWED_STATUSES_FOR.get(survivor_folder)!r}). Folder "
                    "position and declared state must agree."
                ),
            )
            self.assertEqual(declared_status, "done", msg=f"{identifier}: expected the later 'done' state to win.")

    def test_bp1200a_survivor_is_moved_to_the_folder_its_declared_state_permits(self):
        # covers: GE-122e-2
        """The discriminating case named in this AC's own body: for
        TICKET-20260629-BP-1200a-1-ii, the "done"-declaring copy sits in
        01_todo -- a folder that does NOT permit "done" -- on top of the
        00_inbox copy declaring "todo". A survivor rule that assumes "the
        non-inbox / more-final-looking folder wins" would leave the 01_todo
        copy in place, which fails this assertion (01_todo never appears in
        ticket_lifecycle.json's allowed_statuses for "done"). The correct
        survivor is computed from the config and lands in tickets/99_done/,
        requiring an actual file relocation, not just a delete.

        FAILS TODAY: no repair module exists.
        """
        identifier = _FIFTH_INTAKE_PLUS_ACTIVE
        pair = self.pairs[identifier]

        self._run_repair()

        self.assertFalse(
            pair["done_path"].exists(),
            msg=(
                f"{pair['done_path']} (01_todo, declares 'done') must not remain in place -- "
                "01_todo does not permit 'done' per ticket_lifecycle.json, so keeping it there "
                "is the exact 'non-inbox folder wins' defect this case exists to catch."
            ),
        )
        self.assertFalse(pair["todo_path"].exists(), msg=f"{pair['todo_path']} must have been removed.")
        self.assertTrue(
            pair["expected_survivor_path"].exists(),
            msg=(
                f"expected the survivor to be relocated to {pair['expected_survivor_path']} "
                "(the folder its declared 'done' state actually permits)."
            ),
        )
        self.assertEqual(_parse_frontmatter(pair["expected_survivor_path"]).get("status"), "done")


# ---------------------------------------------------------------------------
# AC-3: divergent declared states -> resolution + reason recorded on the
# surviving file.
# ---------------------------------------------------------------------------


class TestDivergentPairRecordsResolutionAndReason(FiveDuplicatesFixtureTestCase):
    def test_divergent_pair_records_the_resolution_and_reason(self):
        # covers: GE-122e-2
        """AC-3: where the two copies declared different states (every pair
        in this fixture does), the surviving file must carry BOTH the
        resolution taken and the reason -- recorded ON THE FILE ITSELF, not
        merely returned in the report object, so no copy is deleted
        silently. This test ties the returned Resolution.reason string back
        to the survivor's own on-disk content: a Resolution.reason that is
        never actually written to the file fails this assertion even if the
        return value looks correct.

        FAILS TODAY: no repair module exists.
        """
        identifier = "TICKET-20260603-ConfigDrivenBuildPaths.md"
        pair = self.pairs[identifier]

        report = self._run_repair()

        matching = [r for r in report.resolutions if r.identifier == identifier]
        self.assertEqual(
            len(matching),
            1,
            msg=f"expected exactly one Resolution for {identifier} in report.resolutions, got {matching}.",
        )
        resolution = matching[0]

        self.assertTrue(
            isinstance(resolution.resolution, str) and resolution.resolution.strip(),
            msg="Resolution.resolution must be a non-empty string describing the decision taken.",
        )
        self.assertTrue(
            isinstance(resolution.reason, str) and resolution.reason.strip(),
            msg="Resolution.reason must be a non-empty string explaining the decision.",
        )

        survivor_text = pair["expected_survivor_path"].read_text(encoding="utf-8")
        self.assertIn(
            resolution.reason,
            survivor_text,
            msg=(
                f"Resolution.reason ({resolution.reason!r}) was returned but never written to "
                f"the surviving file {pair['expected_survivor_path']} -- the resolution and "
                "reason must be recorded ON THE FILE, not just handed back to the caller."
            ),
        )


# ---------------------------------------------------------------------------
# AC-4: content differing beyond declared state is not discarded.
# ---------------------------------------------------------------------------


class TestNoContentLostFromDeletedCopy(FiveDuplicatesFixtureTestCase):
    def test_no_content_lost_from_the_deleted_copy(self):
        # covers: GE-122e-2
        """AC-4: for the one pair in this fixture whose TO-BE-DELETED copy
        (TICKET-20260603-FeedbackAnalysisPipeline's 00_inbox copy) carries a
        unique comment marker found on no other file, the surviving file
        must retain that content after the repair -- so no completed work
        (a sign-off comment, in this case) is discarded merely because it
        happened to sit on the copy that lost the declared-state comparison.

        FAILS TODAY: no repair module exists.
        """
        identifier = "TICKET-20260603-FeedbackAnalysisPipeline.md"
        pair = self.pairs[identifier]
        marker = pair["deleted_marker"]
        self.assertIsNotNone(marker, msg="fixture precondition: this pair must plant a deleted_marker.")
        self.assertNotIn(
            marker,
            pair["done_path"].read_text(encoding="utf-8"),
            msg="fixture precondition: the marker must NOT already be on the copy that survives untouched.",
        )

        self._run_repair()

        survivor_text = pair["expected_survivor_path"].read_text(encoding="utf-8")
        self.assertIn(
            marker,
            survivor_text,
            msg=(
                f"content unique to the deleted copy ({marker!r}) is missing from the surviving "
                f"file {pair['expected_survivor_path']} -- the repair discarded content only the "
                "deleted copy held, which this AC's own Implementation Notes forbid."
            ),
        )


# ---------------------------------------------------------------------------
# AC-5: the work-item uniqueness pass reports zero findings afterwards.
# ---------------------------------------------------------------------------


class TestUniquenessPassReportsZeroFindingsAfterRepair(FiveDuplicatesFixtureTestCase):
    def test_work_item_uniqueness_pass_reports_zero_findings(self):
        # covers: GE-122e-2
        """AC-5: GE-122a-2's own pass, run UNMODIFIED over the repaired
        collection, reports no identifier held by more than one lifecycle
        folder. Uses the real check_identifier_uniqueness.run_uniqueness_pass
        entry point -- the same instrument that detected the five duplicates
        in the first place -- rather than a bespoke audit written just for
        this test.

        FAILS TODAY: no repair module exists (and even once it does, this
        assertion additionally requires check_identifier_uniqueness.py's
        "work-items" namespace from GE-122a-2 to already be implemented and
        loadable at its canonical path).
        """
        if _uniqueness_mod is None:
            self.fail(
                f"check_identifier_uniqueness.py not found at {_UNIQUENESS_CANONICAL} -- "
                "GE-122a-2's detection pass must exist for this repaired-collection "
                "assertion to run at all."
            )

        self._run_repair()

        verdict = _uniqueness_mod.run_uniqueness_pass(self.root)
        self.assertIn("work-items", verdict.namespaces, msg="the work-items namespace is missing from the verdict.")
        ns = verdict.namespaces["work-items"]
        self.assertTrue(ns.passed, msg=f"expected the work-items namespace to pass after repair, findings: {ns.findings}")
        self.assertEqual(
            ns.findings,
            [],
            msg=f"expected zero findings after repair, got {len(ns.findings)}: {ns.findings}",
        )


# ---------------------------------------------------------------------------
# AC-6: every reference to any of the five resolves to the surviving file.
# ---------------------------------------------------------------------------


class TestReferencesResolveToSurvivor(FiveDuplicatesFixtureTestCase):
    def test_references_to_the_five_resolve_to_the_surviving_file(self):
        # covers: GE-122e-2
        """AC-6: every reference to any of the five identifiers -- modeled
        here as a separate referencing ticket naming the identifier in its
        own depends_on list -- resolves to the surviving file and to no
        other. Resolution is performed the same way a real depends_on
        consumer would: locate every file with that exact basename across
        the four lifecycle folders.

        FAILS TODAY: no repair module exists.
        """
        self._run_repair()

        for identifier, pair in self.pairs.items():
            referencer_path = self.referencers[identifier]
            self.assertTrue(
                referencer_path.exists(),
                msg=f"fixture precondition: the referencer for {identifier} must still exist.",
            )
            referenced_id = _parse_frontmatter(referencer_path).get("depends_on", [None])[0]
            self.assertEqual(referenced_id, identifier, msg="fixture precondition: depends_on must name the identifier.")

            resolved = _resolve_identifier(self.tickets_root, identifier)
            self.assertEqual(
                len(resolved),
                1,
                msg=f"{identifier}: reference does not resolve to exactly one file, got {resolved}.",
            )
            self.assertEqual(
                resolved[0],
                pair["expected_survivor_path"],
                msg=(
                    f"{identifier}: reference resolves to {resolved[0]}, not the correct "
                    f"surviving file {pair['expected_survivor_path']}."
                ),
            )


# ---------------------------------------------------------------------------
# Out-of-scope negative assertion (by NAME, per the 2026-08-18 amendment).
# ---------------------------------------------------------------------------


class TestOutOfScopeTicketsUntouched(FiveDuplicatesFixtureTestCase):
    def test_out_of_scope_tickets_are_untouched(self):
        # covers: GE-122e-2
        """Every loose TICKET-*.md at tickets/ root is still at tickets/
        root after the repair, asserted BY NAME against a list captured from
        this test's own fixture BEFORE the repair runs -- never by count,
        which would break the moment an unrelated ticket is added at root.
        Content is also asserted byte-identical, so "still present" cannot
        be satisfied by silently rewriting it.

        The EPIC-MoveOnMainOnly half this descriptor used to carry is
        deleted rather than rewritten, per the AC's own 2026-08-18
        amendment: that pair no longer exists in either lifecycle folder, so
        asserting it is unsatisfiable and out of scope for this module.

        FAILS TODAY: no repair module exists.
        """
        names_before = sorted(p.name for p in self.loose_root_tickets)
        hashes_before = {p.name: _sha256(p) for p in self.loose_root_tickets}

        self._run_repair()

        tickets_root_files = sorted(p.name for p in self.tickets_root.glob("TICKET-*.md"))
        for name in names_before:
            self.assertIn(
                name,
                tickets_root_files,
                msg=(
                    f"loose root ticket {name!r} (captured by name before the repair) is no "
                    f"longer present at tickets/ root. Present: {tickets_root_files}."
                ),
            )
        for name, digest_before in hashes_before.items():
            current_path = self.tickets_root / name
            self.assertTrue(current_path.exists(), msg=f"{name} must still exist at tickets/ root.")
            self.assertEqual(
                _sha256(current_path),
                digest_before,
                msg=f"{name}'s content changed -- out-of-scope tickets must be left completely untouched.",
            )


# ---------------------------------------------------------------------------
# Idempotency (Implementation Notes: "re-running the repair over the
# repaired collection makes no further change").
# ---------------------------------------------------------------------------


class TestRepairIsIdempotent(FiveDuplicatesFixtureTestCase):
    def test_rerunning_repair_over_the_repaired_collection_changes_nothing(self):
        # covers: GE-122e-2
        """Implementation Notes: "Idempotency: re-running the repair over the
        repaired collection makes no further change." The second call's
        report.resolutions must be empty (nothing left to repair), and every
        survivor file's content must be byte-identical to what the first
        call produced.

        FAILS TODAY: no repair module exists.
        """
        self._run_repair()

        survivor_hashes_after_first_run = {
            identifier: _sha256(pair["expected_survivor_path"]) for identifier, pair in self.pairs.items()
        }

        second_report = self._run_repair()

        self.assertEqual(
            second_report.resolutions,
            [],
            msg=(
                "a second repair run over an already-repaired collection must find nothing left "
                f"to repair, but reported: {second_report.resolutions}"
            ),
        )
        for identifier, pair in self.pairs.items():
            self.assertEqual(
                _sha256(pair["expected_survivor_path"]),
                survivor_hashes_after_first_run[identifier],
                msg=f"{identifier}'s survivor file content changed on the second (idempotent) run.",
            )


if __name__ == "__main__":
    unittest.main()
